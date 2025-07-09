from pydantic import Field

from src.bases.models import BaseModel
from src.bases.os import OperatingSystemAPIPrototype
from src.constants.type_parsers.csharp import *


class CSharpDictEntry(BaseModel):
    hash_code: int
    next_index: int
    value: int
    key: int


class CSharpDict(BaseModel):
    entries: list[CSharpDictEntry] = Field(default_factory=list)
    count: int = 0


class CSharpList(BaseModel):
    items: list[int] = Field(default_factory=list)


class CSharpTypeParser(BaseModel):
    os_api: OperatingSystemAPIPrototype
    pid: int
    h_process: int

    def parse_list(self,
                   address: int,
                   keep_none: bool = False,
                   ) -> CSharpList:
        count = self.os_api.get_value_from_pointer(
            h_process=self.h_process,
            pointer=address + LIST_COUNT_OFFSET,
            value_size=LIST_COUNT_LENGTH
        )
        if not count:
            return CSharpList(items=[])

        items_as_bytes = self.os_api.read_memory(
            h_process=self.h_process,
            address=address + LIST_FIRST_ITEM_OFFSET,
            size=count * 8
        )

        items = []

        for i in range(count):
            item_addr = int.from_bytes(
                items_as_bytes[i * 8: (i + 1) * 8],
                byteorder='little'
            )
            if not item_addr and not keep_none:
                continue

            items.append(item_addr)

        return CSharpList(items=items)

    def parse_generic_list(self,
                           address: int,
                           keep_none: bool = False,
                           ) -> CSharpList:
        item_list_addr = self.os_api.get_value_from_pointer(
            h_process=self.h_process,
            pointer=address + GENERIC_LIST_ITEM_LIST_OFFSET,
        )
        return self.parse_list(item_list_addr, keep_none=keep_none)

    def parse_generic_dict(self, address: int, is_32bit: bool = False) -> CSharpDict:
        # https://referencesource.microsoft.com/#mscorlib/system/collections/generic/dictionary.cs,6d8e35702d74cf71
        header_size = GENERIC_DICT_32BIT_HEADER_LENGTH if is_32bit else GENERIC_DICT_64BIT_HEADER_LENGTH
        count_offset = header_size + GENERIC_DICT_BUCKET_ADDR_LENGTH + GENERIC_DICT_ENTRY_LIST_ADDR_LENGTH

        count = self.os_api.get_value_from_pointer(
            h_process=self.h_process,
            pointer=address + count_offset,
            value_size=GENERIC_DICT_COUNT_LENGTH
        )

        entry_list_offset = header_size + GENERIC_DICT_BUCKET_ADDR_LENGTH
        entry_list_addr = self.os_api.get_value_from_pointer(
            h_process=self.h_process,
            pointer=address + entry_list_offset,
        )

        byte_entries = self.os_api.read_memory(
            h_process=self.h_process,
            address=entry_list_addr + GENERIC_DICT_ENTRY_LIST_FIRST_ITEM_OFFSET,
            size=GENERIC_DICT_ENTRY_LENGTH * count
        )

        entries = []

        entry_hash_code_size = 4
        entry_next_index_size = 4
        entry_value_size = 8
        entry_key_size = 8

        for i in range(count):
            byte_entry = byte_entries[i * GENERIC_DICT_ENTRY_LENGTH:(i + 1) * GENERIC_DICT_ENTRY_LENGTH]
            hash_code_offset = 0
            hash_code = byte_entry[hash_code_offset:(hash_code_offset + entry_hash_code_size)]
            next_index_offset = hash_code_offset + entry_hash_code_size
            next_index = byte_entry[next_index_offset:(next_index_offset + entry_next_index_size)]
            key_offset = next_index_offset + entry_next_index_size
            key = byte_entry[key_offset:(key_offset + entry_key_size)]
            value_offset = key_offset + entry_key_size
            value = byte_entry[value_offset: (value_offset + entry_value_size)]

            entries.append(CSharpDictEntry(
                key=int.from_bytes(key, 'little'),
                value=int.from_bytes(value, 'little'),
                hash_code=int.from_bytes(hash_code, 'little'),
                next_index=int.from_bytes(next_index, 'little'),
            ))

        return CSharpDict(
            entries=entries,
            count=count
        )

    def parse_string(self, address: int, is_32bit: bool = False) -> str:
        if not address:
            return ''

        # Skip object header (8 bytes for 32-bit, 16 bytes for 64-bit)
        header_size = STRING_32BIT_HEADER_LENGTH if is_32bit else STRING_64BIT_HEADER_LENGTH

        char_count = self.os_api.get_value_from_pointer(
            h_process=self.h_process,
            pointer=address + header_size,
            value_size=STRING_CHAR_COUNT_LENGTH
        )
        if not char_count:
            return ''
        try:
            string_as_bytes = self.os_api.read_memory(
                h_process=self.h_process,
                address=address + header_size + STRING_CHAR_COUNT_LENGTH,
                size=char_count * 2  # 2 bytes for every character
            )
        except OSError:
            return ''

        # Decode to Python string (UTF-16 little-endian)
        return string_as_bytes.decode('utf-16-le')
