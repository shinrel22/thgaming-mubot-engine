import ctypes
from ctypes import wintypes, windll
from typing import Callable

from src.bases.os import OperatingSystemAPIPrototype
from src.utils import hex_string_to_int_list
from src.os.windows.kernel32 import (
    Process,
    PageProtection,
    AllocationType,
    VirtualAllocEx,
    WriteProcessMemory,
    ReadProcessMemory,
    CreateRemoteThread,
    TerminateProcess,
    ResumeThread,
    SuspendThread,
    Process32Entry,
    ThreadEntry32,
    ThreadContext,
    ModuleEntry32,
    Module32Next,
    Module32First,
    TH32CS_SNAPPROCESS,
    TH32CS_SNAPMODULE,
    TH32CS_SNAPTHREAD,
    INVALID_HANDLE_VALUE,
    THREAD_ALL_ACCESS,
    CONTEXT_FULL,
    CONTEXT_DEBUG_REGISTERS,
    OpenProcess,
    OpenThread,
    GetThreadContext,
    Thread32First,
    Thread32Next,
    CloseHandle,
    WaitForSingleObject,
    VirtualFreeEx,
    CreateToolhelp32Snapshot,
    Process32First,
    Process32Next,
    GetExitCodeThread,
    GetModuleHandleA,
    GetProcAddress,
    LPTHREAD_START_ROUTINE,
    INFINITE,
    FreeType,
    THREAD_CREATE_SUSPENDED,
    ERROR_IO_PENDING,
    WT_EXECUTE_IN_WAIT_THREAD,
    WT_EXECUTE_ONLY_ONCE,
    RegisterWaitForSingleObject,
    UnregisterWaitEx,
    WAIT_OR_TIMER_CALLBACK,
    GetExitCodeProcess,
    STILL_ACTIVE,
    MemoryBasicInformation,
    MemoryState,
    VirtualQueryEx,
    VsFixedFileInfo
)
from src.os.windows.wintypes_extended import (
    HANDLE,
    QWORD,
    DWORD,
)
from src.os.windows.user32 import (
    ShowWindowCommand,
    GetWindowThreadProcessId,
    ShowWindow,
    EnumWindows,
    SetForegroundWindow,
    IsIconic
)
from src.constants.os import (
    DOS_HEADER_SIZE,
    E_LFANEW_OFFSET,
    E_LFANEW_SIZE,
    PE_HEADER_SIZE,
    PE_SIGNATURE_SIZE,
    VALID_PE_SIGNATURE,
    OPTIONAL_HEADER_OFFSET,
    OPTIONAL_HEADER_SIZE,
    SYS32,
    SYS64,
    SYS32_DATA_DIR_OFFSET,
    SYS64_DATA_DIR_OFFSET,
    DATA_DIR_SIZE,
    EXPORT_TABLE_SIZE,
    NUM_OF_FUNC_OFFSET,
    NUM_OF_FUNC_SIZE,
    NUM_OF_NAME_OFFSET,
    NUM_OF_NAME_SIZE,
    FUNC_RVA_ARRAY_RAV_OFFSET,
    FUNC_RVA_ARRAY_RAV_SIZE,
    FUNC_NAME_RVA_ARRAY_RAV_OFFSET,
    FUNC_NAME_RVA_ARRAY_RAV_SIZE,
    FUNC_ORDINAL_RVA_ARRAY_OFFSET,
    FUNC_ORDINAL_RVA_ARRAY_SIZE,
    MAX_NUM_OF_NAME,
    FUNC_NAME_SIZE,
    FUNC_ORDINAL_SIZE,
    FUNC_RVA_SIZE,
    FUNC_NAME_RAV_ARRAY_ITEM_SIZE,
)


