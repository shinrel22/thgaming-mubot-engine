import asyncio
import logging

import uvicorn
import websockets
from fastapi import FastAPI
from datetime import datetime
from pydantic import Field, PrivateAttr

from src.bases.engines import GameServer, EngineMeta, GameDatabase, EngineSettings
from src.bases.engines.data_models import EngineAutologinSettings
from src.bases.models import BaseModel
from src.bases.engines.prototypes import EnginePrototype
from src.utils import get_now
from src.bases.os import OperatingSystemAPIPrototype


class Message(BaseModel):
    type: str
    data: dict
    timestamp: datetime = Field(default_factory=get_now)


class TrainerPrototype(BaseModel):
    engines: dict[int, EnginePrototype] = Field(default_factory=dict)
    ui_origin: str
    websocket_server_port: int
    restful_server_port: int

    _os_api: OperatingSystemAPIPrototype = PrivateAttr()
    _game_server: GameServer | None = PrivateAttr()
    _game_database: GameDatabase | None = PrivateAttr()
    _shutdown_event: asyncio.Event = PrivateAttr()
    _websocket_server: 'WebsocketServerPrototype' = PrivateAttr()
    _restful_server: 'RestfulServerPrototype' = PrivateAttr()
    _workers: dict[str, asyncio.Task] = PrivateAttr()
    _event_loop: asyncio.AbstractEventLoop | None = PrivateAttr()

    @property
    def os_api(self) -> OperatingSystemAPIPrototype:
        return self._os_api

    @property
    def game_server(self) -> GameServer:
        return self._game_server

    @property
    def shutdown_event(self) -> asyncio.Event:
        return self._shutdown_event

    @property
    def game_database(self) -> GameDatabase:
        return self._game_database

    @property
    def event_loop(self) -> asyncio.AbstractEventLoop:
        return self._event_loop

    @property
    def websocket_server(self) -> 'WebsocketServerPrototype':
        return self._websocket_server

    @property
    def restful_server(self) -> 'RestfulServerPrototype':
        return self._restful_server

    async def run(self):
        raise NotImplementedError

    async def shutdown(self):
        raise NotImplementedError

    async def start_engine(self,
                           autologin_settings: EngineAutologinSettings = None
                           ) -> EnginePrototype:
        raise NotImplementedError

    async def start_training(self, engine: EnginePrototype):
        raise NotImplementedError

    async def stop_training(self, engine: EnginePrototype):
        raise NotImplementedError


class WebsocketServerPrototype(BaseModel):
    port: int
    trainer: TrainerPrototype

    _server: websockets.Server = PrivateAttr()
    _client_connection: websockets.ServerConnection | None = PrivateAttr()
    _workers: dict[str, asyncio.Task] = PrivateAttr()

    @property
    def client_connection(self) -> websockets.ServerConnection:
        return self._client_connection

    async def send_message(self, client_connection: websockets.ServerConnection, message: Message):
        raise NotImplementedError

    async def run(self):
        raise NotImplementedError

    async def handle_client_disconnected(self, client_connection: websockets.ServerConnection):
        raise NotImplementedError

    async def handle_client_connection(self, client_connection: websockets.ServerConnection):
        raise NotImplementedError

    async def handle_incoming_message(self, client_connection: websockets.ServerConnection, message: Message):
        raise NotImplementedError


class RestfulServerPrototype(BaseModel):
    port: int
    ui_origin: str
    trainer: TrainerPrototype

    _api: FastAPI = PrivateAttr()
    _server: uvicorn.Server = PrivateAttr()

    def setup_api(self):
        raise NotImplementedError

    def setup_exception_handlers(self):
        raise NotImplementedError

    def setup_server(self):
        raise NotImplementedError

    async def run(self):
        raise NotImplementedError


TrainerPrototype.model_rebuild()
