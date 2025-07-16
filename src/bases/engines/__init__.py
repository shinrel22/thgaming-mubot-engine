import asyncio

from src.constants.engine import (
    GAME_CONTEXT_SYNCHRONIZER,
    ENGINE_OPERATOR, GAME_PLAYING_SCREEN, ENGINE_TRAINING_MODE, ENGINE_IDLE_MODE,
)
from src.bases.errors import Error
from .action_handlers import ActionHandler

from .function_triggerers import EngineFunctionTriggerer
from .game_context_synchronizers import EngineGameContextSynchronizer
from .operators import EngineOperator
from .prototypes import EnginePrototype
from .world_map_handlers import WorldMapHandler
from .data_models import (
    Coord, ChatFrame, GameContext,
    GameDatabase, PlayerClass, LocalPlayer, GameScreen, GameObject,
    EngineSettings, EngineMeta, GameServer,
    GameBody, GameItem, SystemInfo,
    Viewport, PlayerSkill, World, SimulatedDataMemory
)


class Engine(EnginePrototype):
    def __init__(self,
                 **kwargs
                 ):
        super().__init__(**kwargs)

        self._simulated_data_memory = self._init_simulated_data_memory()

        self._shutdown_event: asyncio.Event = asyncio.Event()

        self._workers: dict[str, asyncio.Task] = {}

        self._started: bool = False
        self._game_hidden: bool = False

        self._game_context = None
        self._game_context_synchronizer = self._init_game_context_synchronizer()
        self._function_triggerer = self._init_function_triggerer()
        self._operator = self._init_operator()
        self._action_handler = self._init_action_handler()
        self._world_map_handler = WorldMapHandler(engine=self)
        self._original_codes = {}

    def _init_simulated_data_memory(self) -> SimulatedDataMemory:
        raise NotImplementedError

    def _init_game_context(self) -> GameContext:
        raise NotImplementedError

    def _init_game_context_synchronizer(self) -> EngineGameContextSynchronizer:
        raise NotImplementedError

    def _init_function_triggerer(self) -> EngineFunctionTriggerer:
        raise NotImplementedError

    def _init_operator(self) -> EngineOperator:
        raise NotImplementedError

    def _init_action_handler(self) -> ActionHandler:
        raise NotImplementedError

    def _allocate_simulated_data_memory(self) -> SimulatedDataMemory:
        self._simulated_data_memory.ptr_base = self.os_api.allocate_memory(
            h_process=self.h_process,
            size=2048
        )

        ptr_count: int = 0

        for param_name in self._simulated_data_memory.game_func_params.__class__.model_fields.keys():
            if param_name.startswith('ptr_'):
                value = self._simulated_data_memory.ptr_base + (ptr_count * 8)
                ptr_count += 1
            elif param_name.startswith('data_'):
                value = self.os_api.allocate_memory(
                    h_process=self.h_process,
                    size=2048
                )
            else:
                raise Error(message='Unsupported param name: {}'.format(param_name))
            setattr(self._simulated_data_memory.game_func_params, param_name, value)

        for func_code, func in self._simulated_data_memory.game_funcs.items():
            for callback_code in func.callbacks.keys():
                callback_addr = self.os_api.allocate_memory(
                    h_process=self.h_process,
                    size=2048
                )
                func.callbacks[callback_code] = callback_addr
                print(func_code, callback_code, hex(callback_addr))

            for trigger_code in func.triggers.keys():
                trigger_addr = self.os_api.allocate_memory(
                    h_process=self.h_process,
                    size=2048
                )
                func.triggers[trigger_code] = trigger_addr
                print(func_code, trigger_code, hex(trigger_addr))

        return self._simulated_data_memory

    def _handle_injections(self) -> None:
        raise NotImplementedError

    def _deallocate_simulated_data_memory(self):

        game_func_params = self._simulated_data_memory.game_func_params
        game_funcs = self._simulated_data_memory.game_funcs

        try:
            self.os_api.read_memory(address=self._simulated_data_memory.ptr_base, h_process=self.h_process, size=1)
            self.os_api.dealloc_memory(address=self._simulated_data_memory.ptr_base, h_process=self.h_process)
        except OSError:
            pass

        for param_name, param_addr in game_func_params.model_dump().items():
            if param_name.startswith('ptr_') or not param_addr:
                continue

            # check if process is still running or h_process is still valid
            try:
                self.os_api.read_memory(address=param_addr, h_process=self.h_process, size=1)
            except OSError:
                continue
            self.os_api.dealloc_memory(address=param_addr, h_process=self.h_process)

        for game_func in game_funcs.values():
            for callback_addr in game_func.callbacks.values():
                if not callback_addr:
                    continue
                # check if process is still running or h_process is still valid
                try:
                    self.os_api.read_memory(address=callback_addr, h_process=self.h_process, size=1)
                except OSError:
                    continue
                self.os_api.dealloc_memory(address=callback_addr, h_process=self.h_process)
            for trigger_addr in game_func.triggers.values():
                if not trigger_addr:
                    continue
                # check if process is still running or h_process is still valid
                try:
                    self.os_api.read_memory(address=trigger_addr, h_process=self.h_process, size=1)
                except OSError:
                    continue
                self.os_api.dealloc_memory(address=trigger_addr, h_process=self.h_process)

    def _restore_functions(self):
        for addr, original_code in self._original_codes.items():
            try:
                self.os_api.read_memory(address=addr, h_process=self.h_process, size=1)
            except OSError:
                continue
            self.os_api.write_memory(
                h_process=self.h_process,
                address=addr,
                data=original_code
            )

    def toggle_game_visibility(self):
        if self._game_hidden:
            self._game_hidden = False
            self.os_api.toggle_window_visibility(
                pid=self.pid,
                visible=True,
                focus=True
            )
        else:
            self._game_hidden = True
            self.os_api.toggle_window_visibility(
                pid=self.pid,
                visible=False
            )

    async def start_training(self):
        if self.game_context.screen.screen_id != self.meta.screen_mappings[GAME_PLAYING_SCREEN]:
            raise Error(
                code='InvalidConditions',
                message='Invalid screen'
            )

        if not self._game_context.local_player:
            raise Error(
                code='InvalidConditions',
                message='Local player not found'
            )
        await self.operator.change_mode(ENGINE_TRAINING_MODE)

    async def stop_training(self):
        await self.operator.change_mode(ENGINE_IDLE_MODE)

    async def start(self) -> None:
        if self._started:
            raise Error(message='Engine is already running')

        self._event_loop = asyncio.get_event_loop()
        self._started = True
        self._shutdown_event.clear()

        self._init_game_context()
        self._allocate_simulated_data_memory()
        self._handle_injections()

        # start context sync
        self._workers[GAME_CONTEXT_SYNCHRONIZER] = asyncio.create_task(
            self._game_context_synchronizer.run()
        )

        # start operator
        self._workers[ENGINE_OPERATOR] = asyncio.create_task(
            self._operator.run()
        )

        print('Engine started', self.pid)

    async def stop(self) -> None:
        print(f'Stopping engine {self.pid}')
        self._shutdown_event.set()
        for worker in self._workers.values():
            worker.cancel()
        try:
            await asyncio.gather(*self._workers.values(), return_exceptions=True)
        except asyncio.CancelledError:
            pass

        self._restore_functions()
        self._deallocate_simulated_data_memory()

        self._started = False

        if self._game_hidden:
            self.toggle_game_visibility()

        print(f'Engine {self.pid} stopped')
