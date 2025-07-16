import asyncio

from src.bases.engines import Coord
from src.bases.engines.data_models import NPC, World, WorldFastTravel
from src.bases.engines.event_participators import EventParticipator
from src.bases.errors import Error
from src.constants.engine import (
    EVENT_PARTICIPATION_STARTED_STATUS,
    EVENT_PARTICIPATION_ENDED_STATUS,
    ENGINE_PARTICIPATING_EVENT_MODE
)
from src.utils import capture_error, calculate_distance

STARTING_NOTI: str = 'COLISEUM - STOP OR DIE - ROUND 1'
ENDING_NOTI: str = 'STOP OR DIE FINISHED'
GREEN_SIGNAL_NOTI: str = 'GREEN SIGNAL'
RED_SIGNAL_NOTI: str = 'RED SIGNAL'
LOGGING_MSG_PREFIX: str = '[StopOrDie]'
WORLD_ID: int = 40
FAST_TRAVEL_CODE: str = 'Coliseum'
NPC_ID: int = 415

EVENT_AREA: list[tuple[int, int]] = [
    (209, 244),  # top left
    (241, 244),  # top right
    (209, 177),  # bottom left
    (241, 177),  # bottom right
]

START_AREA: list[tuple[int, int]] = [
    (209, 181),  # top left
    (241, 181),  # top right
    EVENT_AREA[2],  # bottom left
    EVENT_AREA[3],  # bottom right
]

FINISH_AREA: list[tuple[int, int]] = [
    EVENT_AREA[0],  # top left
    EVENT_AREA[1],  # top right
    (209, 240),  # bottom left
    (241, 240),  # bottom right
]


