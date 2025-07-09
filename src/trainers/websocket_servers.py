import asyncio
import json

import websockets

from config import ENVIRONMENT
from src.bases.trainers.prototypes import WebsocketServerPrototype, Message
from src.constants.trainer import (
    GAME_DATABASE_UPDATE_WS_MSG_TYPE,
    ENGINE_UPDATE_WS_MSG_TYPE
)
from src.utils import capture_error


class WebsocketServer(WebsocketServerPrototype):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._client_connection = None
        self._workers = {}

    def _start_workers(self):
        self._workers[self._broadcast_game_database.__name__] = asyncio.create_task(self._broadcast_game_database())
        self._workers[self._broadcast_engines.__name__] = asyncio.create_task(self._broadcast_engines())

    async def _broadcast_game_database(self):
        while not self.trainer.shutdown_event.is_set():
            if self._client_connection and self.trainer.game_database:
                await self.send_message(
                    client_connection=self._client_connection,
                    message=Message(
                        type=GAME_DATABASE_UPDATE_WS_MSG_TYPE,
                        data=self.trainer.game_database.model_dump()
                    )
                )
            await asyncio.sleep(30)

    async def _broadcast_engines(self):
        while not self.trainer.shutdown_event.is_set():
            if self._client_connection:
                for engine_id, engine in self.trainer.engines.items():
                    await self.send_message(
                        client_connection=self._client_connection,
                        message=Message(
                            type=ENGINE_UPDATE_WS_MSG_TYPE,
                            data=self.trainer.parse_engine_data_for_client(engine_id=engine_id, engine=engine)
                        )
                    )
            await asyncio.sleep(1)

    async def handle_client_connection(self, client_connection: websockets.ServerConnection):
        if self._client_connection:
            # only accept 1 client, reject others
            await self.send_message(
                message=Message(
                    type='error',
                    data={
                        'message': 'Another client already connected. You are rejected'
                    }
                ),
                client_connection=client_connection
            )
            return
        # Register client
        self._client_connection = client_connection
        print(f"Client connected: {client_connection}")

        try:
            async for m in client_connection:
                # Process incoming message
                message = Message(**json.loads(m))
                await self.handle_incoming_message(client_connection, message)

        except websockets.ConnectionClosed:
            pass

        except Exception as e:
            capture_error(e)

        await self.handle_client_disconnected(client_connection)

    async def handle_incoming_message(self, client_connection: websockets.ServerConnection, message: Message):
        pass

    async def send_message(self, client_connection: websockets.ServerConnection, message: Message):
        """Handle send with error catching"""
        if not client_connection:
            return
        try:
            await client_connection.send(message.model_dump_json())
        except websockets.ConnectionClosed:
            await self.handle_client_disconnected(client_connection)
        except Exception as e:
            capture_error(e)

    async def handle_client_disconnected(self, client_connection: websockets.ServerConnection):
        print("Client disconnected", client_connection)
        self._client_connection = None
        if ENVIRONMENT == 'PRD':
            asyncio.create_task(self.trainer.shutdown())

    async def run(self):
        self._start_workers()

        self._server = await websockets.serve(self.handle_client_connection, 'localhost',
                                        self.port)

        while not self.trainer.shutdown_event.is_set():
            await asyncio.sleep(1)

        self._server.close()
