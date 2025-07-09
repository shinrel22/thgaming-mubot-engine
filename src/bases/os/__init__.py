from typing import Callable

from src.bases.models import BaseModel


class OperatingSystemAPIPrototype(BaseModel):

    def toggle_window_visibility(self, pid: int, visible: bool = False, focus: bool = False) -> bool:
        raise NotImplementedError

    def get_file_version(self, filepath: str) -> str:
        raise NotImplementedError

    def scan_file(self, filepath: str,
                  pattern: list[str],
                  chunk_size: int = 1 * 1024 * 1024,
                  max_results: int = 1
                  ) -> list[int]:
        raise NotImplementedError

    def scan_memory(
            self,
            h_process: int,
            pattern: str,
            start_address: int = None,
            end_address: int = None,
            max_results: int = 1,
            chunk_size: int = 1024 * 1024,  # 1MB chunks
    ) -> list[int]:
        raise NotImplementedError

    def set_process_termination_callback(self, h_process: int, callback: Callable, context: int = None) -> int:
        raise NotImplementedError

    def close_h_process(self, h_process: int) -> bool:
        raise NotImplementedError

    def get_h_process(self, pid: int) -> int:
        raise NotImplementedError

    def get_pid(self, process_name: str) -> int:
        raise NotImplementedError

    def suspend_thread(self, thread_id: int) -> bool:
        raise NotImplementedError

    def suspend_all_threads(self, pid: int) -> None:
        raise NotImplementedError

    def resume_thread(self, thread_id: int) -> bool:
        raise NotImplementedError

    def resume_all_threads(self, pid: int) -> bool:
        raise NotImplementedError

    def allocate_memory(self,
                        h_process: int,
                        size: int,
                        address: int = None,
                        protection: int = None
                        ) -> int:
        raise NotImplementedError

    def dealloc_memory(self,
                       h_process: int,
                       address: int,
                       size: int = 0,
                       free_type=None) -> bool:
        raise NotImplementedError

    def read_memory(self, h_process: int, address: int, size: int, ) -> bytes:
        raise NotImplementedError

    def write_memory(self, h_process: int, address: int, data: bytes) -> bool:
        raise NotImplementedError

    def terminate_process(self, h_process: int) -> bool:
        raise NotImplementedError

    def list_processes(self) -> dict[int, str]:
        raise NotImplementedError

    def list_modules(self, pid: int) -> dict[str, int]:
        raise NotImplementedError

    def open_thread(self, thread_id: int) -> int:
        raise NotImplementedError

    def list_threads(self, pid: int) -> dict:
        raise NotImplementedError

    def get_thread_context(self, thread_id: int) -> any:
        raise NotImplementedError

    def create_thread(self,
                      address: int,
                      h_process: int,
                      params: int = None,
                      wait: bool = False,
                      ) -> tuple[int, int | None]:
        raise NotImplementedError

    def get_value_from_pointer(self,
                               h_process: int,
                               pointer: int,
                               addr_size: int = None,
                               value_size: int = None,
                               value_signed: bool = False,
                               offsets: list[int] = None,
                               ) -> int | None:
        raise NotImplementedError
