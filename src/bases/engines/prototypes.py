import asyncio
from datetime import datetime
from typing import Callable

from pydantic import PrivateAttr, Field

from src.bases.models import BaseModel
from src.bases.os import OperatingSystemAPIPrototype
from src.constants.engine import ENGINE_IDLE_MODE

from .data_models import (
    GameDatabase,
    EngineSettings, EngineMeta, GameServer,
    PlayerSkill,
    GameItem, GameContext,
    SimulatedDataMemory, ViewportObject,
    Coord,
    Window,
    PartyMember,
    GameCoord, WorldCell, WorldMonsterSpot,
    EngineAutologinSettings, GameText, GameFunction,
    LanguageDatabase,
    EngineOperatorTrainingSpot,
    EngineOperatorEventParticipation, GameEvent, WorldFastTravel, NPC
)


class EnginePrototype(BaseModel):
    mode: str = ENGINE_IDLE_MODE
    h_process: int
    pid: int
    settings: EngineSettings
    autologin_settings: EngineAutologinSettings | None = None
    meta: EngineMeta
    game_server: GameServer
    game_database: GameDatabase
    os_api: OperatingSystemAPIPrototype
    max_threads: int = 100
    func_offsets: dict[str, int]
    game_funcs: dict[str, GameFunction] = Field(default_factory=dict)
    game_modules: dict[str, int]

    _shutdown_event: asyncio.Event = PrivateAttr()
    _game_context: GameContext | None = PrivateAttr()
    _game_context_synchronizer: 'EngineGameContextSynchronizerPrototype' = PrivateAttr()
    _function_triggerer: 'EngineFunctionTriggererPrototype' = PrivateAttr()
    _operator: 'EngineOperatorPrototype' = PrivateAttr()
    _action_handler: 'ActionHandlerPrototype' = PrivateAttr()
    _world_map_handler: 'WorldMapHandlerPrototype' = PrivateAttr()
    _simulated_data_memory: SimulatedDataMemory = PrivateAttr()
    _event_loop: asyncio.AbstractEventLoop = PrivateAttr()
    _original_codes: dict[int, bytes] = PrivateAttr()
    _game_hidden: bool = PrivateAttr()

    @property
    def game_hidden(self) -> bool:
        return self._game_hidden

    @property
    def shutdown_event(self) -> asyncio.Event:
        return self._shutdown_event

    @property
    def event_loop(self) -> asyncio.AbstractEventLoop:
        return self._event_loop

    @property
    def action_handler(self) -> 'ActionHandlerPrototype':
        return self._action_handler

    @property
    def operator(self) -> 'EngineOperatorPrototype':
        return self._operator

    @property
    def world_map_handler(self) -> 'WorldMapHandlerPrototype':
        return self._world_map_handler

    @property
    def function_triggerer(self) -> 'EngineFunctionTriggererPrototype':
        return self._function_triggerer

    @property
    def game_context_synchronizer(self) -> 'EngineGameContextSynchronizerPrototype':
        return self._game_context_synchronizer

    @property
    def simulated_data_memory(self) -> SimulatedDataMemory:
        return self._simulated_data_memory

    @property
    def game_context(self) -> GameContext:
        return self._game_context

    async def start_training(self):
        raise NotImplementedError

    async def stop_training(self):
        raise NotImplementedError

    async def start(self) -> None:
        raise NotImplementedError

    async def stop(self) -> None:
        raise NotImplementedError

    def toggle_game_visibility(self):
        raise NotImplementedError


class EngineFunctionTriggererPrototype(BaseModel):
    engine: EnginePrototype

    async def get_player_skills(self):
        raise NotImplementedError

    async def is_viewport_object_item(self, address: int):
        raise NotImplementedError

    async def add_stats(self, stat_code: str, amount: int):
        raise NotImplementedError

    def prepare_coord(self, address: int, coord: Coord) -> GameCoord:
        raise NotImplementedError

    def prepare_text(self,
                     address: int,
                     text: str,
                     text_class_addr: int) -> GameText:
        raise NotImplementedError

    async def move_to_coord(self, coord: Coord | GameCoord):
        raise NotImplementedError

    async def send_chat(self, text: str):
        raise NotImplementedError

    async def change_world(self, world_id: int, fast_travel_code: str = None):
        raise NotImplementedError

    async def reset_player(self, command: str):
        raise NotImplementedError

    async def pickup_item(self, viewport_object: ViewportObject) -> None:
        raise NotImplementedError

    async def use_item(self, item: GameItem):
        raise NotImplementedError

    async def drop_item(self, item: GameItem):
        raise NotImplementedError

    async def purchase_item(self, item: GameItem):
        raise NotImplementedError

    async def interact_npc(self, viewport_npc: ViewportObject):
        raise NotImplementedError

    async def close_window(self, window: Window) -> None:
        raise NotImplementedError

    async def send_party_request(self, viewport_player: ViewportObject):
        raise NotImplementedError

    async def handle_party_request(self, viewport_player: ViewportObject, accept: bool = False):
        raise NotImplementedError

    async def kick_party_member(self, party_member: PartyMember):
        raise NotImplementedError

    async def move_to_party_member(self, party_member: PartyMember):
        raise NotImplementedError

    async def cast_skill(self,
                         skill: PlayerSkill,
                         target: ViewportObject = None,
                         coord: Coord = None,
                         ):
        raise NotImplementedError

    async def melee_attack(self,
                           target: ViewportObject,
                           ):
        raise NotImplementedError

    async def repair_item(self, item: GameItem):
        raise NotImplementedError

    async def trigger_function(self, func: Callable, *args, **kwargs):
        raise NotImplementedError

    async def change_channel(self, channel_id: int):
        raise NotImplementedError

    async def login_screen_select_channel(self, channel_id: int):
        raise NotImplementedError

    async def login_screen_submit_credential(self, username: str, password: str):
        raise NotImplementedError

    async def lobby_screen_select_character(self, slot: int):
        raise NotImplementedError

    async def get_game_context(self):
        raise NotImplementedError

    async def get_game_data_tables(self):
        raise NotImplementedError

    async def get_game_events(self):
        raise NotImplementedError

    async def push_notification(self, text: str):
        raise NotImplementedError


