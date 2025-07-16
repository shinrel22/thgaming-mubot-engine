import asyncio

from src.bases.errors import Error
from src.bases.engines.data_models import Coord, WorldCell, WorldFastTravel, NPC
from src.constants.engine import NPC_MERCHANT_TYPE
from src.utils import calculate_distance
from src.bases.engines.action_handlers import ActionHandler


class UnityMegaMUActionHandler(ActionHandler):

    async def change_world(self, world_id: int, fast_travel_code: str = None):
        await self.engine.function_triggerer.change_world(
            world_id,
            fast_travel_code=fast_travel_code
        )
        await asyncio.sleep(3)

        while self.engine.game_context.screen.world_id != world_id:
            await self.engine.function_triggerer.change_world(
                world_id,
                fast_travel_code=fast_travel_code
            )
            await asyncio.sleep(3)

        while self.engine.game_context.screen.is_loading or self.engine.game_context.screen.is_world_loading:
            await asyncio.sleep(1)

    async def go_to(self,
                    world_id: int,
                    coord: Coord,
                    fast_travel: WorldFastTravel = None,
                    distance_error: int = 2,
                    world_cells: dict[str: WorldCell] = None,
                    path_to_coord_from_fast_travel: list[Coord] = None,
                    ):
        while self.engine.game_context.is_channel_switching:
            await asyncio.sleep(1)

        player_levels = self.engine.game_context_synchronizer.get_player_levels()

        already_change_world_with_fast_travel = False
        if self.engine.game_context.screen.world_id != world_id:
            if fast_travel and fast_travel.lvl_require <= player_levels:
                await self.change_world(world_id, fast_travel.code)
            else:
                await self.change_world(world_id)

        while calculate_distance(
                (
                        self.engine.game_context.local_player.current_coord.x,
                        self.engine.game_context.local_player.current_coord.y
                ),
                (
                        coord.x,
                        coord.y
                ),
        ) > distance_error:

            if world_cells:
                path_to_coord_from_player = self.engine.world_map_handler.find_path(
                    cells=world_cells,
                    start=(
                        self.engine.game_context.local_player.current_coord.x,
                        self.engine.game_context.local_player.current_coord.y
                    ),
                    goal=(
                        coord.x,
                        coord.y
                    )
                )
                if (fast_travel
                        and fast_travel.lvl_require <= player_levels
                        and not already_change_world_with_fast_travel):
                    if not path_to_coord_from_fast_travel:
                        path_to_coord_from_fast_travel = self.engine.world_map_handler.find_path(
                            cells=world_cells,
                            start=(
                                fast_travel.coord.x,
                                fast_travel.coord.y
                            ),
                            goal=(
                                coord.x,
                                coord.y
                            )
                        )

                    if not path_to_coord_from_player or len(path_to_coord_from_player) > len(
                            path_to_coord_from_fast_travel):
                        await self.change_world(world_id, fast_travel.code)
                        already_change_world_with_fast_travel = True

            if self.engine.game_context.screen.world_id != world_id:
                return await self.go_to(
                    world_id=world_id,
                    coord=coord,
                    fast_travel=fast_travel,
                    distance_error=distance_error,
                    world_cells=world_cells,
                    path_to_coord_from_fast_travel=path_to_coord_from_fast_travel
                )

            await self.engine.function_triggerer.move_to_coord(coord)
            await asyncio.sleep(0.1)

        return None

    async def interact_npc(self, npc: NPC):
        nearest_coord = None
        current_distance = None

        player = self.engine.game_context.local_player

        for world_id, coords in npc.worlds.items():
            if world_id != self.engine.game_context.screen.world_id:
                continue

            for coord in coords:
                distance = calculate_distance(
                    (coord.x, coord.y),
                    (player.current_coord.x, player.current_coord.y)
                )
                if nearest_coord:
                    if distance < current_distance:
                        current_distance = distance
                        nearest_coord = coord
                else:
                    nearest_coord = coord
                    current_distance = distance

        if not nearest_coord:
            raise Error(code='FailedToFindNPCNearestCoord')

        while calculate_distance(
                (nearest_coord.x, nearest_coord.y),
                (player.current_coord.x, player.current_coord.y)
        ) > 2:
            await self.engine.function_triggerer.move_to_coord(nearest_coord)
            await asyncio.sleep(2)
            player = self.engine.game_context.local_player

        viewport_npc = None
        for vpn in self.engine.game_context.viewport.object_npcs.values():
            if vpn.object.npc_id == npc.id:
                viewport_npc = vpn

        if not viewport_npc:
            raise Error(
                code='FailedToFindViewportNPC'
            )

        await self.engine.function_triggerer.interact_npc(viewport_npc)
        await asyncio.sleep(1)

        if NPC_MERCHANT_TYPE in npc.types:
            while not self.engine.game_context.merchant.window.is_open:
                await self.engine.function_triggerer.interact_npc(viewport_npc)
                await asyncio.sleep(1)
