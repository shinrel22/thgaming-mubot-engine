import asyncio
import logging
from datetime import datetime
from typing import Callable
from pydantic import PrivateAttr, Field

from src.bases.models import BaseModel
from src.bases.os import OperatingSystemAPIPrototype
from src.constants.engine import ENGINE_IDLE_MODE

from .data_models import (
    GameDatabase,
    EngineSettings, EngineMeta, GameServer,
    GameBody, PlayerSkill,
    World, GameItem, GameContext,
    SimulatedDataMemory, ViewportObject,
    NPCBody, Coord, Window,
    PlayerBody, PartyMember,
    EngineOperatorTrainingSpot,
    GameCoord, WorldCell, WorldMonsterSpot,
    EngineAutologinSettings, GameText, GameFunction
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
    _game_action_handler: 'EngineGameActionHandlerPrototype' = PrivateAttr()
    _operator: 'EngineOperatorPrototype' = PrivateAttr()
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
    def operator(self) -> 'EngineOperatorPrototype':
        return self._operator

    @property
    def world_map_handler(self) -> 'WorldMapHandlerPrototype':
        return self._world_map_handler

    @property
    def game_action_handler(self) -> 'EngineGameActionHandlerPrototype':
        return self._game_action_handler

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


class EngineGameActionHandlerPrototype(BaseModel):
    engine: EnginePrototype

    def add_stats(self, stat_code: str, amount: int):
        raise NotImplementedError

    def prepare_coord(self, address: int, coord: Coord) -> GameCoord:
        raise NotImplementedError

    def prepare_text(self,
                     address: int,
                     text: str,
                     text_class_addr: int) -> GameText:
        raise NotImplementedError

    def move_to_coord(self, coord: Coord | GameCoord):
        raise NotImplementedError

    def send_chat(self, text: str):
        raise NotImplementedError

    def change_world(self, world_id: int, fast_travel_code: str = None):
        raise NotImplementedError

    def reset_player(self, command: str):
        raise NotImplementedError

    def pickup_item(self, viewport_object: ViewportObject) -> None:
        raise NotImplementedError

    def use_item(self, item: GameItem):
        raise NotImplementedError

    def drop_item(self, item: GameItem):
        raise NotImplementedError

    def purchase_item(self, item: GameItem):
        raise NotImplementedError

    def interact_npc(self, viewport_npc: ViewportObject):
        raise NotImplementedError

    def close_window(self, window: Window) -> None:
        raise NotImplementedError

    def send_party_request(self, viewport_player: ViewportObject):
        raise NotImplementedError

    def handle_party_request(self, viewport_player: ViewportObject, accept: bool = False):
        raise NotImplementedError

    def kick_party_member(self, party_member: PartyMember):
        raise NotImplementedError

    def move_to_party_member(self, party_member: PartyMember):
        raise NotImplementedError

    def cast_skill(self,
                   skill: PlayerSkill,
                   target: ViewportObject = None,
                   coord: Coord = None,
                   ):
        raise NotImplementedError

    def melee_attack(self,
                   target: ViewportObject,
                   ):
        raise NotImplementedError

    def repair_item(self, item: GameItem):
        raise NotImplementedError

    def trigger_function(self, address: int):
        raise NotImplementedError

    def change_channel(self, channel_id: int):
        raise NotImplementedError

    def login_screen_select_channel(self, channel_id: int):
        raise NotImplementedError

    def login_screen_submit_credential(self, username: str, password: str):
        raise NotImplementedError

    def lobby_screen_select_character(self, slot: int):
        raise NotImplementedError


class EngineOperatorPrototype(BaseModel):
    engine: EnginePrototype

    _workers: dict[str, asyncio.Task] = PrivateAttr()
    _potion_cooldowns: dict[str, datetime] = PrivateAttr()
    _skill_cooldowns: dict[int, datetime] = PrivateAttr()
    _occupied_monster_spots: dict[str, WorldMonsterSpot] = PrivateAttr()
    _party_requests_sent: dict[str, datetime] = PrivateAttr()
    _ignored_monsters: dict[int, datetime] = PrivateAttr()

    async def handle_training(self):
        raise NotImplementedError

    async def handle_protection(self):
        raise NotImplementedError

    async def handle_basis_tasks(self):
        raise NotImplementedError

    async def handle_events(self):
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


EnginePrototype.model_rebuild()