class EngineOperatorPrototype(BaseModel):
    engine: EnginePrototype

    _workers: dict[str, asyncio.Task] = PrivateAttr()
    _potion_cooldowns: dict[str, datetime] = PrivateAttr()
    _skill_cooldowns: dict[int, datetime] = PrivateAttr()
    _occupied_monster_spots: dict[str, WorldMonsterSpot] = PrivateAttr()
    _party_requests_sent: dict[str, datetime] = PrivateAttr()
    _ignored_monsters: dict[int, datetime] = PrivateAttr()
    _player_skills: dict[int, PlayerSkill] = PrivateAttr()
    _player_skills_updated_at: datetime | None = PrivateAttr()
    _training_spot: EngineOperatorTrainingSpot | None = PrivateAttr()
    _event_participators: dict[str, tuple[EngineOperatorEventParticipation, asyncio.Task]] = PrivateAttr()

    @property
    def training_spot(self) -> EngineOperatorTrainingSpot:
        return self._training_spot

    @property
    def event_participators(self) -> dict[str, tuple[EngineOperatorEventParticipation, asyncio.Task]]:
        return self._event_participators

    async def handle_training(self):
        raise NotImplementedError

    async def handle_protection(self):
        raise NotImplementedError

    async def handle_basis_tasks(self):
        raise NotImplementedError

    async def handle_dialog_events(self):
        raise NotImplementedError

    async def handle_game_events(self):
        raise NotImplementedError

    async def change_mode(self, mode: str):
        raise NotImplementedError

    async def run(self) -> None:
        raise NotImplementedError


class EngineGameContextSynchronizerPrototype(BaseModel):
    engine: EnginePrototype

    @classmethod
    def init_context(cls,
                     engine: 'EnginePrototype',
                     ) -> GameContext:
        raise NotImplementedError

    async def get_events(self, taking_place_in: int = None) -> dict[str, GameEvent]:
        raise NotImplementedError

    def get_player_levels(self) -> int:
        raise NotImplementedError

    async def load_player_active_skills(self) -> dict[int, PlayerSkill]:
        raise NotImplementedError

    async def update_context(self):
        raise NotImplementedError

    async def run(self) -> None:
        raise NotImplementedError


class WorldMapHandlerPrototype(BaseModel):
    engine: EnginePrototype
    max_map_size: int = 256

    def load_world_cells(self, world_id: int) -> dict[str, WorldCell]:
        raise NotImplementedError

    def crop(self,
             world_id: int,
             center: tuple[int, int],
             bounding_box: tuple[int, int, int, int] = None) -> dict[str, WorldCell]:
        raise NotImplementedError

    def find_path(
            self,
            cells: dict[str, WorldCell],
            start: tuple[int, int],
            goal: tuple[int, int],
            map_size: int = None,
            directional_movements: int = 8) -> list[Coord]:
        raise NotImplementedError

    @staticmethod
    def has_line_of_sight(cells: dict[str, WorldCell],
                          point_1: tuple[int, int],
                          point_2: tuple[int, int]) -> bool:
        raise NotImplementedError


class EventParticipatorPrototype(BaseModel):
    engine: EnginePrototype
    participation: EngineOperatorEventParticipation

    @classmethod
    def init(cls, *args, **kwargs):
        return cls(*args, **kwargs)

    async def run(self):
        raise NotImplementedError


class QuizEventParticipatorPrototype(EventParticipatorPrototype):
    _notification_last_check: datetime | None = None
    _language_databases: dict[str, LanguageDatabase] = PrivateAttr()


class ActionHandlerPrototype(BaseModel):
    engine: EnginePrototype

    async def change_world(self, world_id: int, fast_travel_code: str = None):
        raise NotImplementedError

    async def go_to(self,
                    world_id: int,
                    coord: Coord,
                    fast_travel: WorldFastTravel = None,
                    distance_error: int = 2,
                    world_cells: dict[str: WorldCell] = None,
                    path_to_coord_from_fast_travel: list[Coord] = None,
                    ):
        raise NotImplementedError

    async def interact_npc(self, npc: NPC):
        raise NotImplementedError


EnginePrototype.model_rebuild()
