import asyncio

from src.utils import capture_error
from src.constants.engine import (
    ENGINE_IDLE_MODE,
    ENGINE_TRAINING_MODE,
)
from .prototypes import EngineOperatorPrototype


class EngineOperator(EngineOperatorPrototype):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._workers = {}
        self._skill_cooldowns = {}
        self._potion_cooldowns = {}
        self._occupied_monster_spots = {}
        self._party_requests_sent = {}
        self._ignored_monsters = {}
        self._player_skills = {}
        self._player_skills_updated_at = None
        self._training_spot = None
        self._event_participators = {}

    @staticmethod
    async def _cancel_worker(worker: asyncio.Task):
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass

    async def change_mode(self, mode: str):
        if mode == self.engine.mode:
            return

        if self.engine.mode == ENGINE_TRAINING_MODE:
            handle_training_worker = self._workers.get(self.handle_training.__name__)
            if handle_training_worker:
                await self._cancel_worker(handle_training_worker)
                self._workers.pop(self.handle_training.__name__, None)

        if mode == ENGINE_TRAINING_MODE:
            handle_training_worker = self._workers.get(self.handle_training.__name__)
            # cancel existing worker
            if handle_training_worker:
                await self._cancel_worker(handle_training_worker)
                self._workers.pop(self.handle_training.__name__, None)
            self._workers[self.handle_training.__name__] = asyncio.create_task(self.handle_training())

        self.engine.mode = mode

    async def run(self):
        # starting permanent workers
        self._workers[self.handle_protection.__name__] = asyncio.create_task(self.handle_protection())
        self._workers[self.handle_basis_tasks.__name__] = asyncio.create_task(self.handle_basis_tasks())
        self._workers[self.handle_game_events.__name__] = asyncio.create_task(self.handle_game_events())

        while not self.engine.shutdown_event.is_set():
            await asyncio.sleep(1)

        for worker in self._workers.values():
            worker.cancel()

        try:
            await asyncio.gather(*self._workers.values())
        except asyncio.CancelledError:
            pass
