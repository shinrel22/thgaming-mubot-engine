import enum

from src.os.windows.wintypes_extended import *
from src.os.windows.winapi_error import *


INVALID_HANDLE_VALUE = ctypes.c_void_p(-1)
INFINITE = ctypes.c_uint(-1)
STILL_ACTIVE = 0x103

# Context flags for GetThreadContext()
CONTEXT_FULL = 0x00010007
CONTEXT_DEBUG_REGISTERS = 0x00010010

# Thread constants for CreateToolhelp32Snapshot()
TH32CS_SNAPHEAPLIST = 0x00000001
TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPTHREAD = 0x00000004
TH32CS_SNAPMODULE = 0x00000008
TH32CS_INHERIT = 0x80000000
TH32CS_SNAPALL = (TH32CS_SNAPHEAPLIST | TH32CS_SNAPPROCESS | TH32CS_SNAPTHREAD | TH32CS_SNAPMODULE)
THREAD_ALL_ACCESS = 0x001F03FF
THREAD_CREATE_SUSPENDED = 0x4

SYNCHRONIZE = 0x00100000
WT_EXECUTE_ONLY_ONCE = 0x00000008
WT_EXECUTE_IN_WAIT_THREAD = 0x00000004
ERROR_IO_PENDING = 997


class VsFixedFileInfo(ctypes.Structure):
    _fields_ = [
        ('dwSignature', DWORD),
        ('dwStrucVersion', DWORD),
        ('dwFileVersionMS', DWORD),
        ('dwFileVersionLS', DWORD),
    ]


class SecurityAttributes(ctypes.Structure):
    _fields_ = [
        ("nLength", DWORD),
        ("lpSecurityDescriptor", LPVOID),
        ("bInheritHandle", BOOL),
    ]


LPSECURITY_ATTRIBUTES = ctypes.POINTER(SecurityAttributes)


