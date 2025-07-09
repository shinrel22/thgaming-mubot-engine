import asyncio

from src.utils import capture_error

from .data_models import (
    GameScreen, LocalPlayer,
    Viewport, ChatFrame,
    Dialog
)
from .prototypes import EngineGameContextSynchronizerPrototype


class EngineGameContextSynchronizer(EngineGameContextSynchronizerPrototype):

    def _update_screen(self) -> GameScreen | None:
        raise NotImplementedError

    def _update_local_player(self, address: int) -> LocalPlayer:
        raise NotImplementedError

    def _update_current_dialog(self) -> Dialog | None:
        raise NotImplementedError

    def _update_viewport(self) -> Viewport | None:
        raise NotImplementedError

    def _update_chat_frame(self) -> ChatFrame | None:
        raise NotImplementedError

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
