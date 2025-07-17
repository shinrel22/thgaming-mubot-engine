import asyncio

from src.bases.engines import Coord
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
    (209, 244),  # left top
    (241, 244),  # right top
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
        self._world_cells = self.engine.world_map_handler.load_world_cells(WORLD_ID)

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

    def _find_start_point(self) -> Coord:
        occupied_points = set(map(
            lambda vpp: vpp.object.current_coord,
            self.engine.game_context.viewport.object_players.values()
        ))

        result = None
        distance = None
        for i in range(abs(
                START_AREA[0][0] - START_AREA[1][0]
        )):
            point = Coord(
                x=START_AREA[0][0] + i,
                y=START_AREA[0][1],
            )
            if point in occupied_points:
                continue

            d = calculate_distance(
                (
                    point.x,
                    point.y,
                ),
                (
                    self.engine.game_context.local_player.current_coord.x,
                    self.engine.game_context.local_player.current_coord.y,
                )
            )
            if distance is None or distance > d:
                distance = d
                result = point

        if not result:
            result = self.engine.game_context.local_player.current_coord

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
                await self.engine.action_handler.interact_npc(
                    npc=self.engine.game_database.npcs[NPC_ID]
                )
            except Error as e:
                if e.code == 'FailedToFindViewportNPC':
                    pass
                else:
                    raise e
            attempts += 1
            await asyncio.sleep(1)

    @staticmethod
    def _find_end_point(start_point: Coord) -> Coord:
        top_left, top_right, bottom_left, bottom_right = FINISH_AREA

        result_y = int(bottom_left[1] + (abs(top_left[1] - bottom_left[1]) / 2))

        result = Coord(
            x=start_point.x,
            y=result_y
        )
        return result

    async def _play_event(self):
        while not self._is_event_ended():
            start_point = None
            running_path = None
            end_point = None
            current_step_index = 0

            while not self._is_within_area(
                    FINISH_AREA,
                    self.engine.game_context.local_player.current_coord
            ):
                if self._is_event_ended():
                    return

                if self._is_within_area(
                        START_AREA,
                        self.engine.game_context.local_player.current_coord
                ):
                    if not start_point:
                        start_point = self._find_start_point()
                    while calculate_distance(
                            (
                                    self.engine.game_context.local_player.current_coord.x,
                                    self.engine.game_context.local_player.current_coord.y
                            ),
                            (
                                    start_point.x,
                                    start_point.y
                            )
                    ) > 2:
                        if self._is_event_ended():
                            return
                        await self.engine.function_triggerer.move_to_coord(start_point)
                        await asyncio.sleep(0.5)

                if end_point is None:
                    end_point = self._find_end_point(start_point)

                if running_path is None:
                    running_path = self.engine.world_map_handler.find_path(
                        cells=self._world_cells,
                        start=(
                            self.engine.game_context.local_player.current_coord.x,
                            self.engine.game_context.local_player.current_coord.y,
                        ),
                        goal=(end_point.x, end_point.y),
                    )

                while not self._is_red_signal() and current_step_index + 1 < len(running_path):
                    if self._is_event_ended():
                        return

                    if self.engine.game_context.local_player.is_destroying:
                        start_point = None
                        end_point = None
                        running_path = None
                        current_step_index = 0
                        await asyncio.sleep(3)
                        break

                    remaining_distance = calculate_distance(
                        (
                            self.engine.game_context.local_player.current_coord.x,
                            self.engine.game_context.local_player.current_coord.y
                        ),
                        (end_point.x, end_point.y),
                    )
                    if remaining_distance <= 10:
                        await self.engine.function_triggerer.move_to_coord(end_point)
                        await self.engine.function_triggerer.teleport(end_point)
                        await asyncio.sleep(1)
                        current_step_index = len(running_path)
                        break
                    next_step_index = current_step_index + 1
                    next_step = running_path[next_step_index]

                    # last step
                    if next_step_index + 1 >= len(running_path):
                        await self.engine.function_triggerer.move_to_coord(end_point)
                        await self.engine.function_triggerer.teleport(next_step)
                        current_step_index = len(running_path)
                        await asyncio.sleep(1)
                        break

                    has_blocker = False
                    for vpp in self.engine.game_context.viewport.object_players.values():
                        if vpp.object.current_coord == next_step:
                            has_blocker = True
                            break

                    if has_blocker:
                        next_step_index += 1
                        next_step = running_path[next_step_index]
                        await self.engine.function_triggerer.move_to_coord(next_step)
                        await self.engine.function_triggerer.teleport(next_step)
                    else:
                        await self.engine.function_triggerer.move_to_coord(next_step)
                    current_step_index = next_step_index
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