class UnityMegaMUStopOrDieEventParticipator(EventParticipator):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._npc: NPC = self.engine.game_database.npcs[NPC_ID]
        self._world: World = self.engine.game_database.worlds[WORLD_ID]
        self._fast_travel: WorldFastTravel = self._world.fast_travels[FAST_TRAVEL_CODE]
        self._running_lines: list[tuple[Coord, Coord]] = self._gen_running_lines()

    @staticmethod
    def _gen_running_lines() -> list[tuple[Coord, Coord]]:
        result = []

        sa_top_left, sa_top_right, sa_bottom_left, sa_bottom_right = START_AREA
        fa_top_left, fa_top_right, fa_bottom_left, fa_bottom_right = FINISH_AREA

        for dx in range(abs(sa_top_right[0] - sa_top_left[0])):
            start_point = Coord(x=sa_top_left[0] + dx, y=sa_top_left[1])
            end_point = Coord(x=fa_top_left[0] + dx, y=fa_top_left[1])
            result.append((start_point, end_point))
        return result

    async def _wait_for_started(self):
        target_notifications: set[str] = {
            STARTING_NOTI,
            GREEN_SIGNAL_NOTI,
            RED_SIGNAL_NOTI
        }
        self._logger.info(f'{LOGGING_MSG_PREFIX} Waiting for event to start')
        if self.participation.status == EVENT_PARTICIPATION_STARTED_STATUS:
            return

        while self.participation.status != EVENT_PARTICIPATION_STARTED_STATUS:
            for noti_title in self._get_notifications():
                if noti_title in target_notifications:
                    self.participation.status = EVENT_PARTICIPATION_STARTED_STATUS
                    break
            await asyncio.sleep(1)

        self._logger.info(f'{LOGGING_MSG_PREFIX} Event started')

    def _is_event_ended(self) -> bool:
        if self.participation.status == EVENT_PARTICIPATION_ENDED_STATUS:
            return True
        if ENDING_NOTI in self._get_notifications():
            self.participation.status = EVENT_PARTICIPATION_ENDED_STATUS
            self._logger.info(f'{LOGGING_MSG_PREFIX} Event ended')
            return True
        return False

    def _is_within_area(self,
                        area: list[tuple[int, int]],
                        coord: Coord
                        ) -> bool:
        if self.engine.game_context.screen.world_id != WORLD_ID:
            return False

        top_left, top_right, bottom_left, bottom_right = area

        return ((top_left[0] <= coord.x <= top_right[0])
                and (bottom_left[1] <= coord.y <= top_right[1]))

    def _get_nearest_running_line(self) -> tuple[Coord, Coord]:

        result = None
        distance = None

        for line in self._running_lines:
            start_point, _ = line
            d = calculate_distance(
                (start_point.x, start_point.y),
                (
                    self.engine.game_context.local_player.current_coord.x,
                    self.engine.game_context.local_player.current_coord.y,
                )
            )
            if distance is None or d < distance:
                distance = d
                result = line

        return result

    async def _ensure_within_event_area(self):
        while self.engine.game_context.screen.world_id != WORLD_ID:
            if self._is_event_ended():
                return

            await self.engine.action_handler.change_world(
                world_id=WORLD_ID,
                fast_travel_code=FAST_TRAVEL_CODE,
            )

        attempts: int = 0
        while not self._is_within_area(
                EVENT_AREA,
                self.engine.game_context.local_player.current_coord
        ):
            if attempts >= 10:
                raise Error(
                    code='FailedToEnterEventArea',
                    message='Failed to enter event area'
                )
            try:
                await self.engine.action_handler.interact_npc(npc=self._npc)
            except Error as e:
                if e.code == 'FailedToFindViewportNPC':
                    pass
                else:
                    raise e
            attempts += 1
            await asyncio.sleep(1)

    async def _play_event(self):
        while not self._is_event_ended():

            running_line = None
            teleport_casted = False

            while not self._is_within_area(
                    FINISH_AREA,
                    self.engine.game_context.local_player.current_coord
            ):

                if self._is_event_ended():
                    return

                if not running_line:
                    running_line = self._get_nearest_running_line()

                start_point, end_point = running_line

                if self._is_within_area(
                        START_AREA,
                        self.engine.game_context.local_player.current_coord
                ):
                    await self.engine.action_handler.go_to(
                        world_id=WORLD_ID,
                        coord=start_point,
                        distance_error=0
                    )

                while not self._is_red_signal():
                    if calculate_distance(
                            (end_point.x, end_point.y),
                            (
                                    self.engine.game_context.local_player.current_coord.x,
                                    self.engine.game_context.local_player.current_coord.y,
                            )
                    ) <= 8 and not teleport_casted:
                        await self.engine.function_triggerer.teleport(end_point)
                        teleport_casted = True
                    await self.engine.function_triggerer.move_to_coord(end_point)
                    await asyncio.sleep(0.1)

                while self.engine.game_context.local_player.is_moving:
                    await self.engine.function_triggerer.move_to_coord(
                        self.engine.game_context.local_player.current_coord
                    )
                    await asyncio.sleep(0.1)

                await asyncio.sleep(0.1)

            await asyncio.sleep(1)

    def _is_statue_ready(self) -> bool:
        statue_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=self.engine.simulated_data_memory.game_func_params.ptr_stop_or_die_statue
        )
        return statue_addr is not None

    def _is_red_signal(self) -> bool:
        statue_addr = self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=self.engine.simulated_data_memory.game_func_params.ptr_stop_or_die_statue
        )
        if not statue_addr:
            return True

        return self.engine.os_api.get_value_from_pointer(
            h_process=self.engine.h_process,
            pointer=statue_addr + self.engine.meta.stop_or_die_red_signal_flag_offset,
            value_size=1
        ) == 1

    async def run(self):
        await self._wait_for_started()

        await self.engine.operator.change_mode(ENGINE_PARTICIPATING_EVENT_MODE)
        self._logger.info(f'{LOGGING_MSG_PREFIX} Start participating')

        while not self._is_event_ended():
            if not self._is_within_area(
                    area=EVENT_AREA,
                    coord=self.engine.game_context.local_player.current_coord
            ):
                await self._ensure_within_event_area()

            if not self._is_statue_ready():
                await asyncio.sleep(1)
                continue

            try:
                await self._play_event()
            except Exception as e:
                capture_error(e)
                await asyncio.sleep(1)
                continue

            await asyncio.sleep(1)