class Process32Entry(ctypes.Structure):
    _fields_ = [
        ("dwSize", DWORD),
        ("cntUsage", DWORD),
        ("th32ProcessID", DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", DWORD),
        ("cntThreads", DWORD),
        ("th32ParentProcessID", DWORD),
        ("pcPriClassBase", LONG),
        ("dwFlags", DWORD),
        ("szExeFile", CHAR * MAX_PATH),
    ]


LPPROCESSENTRY32 = ctypes.POINTER(Process32Entry)


class Process(enum.IntFlag):
    CREATE_PROCESS = 0x0080
    CREATE_THREAD = 0x0002
    DUP_HANDLE = 0x0002
    QUERY_INFORMATION = 0x0400
    QUERY_LIMITED_INFORMATION = 0x1000
    SET_INFORMATION = 0x0200
    SET_QUOTA = 0x0100
    SUSPEND_RESUME = 0x0800
    TERMINATE = 0x0001
    VM_OPERATION = 0x0008
    VM_READ = 0x0010
    VM_WRITE = 0x0020
    SYNCHRONIZE = 0x00100000


class AllocationType(enum.IntFlag):
    COMMIT = 0x00001000
    RESERVE = 0x00002000
    RESET = 0x00080000
    RESET_UNDO = 0x1000000
    LARGE_PAGES = 0x20000000
    PHYSICAL = 0x00400000
    TOP_DOWN = 0x00100000


class FreeType(enum.IntFlag):
    COALESCE_PLACEHOLDERS = 0x1
    PRESERVE_PLACEHOLDER = 0x2
    DECOMMIT = 0x4000
    RELEASE = 0x8000


class PageProtection(enum.IntFlag):
    EXECUTE = 0x10
    EXECUTE_READ = 0x20
    EXECUTE_READWRITE = 0x40
    EXECUTE_WRITECOPY = 0x80
    NOACCESS = 0x01
    READONLY = 0x02
    READWRITE = 0x04
    WRITECOPY = 0x08
    TARGETS_INVALID = 0x40000000
    TARGETS_NO_UPDATE = 0x40000000
    GUARD = 0x100
    NOCACHE = 0x200
    WRITECOMBINE = 0x400
    # LoadEnclaveData
    # ENCLAVE_THREAD_CONTROL
    # ENCLDAVE_UNVALIDATED


class SnapshotInclude(enum.IntFlag):
    INHERIT = 0x80000000
    HEAPLIST = 0x00000001
    MODULE = 0x00000008
    MODULE32 = 0x00000010
    PROCESS = 0x00000002
    THREAD = 0x00000004
    ALL = HEAPLIST | MODULE | PROCESS | THREAD


class Wait(enum.IntEnum):
    ABANDONED = 0x00000080
    OBJECT_0 = 0x00000000
    TIMEOUT = 0x00000102
    FAILED = 0xFFFFFFFF


class FloatingSaveArea(ctypes.Structure):
    _fields_ = [

        ("ControlWord", DWORD),
        ("StatusWord", DWORD),
        ("TagWord", DWORD),
        ("ErrorOffset", DWORD),
        ("ErrorSelector", DWORD),
        ("DataOffset", DWORD),
        ("DataSelector", DWORD),
        ("RegisterArea", BYTE * 80),
        ("Cr0NpxState", DWORD),
    ]


class MemoryBasicInformation(ctypes.Structure):
    _fields_ = [
        ('BaseAddress', LPVOID),
        ('AllocationBase', LPVOID),
        ('AllocationProtect', DWORD),
        ('PartitionId', WORD),
        ('RegionSize', SIZE_T),
        ('State', DWORD),
        ('Protect', DWORD),
        ('Type', DWORD),
    ]


class MemoryState(enum.IntFlag):
    MEM_COMMIT = 0x1000
    MEM_FREE = 0x10000
    MEM_RESERVE = 0x2000


# The CONTEXT structure which holds all of the register values after a GetThreadContext() call
class ThreadContext(ctypes.Structure):
    _fields_ = [
        ("P1Home", QWORD),
        ("P2Home", QWORD),
        ("P3Home", QWORD),
        ("P4Home", QWORD),
        ("P5Home", QWORD),
        ("P6Home", QWORD),
        ("MxCsr", DWORD),
        ("SegCs", WORD),
        ("SegDs", WORD),
        ("SegEs", WORD),
        ("SegFs", WORD),
        ("SegGs", WORD),
        ("SegSs", WORD),
        ("EFlags", DWORD),
        ("Dr0", QWORD),
        ("Dr1", QWORD),
        ("Dr2", QWORD),
        ("Dr3", QWORD),
        ("Dr6", QWORD),
        ("Dr7", QWORD),
        ("Rax", QWORD),
        ("Rcx", QWORD),
        ("Rdx", QWORD),
        ("Rbx", QWORD),
        ("Rsp", QWORD),
        ("Rbp", QWORD),
        ("Rsi", QWORD),
        ("Rdi", QWORD),
        ("R8", QWORD),
        ("R9", QWORD),
        ("R10", QWORD),
        ("R11", QWORD),
        ("R12", QWORD),
        ("R13", QWORD),
        ("R14", QWORD),
        ("R15", QWORD),
        ("Rip", QWORD),
        ("FloatSave", FloatingSaveArea),
        ("ExtendedRegisters", BYTE * 512),
        ("ContextFlags", DWORD),

    ]

class ThreadEntry32(ctypes.Structure):
    _fields_ = [
        ("dwSize", DWORD),
        ("cntUsage", DWORD),
        ("th32ThreadID", DWORD),
        ("th32OwnerProcessID", DWORD),
        ("tpBasePri", DWORD),
        ("tpDeltaPri", DWORD),
        ("dwFlags", DWORD),
    ]


class ModuleEntry32(ctypes.Structure):
    _fields_ = [
        ("dwSize", DWORD),
        ("th32ModuleID", DWORD),
        ("th32ProcessID", DWORD),
        ("GlblcntUsage", DWORD),
        ("ProccntUsage", DWORD),
        ("modBaseAddr", ctypes.POINTER(BYTE)),
        ("modBaseSize", DWORD),
        ("hModule", HMODULE),
        ("szModule", CHAR * 256),
        ("szExePath", CHAR * 260),
    ]


def CreateToolhelp32Snapshot_errcheck(result, func, args):
    if result == INVALID_HANDLE_VALUE:
        raise ctypes.WinError()
    return result


VirtualAllocEx = ctypes.windll.kernel32.VirtualAllocEx
VirtualAllocEx.argtypes = [HANDLE, LPVOID, SIZE_T, DWORD, DWORD]
VirtualAllocEx.restype = LPVOID
VirtualAllocEx.errcheck = LPVOID_errcheck

VirtualFreeEx = ctypes.windll.kernel32.VirtualFreeEx
VirtualFreeEx.argtypes = [HANDLE, LPVOID, SIZE_T, DWORD]
VirtualFreeEx.restype = BOOL
VirtualFreeEx.errcheck = Win32API_errcheck

WriteProcessMemory = ctypes.windll.kernel32.WriteProcessMemory
WriteProcessMemory.argtypes = [HANDLE, LPVOID, LPCVOID, SIZE_T, ctypes.POINTER(SIZE_T)]
WriteProcessMemory.restype = BOOL
WriteProcessMemory.errcheck = Win32API_errcheck

ReadProcessMemory = ctypes.windll.kernel32.ReadProcessMemory
TerminateProcess = ctypes.windll.kernel32.TerminateProcess
SuspendThread = ctypes.windll.kernel32.SuspendThread
ResumeThread = ctypes.windll.kernel32.ResumeThread

GetProcAddress = ctypes.windll.kernel32.GetProcAddress
GetProcAddress.argtypes = [HMODULE, LPCSTR]
GetProcAddress.restype = FARPROC

OpenProcess = ctypes.windll.kernel32.OpenProcess
OpenProcess.argtypes = [QWORD, BOOL, QWORD]
OpenProcess.restype = HANDLE
OpenProcess.errcheck = LPVOID_errcheck

GetModuleHandleA = ctypes.windll.kernel32.GetModuleHandleA
GetModuleHandleA.argtypes = [LPCSTR]
GetModuleHandleA.restype = HMODULE
GetModuleHandleA.errcheck = LPVOID_errcheck

CreateToolhelp32Snapshot = ctypes.windll.kernel32.CreateToolhelp32Snapshot
CreateToolhelp32Snapshot.argtypes = [DWORD, DWORD]
CreateToolhelp32Snapshot.restype = HANDLE
CreateToolhelp32Snapshot.errcheck = CreateToolhelp32Snapshot_errcheck

Process32First = ctypes.windll.kernel32.Process32First
Process32First.argtypes = [HANDLE, LPPROCESSENTRY32]
Process32First.restype = BOOL

Process32Next = ctypes.windll.kernel32.Process32Next
Process32Next.argtypes = [HANDLE, LPPROCESSENTRY32]
Process32Next.restype = BOOL

GetThreadContext = ctypes.windll.kernel32.GetThreadContext
GetThreadContext.restype = BOOL
GetThreadContext.errcheck = Win32API_errcheck

Thread32First = ctypes.windll.kernel32.Thread32First
Thread32Next = ctypes.windll.kernel32.Thread32Next

Module32First = ctypes.windll.kernel32.Module32First
Module32First.argtypes = [HANDLE, ctypes.POINTER(ModuleEntry32)]
Module32Next = ctypes.windll.kernel32.Module32Next
OpenThread = ctypes.windll.kernel32.OpenThread

CloseHandle = ctypes.windll.kernel32.CloseHandle
CloseHandle.argtypes = [HANDLE]
CloseHandle.restype = BOOL
CloseHandle.errcheck = Win32API_errcheck

CreateRemoteThread = ctypes.windll.kernel32.CreateRemoteThread
CreateRemoteThread.argtypes = [
    HANDLE,
    LPSECURITY_ATTRIBUTES,
    SIZE_T,
    LPTHREAD_START_ROUTINE,
    LPVOID,
    DWORD,
    LPDWORD,
]
CreateRemoteThread.restype = HANDLE
CreateRemoteThread.errcheck = LPVOID_errcheck

WaitForSingleObject = ctypes.windll.kernel32.WaitForSingleObject
WaitForSingleObject.argtypes = [HANDLE, DWORD]
WaitForSingleObject.restype = DWORD

GetExitCodeThread = ctypes.windll.kernel32.GetExitCodeThread
GetExitCodeThread.argtypes = [HANDLE, LPQWORD]
GetExitCodeThread.restype = BOOL
GetExitCodeThread.errcheck = Win32API_errcheck

IsWow64Process2 = ctypes.windll.kernel32.IsWow64Process2
IsWow64Process2.argtypes = [HANDLE, ctypes.POINTER(USHORT), ctypes.POINTER(USHORT)]
IsWow64Process2.restype = BOOL
IsWow64Process2.errcheck = Win32API_errcheck

GetCurrentProcess = ctypes.windll.kernel32.GetCurrentProcess
GetCurrentProcess.argtypes = None
GetCurrentProcess.restype = HANDLE

QueryFullProcessImageNameA = ctypes.windll.kernel32.QueryFullProcessImageNameA
QueryFullProcessImageNameA.argtypes = [HANDLE, DWORD, LPSTR, PDWORD]
QueryFullProcessImageNameA.restype = BOOL
QueryFullProcessImageNameA.errcheck = Win32API_errcheck


RegisterWaitForSingleObject = ctypes.windll.kernel32.RegisterWaitForSingleObject
RegisterWaitForSingleObject.argtypes = [
    ctypes.POINTER(HANDLE),  # phNewWaitObject
    HANDLE,                  # hObject
    ctypes.c_void_p,                  # Callback function pointer
    ctypes.c_void_p,                  # Context
    ULONG,                   # dwMilliseconds
    ULONG                    # dwFlags
]
RegisterWaitForSingleObject.restype = BOOL

UnregisterWaitEx = ctypes.windll.kernel32.UnregisterWaitEx
UnregisterWaitEx.argtypes = [HANDLE, HANDLE]
UnregisterWaitEx.restype = BOOL

# Callback function type
WAIT_OR_TIMER_CALLBACK = ctypes.WINFUNCTYPE(
    None,
    ctypes.c_void_p,   # lpParameter (context)
    BOOL      # TimerOrWaitFired
)

# Add function prototype
GetExitCodeProcess = ctypes.windll.kernel32.GetExitCodeProcess
GetExitCodeProcess.argtypes = [HANDLE, LPDWORD]
GetExitCodeProcess.restype = BOOL

VirtualQueryEx = ctypes.windll.kernel32.VirtualQueryEx
VirtualQueryEx.argtypes = [HANDLE, LPCVOID, ctypes.POINTER(MemoryBasicInformation), SIZE_T]
VirtualQueryEx.restype = SIZE_T
VirtualQueryEx.errcheck = VirtualQueryEx_errcheck
