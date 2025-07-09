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

    async def handle_training(self):
        raise NotImplementedError

    async def handle_protection(self):
        raise NotImplementedError

    async def handle_basis_tasks(self):
        raise NotImplementedError

    async def handle_events(self):
        raise NotImplementedError

    async def run(self):
        # starting permanent workers
        self._workers[self.handle_protection.__name__] = asyncio.create_task(self.handle_protection())
        self._workers[self.handle_basis_tasks.__name__] = asyncio.create_task(self.handle_basis_tasks())
        self._workers[self.handle_events.__name__] = asyncio.create_task(self.handle_events())
        while not self.engine.shutdown_event.is_set():
            handle_training_worker = self._workers.get(self.handle_training.__name__)

            if self.engine.mode == ENGINE_TRAINING_MODE:
                if handle_training_worker:
                    if handle_training_worker.done():
                        training_error = handle_training_worker.exception()
                        if training_error:
                            capture_error(training_error)
                        else:
                            # done training?
                            self.engine.mode = ENGINE_IDLE_MODE
                            self._workers.pop(self.handle_training.__name__)
                else:
                    self._workers[self.handle_training.__name__] = asyncio.create_task(self.handle_training())

            else:
                if handle_training_worker:
                    handle_training_worker.cancel()
                    self._workers.pop(self.handle_training.__name__)

            await asyncio.sleep(1)

        for worker in self._workers.values():
            worker.cancel()

        try:
            await asyncio.gather(*self._workers.values())
        except asyncio.CancelledError:
            pass
