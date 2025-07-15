import datetime
import sys
import traceback
import zlib
import math
import heapq
import json
from tempfile import TemporaryFile
from logging import getLogger
from cryptography.fernet import Fernet
from keystone import Ks, KS_ARCH_X86, KS_MODE_32, KS_MODE_64
from capstone import Cs, CS_ARCH_X86, CS_MODE_32, CS_MODE_64, CsInsn
from typing import Iterable

from config import SECRET_KEY

from .logging import setup_logging

setup_logging()
logger = getLogger(__name__)


def get_now(local: bool = False) -> datetime.datetime:
    result = datetime.datetime.now(tz=datetime.timezone.utc)
    if local:
        result = result.astimezone()
    return result


def get_local_timezone() -> datetime.timezone:
    return datetime.datetime.now(tz=datetime.timezone.utc).astimezone().tzinfo


def bytes_to_assembly(data: bytes, offset: int = 0, bits: int = 64) -> Iterable[CsInsn]:
    if bits == 64:
        cs_mode = CS_MODE_64
    else:
        cs_mode = CS_MODE_32

    cs = Cs(CS_ARCH_X86, cs_mode)

    return cs.disasm(data, offset)


def assembly_to_bytes(asm_code: str, address: int = None, bits: int = 64) -> bytes:
    if bits == 64:
        ks_mode = KS_MODE_64
    else:
        ks_mode = KS_MODE_32

    ks = Ks(KS_ARCH_X86, ks_mode)
    if address is None:
        address = 0

    result, count = ks.asm(asm_code, addr=address)

    return bytes(result)


def assembly_to_hex(asm_code: str, bits: int = 64) -> str:
    result = assembly_to_bytes(asm_code=asm_code, bits=bits)
    # Convert to hex string
    result = ''.join(f'{x:02x}' for x in result)
    return result


def str_to_bytes(string: str, wstr: bool = True) -> bytes:
    if wstr:
        result = string.encode('utf-16le') + b'\x00\x00'
    else:
        result = string.encode('utf-8') + b'\x00'
    return result


def capture_error(error: Exception, object_name: str = None) -> None:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    if object_name:
        logger.error(f'{object_name} failed: {error} - {tb_str}')
    else:
        logger.error(f'Error: {error} - {tb_str}')


def hex_string_to_int_list(hex_str: str) -> list[int | None]:
    hex_str = hex_str.strip().replace(' ', '')
    int_list = []
    i = 0
    n = len(hex_str)

    while i < n:
        if i + 1 < n and hex_str[i] == '?' and hex_str[i + 1] == '?':
            int_list.append(None)  # Wildcard byte
            i += 2
        else:
            # Extract next two characters (assuming valid hex)
            if i + 1 >= n:
                raise ValueError(f"Invalid hex string (odd length or incomplete byte at position {i})")

            byte_str = hex_str[i] + hex_str[i + 1]
            if all(c in '0123456789ABCDEFabcdef' for c in byte_str):
                int_list.append(int(byte_str, 16))  # Convert to integer
            else:
                raise ValueError(f"Invalid hex byte '{byte_str}' at position {i}")
            i += 2

    return int_list


def decompress_data(data: bytes, encryption_key: str = None) -> bytes:
    if encryption_key:
        cipher_suite = Fernet(encryption_key)
        data = cipher_suite.decrypt(data)

    decompressed_data = zlib.decompress(data)

    return decompressed_data


def compress_data(data: bytes, encryption_key: str = None) -> bytes:
    compressed_data = zlib.compress(data)

    if encryption_key:
        cipher_suite = Fernet(encryption_key)
        compressed_data = cipher_suite.encrypt(compressed_data)

    return compressed_data


def calculate_distance(point_1: tuple[int, int], point_2: tuple[int, int]) -> float:
    x1, y1 = point_1
    x2, y2 = point_2

    dx = x2 - x1
    dy = y2 - y1

    return math.sqrt(dx * dx + dy * dy)


def calculate_point_distribution(
        free_points: int,
        current_stats: dict[str, int],
        needed_stats: dict[str, int]) -> dict[str, int]:
    # Calculate remaining needs for each stat
    remaining_needs = {
        stat: max(0, needed_stats[stat] - current_stats[stat])
        for stat in needed_stats
    }

    total_need = sum(remaining_needs.values())

    # If no need or no points, return zeros
    if total_need == 0 or free_points == 0:
        return {stat: 0 for stat in needed_stats}

    # Calculate distribution based on ratios
    distribution = {stat: 0 for stat in needed_stats}

    stats: list[tuple[str, int]] = []

    for stat, value in remaining_needs.items():
        if not value:
            continue
        stats.append((stat, value))

    # add to the lowest demand first
    stats = sorted(stats, key=lambda i: i[1])

    avg_allocating = round(free_points / len(stats))

    remaining_points = free_points
    for stat, _ in stats:
        ratio = remaining_needs[stat] / total_need
        if remaining_needs[stat] < avg_allocating:
            allocating = remaining_needs[stat]
        else:
            allocating = round(min(ratio * free_points, remaining_points))

        allocating = max(10, allocating)

        distribution[stat] = allocating
        remaining_points -= allocating
        if remaining_points <= 0:
            break

    return distribution