class WindowsAPI(OperatingSystemAPIPrototype):
    _termination_callbacks: dict = {}

    def scan_file(self,
                  filepath: str,
                  pattern: list[str],
                  chunk_size: int = 1 * 1024 * 1024,
                  max_results: int = 1,
                  ) -> list[int]:
        results = []

        pattern = hex_string_to_int_list(''.join(pattern).replace(' ', ''))

        pattern_len = len(pattern)
        if not pattern_len:
            return results

        # Precompute non-wildcard positions
        non_wildcards = []
        for idx, byte in enumerate(pattern):
            if byte is not None:
                non_wildcards.append((idx, byte))

        current_address = 0
        last_matched_address = None
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(chunk_size), b''):
                chunk_length = len(chunk)
                for offset in range(chunk_length - pattern_len + 1):

                    # ignore if the offset is in the last matched function
                    if last_matched_address is not None:
                        if (current_address + offset) <= (last_matched_address + pattern_len):
                            continue

                    match = True
                    for pos, val in non_wildcards:
                        if chunk[offset + pos] != val:
                            match = False
                            break

                    if match:
                        matched_address = current_address + offset
                        last_matched_address = matched_address
                        results.append(matched_address)

                        if len(results) >= max_results:
                            break

                current_address += chunk_length
                if len(results) >= max_results:
                    break

        return results

    def scan_memory(
            self,
            h_process: int,
            pattern: list[str],
            start_address: int = None,
            end_address: int = None,
            max_results: int = 1,
            chunk_size: int = 1 * 1024 * 1024,  # 1MB chunks
    ) -> list[int]:

        pattern = hex_string_to_int_list(''.join(pattern).replace(' ', ''))
        results = []

        pattern_len = len(pattern)
        if not pattern_len:
            return results

        # Precompute non-wildcard positions
        non_wildcards = []
        for idx, byte in enumerate(pattern):
            if byte is not None:
                non_wildcards.append((idx, byte))

        mbi = MemoryBasicInformation()
        mbi_size = ctypes.sizeof(mbi)

        # Start at beginning of user space if not specified
        if start_address is None:
            start_address = 0x0  # Skip NULL page area

        # Use max user space address if not specified
        if end_address is None:
            end_address = 0x7FFFFFFFFFFFFFFF

        current_address = start_address
        last_matched_address = None

        while (current_address < end_address) and len(results) < max_results:
            try:
                # Query memory region
                ret = VirtualQueryEx(h_process, current_address, ctypes.byref(mbi), mbi_size)
                if ret == 0:
                    # End of valid memory regions
                    break
            except OSError as e:
                if e.winerror == 87:  # ERROR_INVALID_PARAMETER
                    break
                raise

            # Skip uncommitted or unreadable regions
            if mbi.State != MemoryState.MEM_COMMIT:
                continue

            is_readable = mbi.Protect in (
                PageProtection.READONLY,
                PageProtection.READWRITE,
                PageProtection.EXECUTE_READ,
                PageProtection.EXECUTE_READWRITE,
                PageProtection.WRITECOPY,
                PageProtection.EXECUTE_WRITECOPY
            )
            if not is_readable:
                continue

            # Move to next region
            region_size = mbi.RegionSize
            region_offset = 0

            read_size = min(
                chunk_size + pattern_len - 1,
                region_size - region_offset,
                end_address - current_address
            )

            while (region_offset < read_size) and len(results) < max_results:
                # Calculate chunk size with overlap for pattern

                try:
                    data = self.read_memory(h_process, current_address, read_size)
                except OSError:
                    break  # Skip inaccessible chunk
                # Search pattern in this chunk
                for offset in range(len(data) - pattern_len + 1):
                    match = True

                    address_at_this_point = current_address + offset

                    # ignore if the offset is in the last matched function
                    if last_matched_address is not None:
                        if address_at_this_point <= (last_matched_address + pattern_len):
                            continue

                    for pos, val in non_wildcards:
                        if data[offset + pos] != val:
                            match = False
                            break
                    if match:
                        last_matched_address = address_at_this_point
                        results.append(address_at_this_point)
                        if len(results) >= max_results:
                            return results

                current_address += read_size
                region_offset += read_size

        return results

    def set_process_termination_callback(self, h_process: int, callback: Callable, context: int = None) -> int:
        w_handle = HANDLE()
        flags = WT_EXECUTE_ONLY_ONCE | WT_EXECUTE_IN_WAIT_THREAD

        if context:
            context = ctypes.c_void_p(context)

        def callback_wrapper(_context: ctypes.c_void_p, _timer_fired: bool):
            callback(_context)
            self._clean_process_termination_callback(w_handle)

        callback_obj = WAIT_OR_TIMER_CALLBACK(callback_wrapper)

        if not RegisterWaitForSingleObject(
                ctypes.byref(w_handle),
                h_process,
                callback_obj,
                context,
                INFINITE,
                flags
        ):
            raise ctypes.WinError(ctypes.get_last_error())

        self._termination_callbacks[w_handle.value] = callback_obj

        return w_handle.value

    def _clean_process_termination_callback(self, w_handle: HANDLE) -> bool:
        if not kernel32.UnregisterWaitEx(
                w_handle,
                INVALID_HANDLE_VALUE  # Wait for callback to complete
        ):
            raise ctypes.WinError(ctypes.get_last_error())

        if w_handle.value in self._termination_callbacks:
            del self._termination_callbacks[w_handle.value]

        return True

    def get_pid(self, process_name: str) -> int | None:
        processes = self.list_processes()
        result = None
        for pid, proc_name in processes.items():
            if proc_name == process_name:
                result = pid
                break
        return result

    def close_h_process(self, h_process: int) -> bool:
        CloseHandle(h_process)
        return True

    def get_h_process(self, pid: int) -> int:
        h_process = OpenProcess(
            Process.QUERY_INFORMATION
            | Process.CREATE_THREAD
            | Process.VM_OPERATION
            | Process.VM_READ
            | Process.VM_WRITE
            | Process.SYNCHRONIZE,
            False,
            pid)
        if not h_process:
            raise ctypes.WinError(ctypes.get_last_error())
        return h_process

    def suspend_thread(self, thread_id: int) -> bool:
        h_thread = self.open_thread(thread_id)

        error = None

        if SuspendThread(h_thread) == -1:
            error = ctypes.get_last_error()

        CloseHandle(h_thread)

        if error:
            raise ctypes.WinError(error)

        return True

    def suspend_all_threads(self, pid: int) -> None:
        for thread_id in self.list_threads(pid):
            self.suspend_thread(thread_id)

    def resume_thread(self, thread_id: int) -> bool:
        h_thread = self.open_thread(thread_id)

        error = None

        if ResumeThread(h_thread) == -1:
            error = ctypes.get_last_error()
        CloseHandle(h_thread)
        if error:
            raise ctypes.WinError(error)
        return True

    def resume_all_threads(self, pid: int) -> bool:
        for thread_id in self.list_threads(pid):
            self.resume_thread(thread_id)
        return True

    def allocate_memory(self,
                        h_process: int,
                        size: int,
                        address: int = None,
                        protection: int = None
                        ) -> int:
        if not protection:
            protection = PageProtection.EXECUTE_READWRITE

        size = ctypes.c_size_t(size)
        allocate_addr = VirtualAllocEx(
            h_process,
            address,
            size,
            AllocationType.COMMIT | AllocationType.RESERVE,
            protection
        )
        if not allocate_addr:
            raise ctypes.WinError(ctypes.get_last_error())

        return allocate_addr

    def dealloc_memory(self,
                       h_process: int,
                       address: int,
                       size: int = 0,
                       free_type: int = None) -> bool:
        if not free_type or not size:
            free_type = FreeType.RELEASE
            size = 0

        # Convert address to proper pointer type
        address_ptr = ctypes.c_void_p(address)

        freeing = VirtualFreeEx(
            h_process,
            address_ptr,
            size,
            free_type
        )

        if not freeing:
            print('vao day', ctypes.get_last_error())
            raise ctypes.WinError(ctypes.get_last_error())
        return True

    def read_memory(self, h_process: int, address: int, size: int) -> bytes:
        buffer = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_ulong(0)
        success = ReadProcessMemory(h_process,
                                    ctypes.c_void_p(address),
                                    buffer,
                                    size,
                                    ctypes.byref(bytes_read))
        if not success:
            raise ctypes.WinError(ctypes.get_last_error())

        return buffer.raw[:bytes_read.value]

    def write_memory(self, h_process: int, address: int, data: bytes):
        bytes_written = ctypes.c_size_t(0)
        size = len(data)

        # Convert address to 64-bit pointer
        address_ptr = ctypes.c_void_p(address)
        result = WriteProcessMemory(
            h_process,
            address_ptr,
            data,
            size,
            ctypes.byref(bytes_written)
        )
        if not result:
            raise ctypes.WinError(ctypes.get_last_error())
        return True

    def terminate_process(self, h_process: int) -> bool:
        exit_code = wintypes.DWORD(0)
        terminating = TerminateProcess(h_process, exit_code)

        if not terminating:
            raise ctypes.WinError(ctypes.get_last_error())
        return True

    def list_processes(self) -> dict[int, str]:
        pe = Process32Entry()
        process_list = {}
        snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)

        if snapshot == INVALID_HANDLE_VALUE:
            raise ctypes.WinError(ctypes.get_last_error())

        # we *must* set the size of the structure prior to using it, otherwise Process32First() will fail.
        pe.dwSize = ctypes.sizeof(Process32Entry)

        found_proc = Process32First(snapshot, ctypes.byref(pe))

        while found_proc:
            process_list[int(pe.th32ProcessID)] = pe.szExeFile.decode()
            found_proc = Process32Next(snapshot, ctypes.byref(pe))

        CloseHandle(snapshot)
        return process_list

    def list_modules(self, pid: int) -> dict[str, int]:
        module_entry = ModuleEntry32()
        results = dict()
        snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, pid)

        if snapshot == INVALID_HANDLE_VALUE:
            raise ctypes.WinError(ctypes.get_last_error())

        # we *must* set the size of the structure prior to using it, otherwise Module32First() will fail.
        module_entry.dwSize = ctypes.sizeof(module_entry)

        found_module = Module32First(snapshot, ctypes.byref(module_entry))

        while found_module:
            results[module_entry.szModule.decode()] = module_entry.hModule
            found_module = Module32Next(snapshot, ctypes.byref(module_entry))

        CloseHandle(snapshot)
        return results

    def open_thread(self, thread_id: int) -> int:
        h_thread = OpenThread(THREAD_ALL_ACCESS, False, thread_id)
        if not h_thread:
            raise ctypes.WinError(ctypes.get_last_error())
        return h_thread

    def list_threads(self, pid: int) -> dict[int, ThreadContext]:
        result = dict()

        thread_entry = ThreadEntry32()
        h_snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, pid)
        if h_snapshot is not None:
            # You have to set the size of the struct or the call will fail
            thread_entry.dwSize = ctypes.sizeof(thread_entry)
            success = Thread32First(h_snapshot, ctypes.byref(thread_entry))

            while success:
                if thread_entry.th32OwnerProcessID == pid:
                    thread_id = thread_entry.th32ThreadID
                    result[thread_id] = self.get_thread_context(thread_id)
                success = Thread32Next(h_snapshot, ctypes.byref(thread_entry))

            CloseHandle(h_snapshot)
        return result

    def get_thread_context(self, thread_id: int) -> ThreadContext:
        context = ThreadContext()
        context.ContextFlags = CONTEXT_FULL | CONTEXT_DEBUG_REGISTERS

        # Obtain a handle to the thread
        h_thread = self.open_thread(thread_id)
        if not GetThreadContext(h_thread, ctypes.byref(context)):
            raise ctypes.WinError(ctypes.get_last_error())
        CloseHandle(h_thread)
        return context

    def create_thread(self,
                      h_process: int,
                      address: int,
                      params: int = None,
                      wait: bool = False,
                      ) -> tuple[int, int | None]:

        if params:
            params = ctypes.c_void_p(params)

        # Create remote thread
        thread_id = wintypes.DWORD(0)
        h_thread = CreateRemoteThread(
            h_process,
            None,
            0,
            ctypes.cast(address, LPTHREAD_START_ROUTINE),  # Convert address to function pointer
            params,
            0,
            ctypes.byref(thread_id)
        )
        if not h_thread:
            CloseHandle(h_thread)
            raise ctypes.WinError(ctypes.get_last_error())

        # Wait for thread to finish if requested
        if wait:
            # Wait with timeout (100ms)
            while True:
                wait_result = WaitForSingleObject(h_thread, 100)
                if wait_result == 0:  # WAIT_OBJECT_0
                    break
                # Check if process terminated
                process_exit_code = DWORD(0)
                if GetExitCodeProcess(h_process, ctypes.byref(process_exit_code)):
                    if process_exit_code.value != STILL_ACTIVE:
                        break

        exit_code = QWORD(0)
        GetExitCodeThread(h_thread, ctypes.byref(exit_code))

        CloseHandle(h_thread)

        return thread_id.value, exit_code.value

    def get_value_from_pointer(self,
                               h_process: int,
                               pointer: int,
                               addr_size: int = None,
                               value_size: int = None,
                               value_signed: bool = False,
                               offsets: list[int] = None,
                               ) -> int | None:
        if not value_size:
            value_size = 8
        if not addr_size:
            addr_size = 8
        try:
            if offsets:
                result = int.from_bytes(
                    self.read_memory(
                        h_process=h_process,
                        address=pointer,
                        size=addr_size
                    ),
                    byteorder='little',
                )

                for index, offset in enumerate(offsets):
                    if index + 1 == len(offsets):
                        size = value_size
                        signed = value_signed
                    else:
                        size = addr_size
                        signed = False
                    result = int.from_bytes(
                        self.read_memory(
                            h_process=h_process,
                            address=result + offset,
                            size=size
                        ),
                        byteorder='little',
                        signed=signed
                    )
            else:
                result = int.from_bytes(
                    self.read_memory(
                        h_process=h_process,
                        address=pointer,
                        size=value_size
                    ),
                    byteorder='little',
                    signed=value_signed
                )
        except OSError as e:
            # error_data: dict = {
            #     'error': e,
            #     'h_process': h_process,
            #     'pointer': hex(pointer),
            #     'addr_size': addr_size,
            #     'value_size': value_size,
            #     'value_signed': value_signed,
            #     'offsets': offsets,
            # }
            # if ENVIRONMENT != 'PRD':
            #     print('get value from pointer failed', error_data)
            return None
        return result

    def list_module_functions(self, pid: int, h_process: int, module_name: str) -> dict[str, int]:
        result = dict()

        modules = self.list_modules(pid=pid)
        module_addr = modules.get(module_name)
        if not module_addr:
            raise OSError(f'Module not found: {module_name}')

        dos_header = self.read_memory(
            h_process=h_process,
            address=module_addr,
            size=DOS_HEADER_SIZE
        )
        if not dos_header:
            raise OSError('Failed to read DOS header')

        print('dos_header', dos_header)

        e_lfanew = int.from_bytes(
            dos_header[E_LFANEW_OFFSET:E_LFANEW_OFFSET + E_LFANEW_SIZE],
            byteorder='little',
            signed=False
        )

        print('e_lfanew', e_lfanew)
        pe_header = self.read_memory(
            h_process=h_process,
            address=module_addr + e_lfanew,
            size=PE_HEADER_SIZE
        )
        if not pe_header:
            raise OSError(
                'Failed to read PE header at e_lfanew'
            )

        signature = int.from_bytes(
            pe_header[:PE_SIGNATURE_SIZE],
            byteorder='little',
            signed=False
        )
        if signature != VALID_PE_SIGNATURE:
            raise OSError(
                f'Invalid PE signature: {hex(signature)}'
            )
        opt_header = pe_header[OPTIONAL_HEADER_OFFSET: OPTIONAL_HEADER_OFFSET + OPTIONAL_HEADER_SIZE]
        sys = int.from_bytes(opt_header, byteorder='little')

        is32 = (sys == SYS32)
        is64 = (sys == SYS64)

        if not (is32 or is64):
            raise OSError(f'Not a valid PE32 or PE32+ file: {sys}')

        data_dir_offset = SYS32_DATA_DIR_OFFSET if is32 else SYS64_DATA_DIR_OFFSET
        data_dir_addr = OPTIONAL_HEADER_OFFSET + data_dir_offset
        export_rva = int.from_bytes(
            pe_header[data_dir_addr: data_dir_addr + DATA_DIR_SIZE],
            byteorder='little',
            signed=False
        )
        if not export_rva:
            raise OSError('Export RVA is 0, no export table found')

        export_table_addr = module_addr + export_rva
        export_table = self.read_memory(
            h_process=h_process,
            address=export_table_addr,
            size=EXPORT_TABLE_SIZE
        )
        if not export_table:
            raise OSError(f'Failed to read export table at: {export_table_addr}')

        num_of_funcs = int.from_bytes(
            export_table[NUM_OF_FUNC_OFFSET:NUM_OF_FUNC_OFFSET + NUM_OF_FUNC_SIZE],
            byteorder='little', signed=True
        )

        num_of_names = int.from_bytes(
            export_table[NUM_OF_NAME_OFFSET:NUM_OF_NAME_OFFSET + NUM_OF_NAME_SIZE],
            byteorder='little', signed=True
        )

        func_rav_array_rav = int.from_bytes(
            export_table[FUNC_RVA_ARRAY_RAV_OFFSET:FUNC_RVA_ARRAY_RAV_OFFSET + FUNC_RVA_ARRAY_RAV_SIZE],
            byteorder='little', signed=False
        )

        func_name_rav_array_rav = int.from_bytes(
            export_table[FUNC_NAME_RVA_ARRAY_RAV_OFFSET:FUNC_NAME_RVA_ARRAY_RAV_OFFSET + FUNC_NAME_RVA_ARRAY_RAV_SIZE],
            byteorder='little', signed=False
        )

        func_ord_array_rav = int.from_bytes(
            export_table[FUNC_ORDINAL_RVA_ARRAY_OFFSET:FUNC_ORDINAL_RVA_ARRAY_OFFSET + FUNC_ORDINAL_RVA_ARRAY_SIZE],
            byteorder='little', signed=False
        )

        if num_of_funcs < 0 or num_of_names < 0:
            raise OSError(
                'Negative function/name count. Possibly invalid data or mismatched architecture.'
            )

        func_rav_array_addr = module_addr + func_rav_array_rav
        func_name_rav_array_addr = module_addr + func_name_rav_array_rav
        print('func_name_rav_array_addr', hex(func_name_rav_array_addr))
        ord_array_addr = module_addr + func_ord_array_rav

        max_names_to_check = min(num_of_names, MAX_NUM_OF_NAME)

        for i in range(max_names_to_check):
            name_rva = self.get_value_from_pointer(
                h_process=h_process,
                pointer=func_name_rav_array_addr + (i * FUNC_NAME_RAV_ARRAY_ITEM_SIZE),
                value_size=FUNC_NAME_RAV_ARRAY_ITEM_SIZE
            )
            if not name_rva:
                continue
            print('name_rva', hex(name_rva))
            func_name = self.read_memory(
                h_process=h_process,
                address=module_addr + name_rva,
                size=FUNC_NAME_SIZE
            )
            if not func_name:
                continue

            ord_addr = ord_array_addr + (i * FUNC_ORDINAL_SIZE)
            ord_data = self.read_memory(
                h_process=h_process,
                address=ord_addr,
                size=FUNC_ORDINAL_SIZE
            )
            if not ord_data:
                raise OSError(f'Failed to read function ordinal at: {ord_addr}')

            ordinal = int.from_bytes(
                ord_data,
                byteorder='little',
            )
            func_rva_addr = func_rav_array_addr + (ordinal * FUNC_RVA_SIZE)
            func_rva = self.read_memory(
                h_process=h_process,
                address=func_rva_addr,
                size=FUNC_RVA_SIZE
            )
            if not func_rva:
                raise OSError(f'Failed to read function rav at {func_rva_addr}')

            func_rva = int.from_bytes(func_rva, byteorder='little')
            result[func_name] = module_addr + func_rva

        return result

    def get_file_version(self, filepath: str) -> str:
        # Get size of version info
        size = ctypes.windll.version.GetFileVersionInfoSizeW(filepath, None)
        if not size:
            return None

        # Allocate buffer and get version info
        buffer = (ctypes.c_char * size)()
        if not ctypes.windll.version.GetFileVersionInfoW(filepath, 0, size, buffer):
            return None

        # Query fixed file info
        pvi = ctypes.c_void_p()
        uvi = wintypes.UINT()
        if not ctypes.windll.version.VerQueryValueW(buffer, '\\', ctypes.byref(pvi), ctypes.byref(uvi)):
            return None

        # Cast to VS_FIXEDFILEINFO structure
        fixed_info = ctypes.cast(pvi, ctypes.POINTER(VsFixedFileInfo)).contents

        versions = (
            (fixed_info.dwFileVersionMS >> 16) & 0xFFFF,  # Major
            (fixed_info.dwFileVersionMS >> 0) & 0xFFFF,  # Minor
            (fixed_info.dwFileVersionLS >> 16) & 0xFFFF,  # Build
            (fixed_info.dwFileVersionLS >> 0) & 0xFFFF  # Revision
        )

        return f'{versions[0]}.{versions[1]}.{versions[2]}.{versions[3]}'

    def _find_window_handles(self, pid: int) -> list[int]:
        results = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def enum_proc(_h_window, _):
            # Get PID for this window
            w_pid = wintypes.DWORD()
            GetWindowThreadProcessId(_h_window, ctypes.byref(w_pid))

            if w_pid.value == pid:
                results.append(_h_window)
            return True  # Continue enumeration

        EnumWindows(enum_proc, 0)

        return results

    def toggle_window_visibility(self, pid: int, visible: bool = False, focus: bool = False) -> bool:
        window_handles = self._find_window_handles(pid)

        if not window_handles:
            raise OSError(f'Failed to find windows for pid: {pid}')

        command = ShowWindowCommand.SHOW if visible else ShowWindowCommand.HIDE
        for index, h_window in enumerate(window_handles):
            ShowWindow(h_window, command)

            # Set foreground for the first window
            if visible and focus:
                # Restore window if minimized
                if IsIconic(h_window):
                    ShowWindow(h_window, ShowWindowCommand.RESTORE)

                # Unlock focus with Alt
                windll.user32.keybd_event(0x12, 0, 0, 0)
                windll.user32.keybd_event(0x12, 0, 0x0002, 0)

                if not SetForegroundWindow(h_window):
                    print('SetForegroundWindow failed', print(ctypes.get_last_error()))

        return True
