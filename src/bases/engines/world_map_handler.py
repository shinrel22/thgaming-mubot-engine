import os

from src.bases.engines.data_models import WorldCell, Coord
from src.constants import DATA_DIR
from src.utils import find_path, load_data_file

from .prototypes import WorldMapHandlerPrototype


class WorldMapHandler(WorldMapHandlerPrototype):
    def _make_filepath(self, world_id: int):
        return os.path.join(
            DATA_DIR,
            self.engine.game_server.code,
            'world_cells',
            f'{world_id}.jsonl'
        )

    def crop(self,
             world_id: int,
             center: tuple[int, int],
             bounding_box: tuple[int, int, int, int] = None
             ) -> dict[str, WorldCell]:

        if not bounding_box:
            bounding_box = (15, 15, 15, 15)

        left, top, right, bottom = bounding_box

        filepath = self._make_filepath(world_id)

        result = dict()

        if not os.path.exists(filepath):
            return result

        lines_to_read: list[int] = []
        line_mappings: dict[int, tuple[int, int]] = {}

        center_x, center_y = center

        min_dx = -left
        max_dx = right
        min_dy = -bottom
        max_dy = top

        for dx in range(min_dx, max_dx):
            for dy in range(min_dy, max_dy):
                if dx <= 0:
                    rx = dx + abs(min_dx)
                else:
                    rx = dx + abs(max_dx)

                if dy <= 0:
                    ry = dy + abs(min_dy)
                else:
                    ry = dy + abs(max_dy)

                world_x = center_x + dx
                world_y = center_y + dy

                if 0 <= world_x < self.max_map_size and 0 <= world_y < self.max_map_size:
                    line_number = world_x * self.max_map_size + world_y
                    line_mappings[line_number] = (rx, ry)
                    lines_to_read.append(line_number)

                else:
                    cell = WorldCell(
                        coord=Coord(x=rx, y=ry),
                        walkable=False,
                        is_safezone=False,
                    )
                    result[cell.coord.code] = cell


        for index, line in enumerate(load_data_file(filepath)):
            if index > lines_to_read[-1]:
                break
            if index not in lines_to_read:
                continue
            cell = WorldCell(**line)
            rx, ry = line_mappings[index]
            r_cell = WorldCell(
                coord=Coord(x=rx, y=ry),
                walkable=cell.walkable,
                is_safezone=cell.is_safezone,
            )
            result[r_cell.coord.code] = r_cell

        return result

    def load_world_cells(self,
                         world_id: int,
                         ) -> dict[str, WorldCell]:

        filepath = self._make_filepath(world_id)

        result = dict()
        if not os.path.exists(filepath):
            return result

        for line in load_data_file(filepath):
            cell = WorldCell(**line)
            result[cell.coord.code] = cell

        return result

    def find_path(
            self,
            cells: dict[str, WorldCell],
            start: tuple[int, int],
            goal: tuple[int, int],
            map_size: int = None,
            directional_movements: int = 8) -> list[Coord]:

        if not map_size:
            map_size = self.max_map_size

        grid_2d = [[False] * map_size for _ in range(map_size)]
        for cell in cells.values():
            if 0 <= cell.coord.x < map_size and 0 <= cell.coord.y < map_size:
                grid_2d[cell.coord.x][cell.coord.y] = cell.walkable

        return [Coord(x=i[0], y=i[1]) for i in find_path(
            grid=grid_2d,
            start=start,
            goal=goal,
            map_size=map_size,
            directional_movements=directional_movements,
        )]

    @staticmethod
    def has_line_of_sight(cells: dict[str, WorldCell],
                          point_1: tuple[int, int],
                          point_2: tuple[int, int]) -> bool:
        x0, y0 = point_1
        x1, y1 = point_2

        # If start and end are the same, no 'between' points exist
        if point_1 == point_2:
            return True

        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        x, y = x0, y0

        # Generate all points along the line from start to end
        while (x, y) != (x1, y1):
            e2 = 2 * err
            if e2 > -dy:  # Step in x direction
                err -= dy
                x += sx
            if e2 < dx:  # Step in y direction
                err += dx
                y += sy
            coord = Coord(x=x, y=y)
            cell = cells.get(coord.code)
            if not cell:
                return False

            if not cell.walkable:
                return False

        return True