def scan_string(
        data: str,
        pattern: str,
        case_sensitive: bool = False,
        max_results: int = 1
) -> list[int]:
    data = data.strip()
    pattern = pattern.strip()

    if not case_sensitive:
        data = data.lower()
        pattern = pattern.lower()

    results = []

    pattern_len = len(pattern)
    if not pattern_len:
        return results

    # Precompute non-wildcard positions
    non_wildcards = []
    for idx, char in enumerate(pattern):
        if char != '?':
            non_wildcards.append((idx, char))

    last_matched_addr = None

    for addr in range(len(data) - pattern_len + 1):
        match = True

        # ignore if the offset is in the last matched function
        if last_matched_addr is not None:
            if addr <= (last_matched_addr + pattern_len):
                continue

        for pos, val in non_wildcards:
            if data[addr + pos] != val:
                match = False
                break

        if match:
            last_matched_addr = addr
            results.append(addr)
            if len(results) >= max_results:
                return results

    return results


def heuristic(a: tuple[int, int], b: tuple[int, int], directional_movements: int = 4) -> int:
    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])

    if directional_movements not in [4, 8]:
        raise Exception('directional_movements must be 4 or 8')

    if directional_movements == 4:
        return dx + dy

    return 1000 * (dx + dy) - 586 * min(dx, dy)


def find_path(
        grid: list[list[bool]],
        start: tuple[int, int],
        goal: tuple[int, int],
        map_size: int,
        directional_movements: int = 8) -> list[tuple[int, int]]:
    if not (0 <= start[0] < map_size
            and 0 <= start[1] < map_size
            and 0 <= goal[0] < map_size
            and 0 <= goal[1] < map_size):
        return []

    if not grid[start[0]][start[1]] or not grid[goal[0]][goal[1]]:
        return []

    if start == goal:
        return [start]

    if directional_movements not in [4, 8]:
        raise ValueError("Movement must be 4 or 8")

    straight_move_cost = 1000
    diagonal_move_cost = 1414

    directions = [(0, 1, straight_move_cost), (0, -1, straight_move_cost),
                  (1, 0, straight_move_cost), (-1, 0, straight_move_cost)]
    if directional_movements == 8:
        directions.extend([
            (1, 1, diagonal_move_cost), (1, -1, diagonal_move_cost),
            (-1, 1, diagonal_move_cost), (-1, -1, diagonal_move_cost)
        ])
    # Minimum cost to reach each node
    g_score = [[10 ** 9] * map_size for _ in range(map_size)]
    # Parent node for path reconstruction
    parent = [[None] * map_size for _ in range(map_size)]

    start_x, start_y = start
    g_score[start_x][start_y] = 0
    f_start = heuristic(start, goal, directional_movements)
    open_set = []
    heapq.heappush(open_set, (f_start, 0, start_x, start_y))

    while open_set:
        f_val, g_val, x, y = heapq.heappop(open_set)
        if g_val != g_score[x][y]:
            continue

        if (x, y) == goal:
            path = []
            current = (x, y)

            while current != start:
                path.append(current)
                px, py = parent[current[0]][current[1]]
                current = (px, py)

            path.append(start)
            path.reverse()

            return path

        for dx, dy, cost in directions:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < map_size and 0 <= ny < map_size):
                continue
            if not grid[nx][ny]:
                continue

            new_g = g_val + cost
            if new_g < g_score[nx][ny]:
                g_score[nx][ny] = new_g
                f_new = new_g + heuristic((nx, ny), goal, directional_movements)
                heapq.heappush(open_set, (f_new, new_g, nx, ny))
                parent[nx][ny] = (x, y)

    return []


def load_data_file(filepath: str) -> dict | list:
    if filepath.endswith('.json'):
        with open(filepath, 'rb') as rf:
            data = decompress_data(
                rf.read(),
                encryption_key=SECRET_KEY,
            )
        return json.loads(data)

    result = []

    tmp_file = TemporaryFile('wb+')
    with open(filepath, 'rb') as rf:
        tmp_file.write(decompress_data(
            rf.read(),
            encryption_key=SECRET_KEY,
        ))
        tmp_file.seek(0)
        for line in tmp_file:
            if not line:
                continue
            result.append(json.loads(line))
    tmp_file.close()
    return result


