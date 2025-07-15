import asyncio

from src.utils import capture_error

from .prototypes import EngineGameContextSynchronizerPrototype


class EngineGameContextSynchronizer(EngineGameContextSynchronizerPrototype):

    async def run(self) -> None:
        while not self.engine.shutdown_event.is_set():
            try:
                await self.update_context()
            except asyncio.CancelledError:
                break
            except KeyboardInterrupt:
                break
            except Exception as e:
                capture_error(e)
            finally:
                await asyncio.sleep(0.05)
