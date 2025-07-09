import asyncio

from pydantic import PrivateAttr

from src.bases.engines import Engine
from src.utils import assembly_to_bytes, bytes_to_assembly
from src.bases.engines.data_models import SimulatedDataMemoryFunc, FuncCallback
from src.utils.type_parsers.csharp import CSharpTypeParser
from src.bases.errors import Error
from src.constants.engine import GAME_CHAR_SELECTION_SCREEN, GAME_PLAYING_SCREEN, GAME_LOGIN_SCREEN

from .game_context_synchronizers import UnityMegaMUEngineGameContextSynchronizer
from .game_action_handlers import UnityMegaMUEngineGameActionHandler
from .operators import UnityMegaMUEngineOperator
from .data_models import (
    UnityMegaMUViewport,
    UnityMegaMUSettings,
    UnityMegaMUChatFrame,
    UnityMegaMUGameContext,
    UnityMegaMUEngineMeta,
    UnityMegaMUSimulatedDataMemory,
    UnityMegaMUSimulatedFuncParams,
)


class UnityMegaMUEngine(Engine):
    settings: UnityMegaMUSettings
    meta: UnityMegaMUEngineMeta

    _game_context_synchronizer: UnityMegaMUEngineGameContextSynchronizer = PrivateAttr()
    _game_context: UnityMegaMUGameContext = PrivateAttr()
    _game_action_handler: UnityMegaMUEngineGameActionHandler = PrivateAttr()
    _operator: UnityMegaMUEngineOperator = PrivateAttr()
    _simulated_data_memory: UnityMegaMUSimulatedDataMemory = PrivateAttr()
    _cs_type_parser: CSharpTypeParser = PrivateAttr()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._cs_type_parser = CSharpTypeParser(
            h_process=self.h_process,
            pid=self.pid,
            os_api=self.os_api,
        )

    @property
    def cs_type_parser(self) -> CSharpTypeParser:
        return self._cs_type_parser

    def _init_game_action_handler(self) -> UnityMegaMUEngineGameActionHandler:
        return UnityMegaMUEngineGameActionHandler(engine=self)

    def _init_game_context(self) -> UnityMegaMUGameContext:
        self._game_context = UnityMegaMUEngineGameContextSynchronizer.init_context(engine=self)
        return self._game_context

    def _init_game_context_synchronizer(self) -> UnityMegaMUEngineGameContextSynchronizer:
        return UnityMegaMUEngineGameContextSynchronizer(engine=self)

    def _init_operator(self) -> UnityMegaMUEngineOperator:
        return UnityMegaMUEngineOperator(engine=self)

    def _init_simulated_data_memory(self) -> UnityMegaMUSimulatedDataMemory:
        game_func_params: dict[str, int] = {}
        for field_name in UnityMegaMUSimulatedFuncParams.model_fields.keys():
            game_func_params[field_name] = 0

        game_funcs = {}

        for func_code, game_func in self.game_funcs.items():
            callbacks = dict()
            triggers = dict()
            for trigger_code in game_func.triggers.keys():
                triggers[trigger_code] = 0
            for callback_code in game_func.callbacks.keys():
                callbacks[callback_code] = 0

            game_funcs[func_code] = SimulatedDataMemoryFunc(
                callbacks=callbacks,
                triggers=triggers,
            )

        return UnityMegaMUSimulatedDataMemory(
            ptr_base=0,
            game_func_params=UnityMegaMUSimulatedFuncParams(**game_func_params),
            game_funcs=game_funcs,
        )

    def _gen_trigger(self,
                     prototype: str,
                     without_ret: bool = False,
                     stack_size: int = 0x28,
                     params: dict = None
                     ) -> bytes:

        if not params:
            params = dict()

        ## Assembly code preparation
        stubs = ['start:']

        if stack_size:
            stubs.append(f'sub rsp, {stack_size}')

        trigger_main_func = prototype.format(**params)
        stubs.append(trigger_main_func)

        stubs.append('end:')

        if stack_size:
            stubs.append(f'add rsp, {stack_size}')

        if not without_ret:
            stubs.append('ret')

        trigger_asm_code = '\n'.join(stubs)
        trigger = assembly_to_bytes(
            asm_code=trigger_asm_code
        )
        return trigger

    def _gen_callback(
            self,
            func_code: str,
            func_callback: FuncCallback,
            func_callback_addr: int,
            func_addr: int,
            params: dict = None
    ) -> tuple[bytes, bytes, bytes]:
        if not params:
            params = dict()

        func = self.game_funcs[func_code]

        patching_prototype = [
            f'mov r15, {func_callback_addr}',
            'jmp r15'
        ]

        patching_bytes = assembly_to_bytes('\n'.join(patching_prototype))
        patching_length = len(patching_bytes)

        num_of_opcodes_to_patch = 0
        current_length = 0
        for bytecode in func.bytecodes:
            current_length += int(len(bytecode.replace(' ', '')) / 2)
            num_of_opcodes_to_patch += 1
            if current_length >= patching_length:
                break

        num_of_padding_bytes = current_length - patching_length
        if num_of_padding_bytes:
            for i in range(num_of_padding_bytes):
                patching_prototype.append('nop')

        patching_bytes = assembly_to_bytes('\n'.join(patching_prototype))
        patching_length = len(patching_bytes)

        asm_callback_codes = [
            'cache_registers:',
            '   push rax',
            '   push rbx',
            '   push rcx',
            '   push rdx',
            '   push rsi',
            '   push rdi',
            '   push rbp',
            '   push r8',
            '   push r9',
            '   push r10',
            '   push r11',
            '   push r12',
            '   push r13',
            '   push r14',
            '   push r15',
            '   mov r15, {ptr_rsp_cache}',
            '   mov [r15], rsp',

            func_callback.prototype,

            'restore_registers:',
            '    mov r15, {ptr_rsp_cache}',
            '    mov rsp, [r15]',
            '    pop r15',
            '    pop r14',
            '    pop r13',
            '    pop r12',
            '    pop r11',
            '    pop r10',
            '    pop r9',
            '    pop r8',
            '    pop rbp',
            '    pop rdi',
            '    pop rsi',
            '    pop rdx',
            '    pop rcx',
            '    pop rbx',
            '    pop rax',
        ]

        original_bytes = self.os_api.read_memory(
            h_process=self.h_process,
            address=func_addr,
            size=patching_length
        )

        asm_simulated_original_codes = [
            'handle_original_logic:'
        ]
        for ins in bytes_to_assembly(original_bytes, offset=func_addr):
            ins_opcode = f'{ins.mnemonic} {ins.op_str}'
            if 'rip' in ins_opcode:
                asm_simulated_original_codes.append(
                    f'mov r15, {ins.address + ins.size}'
                )
                ins_opcode = ins_opcode.replace('rip', 'r15')
            asm_simulated_original_codes.append(ins_opcode)
        asm_simulated_original_codes.extend([
            f'mov r15, {func_addr + patching_length}',  # return address
            'jmp r15'
        ])
        asm_callback_codes.extend(asm_simulated_original_codes)
        callback_bytes = assembly_to_bytes('\n'.join(asm_callback_codes).format(**params))

        return original_bytes, patching_bytes, callback_bytes

    def _gen_patches(self,
                      func_addr: int,
                      func_code: str,
                      prototype: str,
                      params: dict = None,
                      ) -> tuple[bytes, bytes]:
        if not params:
            params = dict()

        patching_code = prototype.format(**params)
        patching_bytes = assembly_to_bytes(patching_code)

        patching_length = len(patching_bytes)

        func = self.game_funcs[func_code]

        bytecodes = ''.join(func.bytecodes).replace(' ', '')
        func_length = int(len(bytecodes) / 2)

        paddings = func_length - patching_length
        if paddings:
            for i in range(paddings):
                patching_bytes += assembly_to_bytes('nop')

        origin_bytes = self.os_api.read_memory(
            h_process=self.h_process,
            address=func_addr,
            size=func_length
        )

        return origin_bytes, patching_bytes

    def _handle_injections(self) -> None:
        base_module_addr = self.game_modules[self.meta.game_assembly_dll]

        func_offsets = self.func_offsets

        game_func_params = self._simulated_data_memory.game_func_params.model_dump()
        game_func_params.update(self.meta.model_dump())

        for func_code, game_func in self.game_funcs.items():
            gf_offset = func_offsets.get(func_code)
            if not gf_offset:
                raise Error(
                    message=f'Missing func offset for: {func_code}'
                )
            game_func_addr = base_module_addr + gf_offset
            func_params = dict(
                game_func=game_func_addr
            )
            func_params.update(game_func_params)

            for trigger_code, trigger_data in game_func.triggers.items():
                trigger_addr = self._simulated_data_memory.game_funcs[func_code].triggers[trigger_code]
                trigger = self._gen_trigger(
                    prototype=trigger_data.prototype,
                    without_ret=trigger_data.without_ret,
                    stack_size=trigger_data.stack_size,
                    params=func_params,
                )
                self.os_api.write_memory(
                    h_process=self.h_process,
                    address=trigger_addr,
                    data=trigger
                )

            for callback_code, callback_data in game_func.callbacks.items():
                callback_addr = self._simulated_data_memory.game_funcs[func_code].callbacks[callback_code]
                original_bytes, patching_bytes, callback_bytes = self._gen_callback(
                    func_callback=callback_data,
                    func_addr=game_func_addr,
                    func_callback_addr=callback_addr,
                    params=func_params,
                    func_code=func_code,
                )
                # inject callback
                self.os_api.write_memory(
                    h_process=self.h_process,
                    address=callback_addr,
                    data=callback_bytes
                )
                # patch original func
                self.os_api.write_memory(
                    h_process=self.h_process,
                    address=game_func_addr + callback_data.offset,
                    data=patching_bytes
                )
                self._original_codes[game_func_addr] = original_bytes

            for patching_name, patching_data in game_func.patches.items():
                patching_addr = game_func_addr + patching_data.offset

                origin, patching = self._gen_patches(
                    func_code=func_code,
                    func_addr=game_func_addr,
                    prototype=patching_data.prototype,
                    params=func_params
                )

                self._original_codes[patching_addr] = origin

                self.os_api.write_memory(
                    h_process=self.h_process,
                    address=patching_addr,
                    data=patching
                )

    async def _disable_default_autologin(self):
        while not self._game_context or not self._game_context.addr:
            await asyncio.sleep(0.1)

        autologin_addr = self.os_api.get_value_from_pointer(
            h_process=self.h_process,
            pointer=self._game_context.addr + self.meta.autologin_offset,
        )
        while not autologin_addr:
            await asyncio.sleep(0.1)
            autologin_addr = self.os_api.get_value_from_pointer(
                h_process=self.h_process,
                pointer=self._game_context.addr + self.meta.autologin_offset,
            )
        for flag_offset in self.meta.autologin_flag_offsets:
            self.os_api.write_memory(
                h_process=self.h_process,
                address=autologin_addr + flag_offset,
                data=(0).to_bytes(1, 'little'),
            )

    async def _handle_autologin(self):
        while not self._game_context or not self._game_context.addr or not self._game_context.screen:
            await asyncio.sleep(1)

        login_screen_id = self.meta.screen_mappings[GAME_LOGIN_SCREEN]

        while (not self._game_context.login_screen
               or not self._game_context.screen.screen_id == login_screen_id
               or not self._game_context.channels):
            await asyncio.sleep(1)

        self._game_action_handler.login_screen_submit_credential(
            username=self.autologin_settings.username,
            password=self.autologin_settings.password,
        )

        await asyncio.sleep(1)

        while self._game_context.login_screen.login_locked:
            await asyncio.sleep(1)

        server_response = self._game_context.login_screen.server_response
        if not server_response.get('Success'):
            return None
        print('server_response', server_response)
        print('self._game_context.login_screen.current_state', self._game_context.login_screen.current_state)

        # wrong credential or connection issue, ...
        if self._game_context.login_screen.current_state != 3:
            await asyncio.sleep(1)
            if self._game_context.current_dialog and self._game_context.current_dialog.window.is_open:
                if self._game_context.current_dialog.title in [
                    'NO CONNECTION',
                    'ERROR'
                ]:
                    self._game_action_handler.close_window(
                        self._game_context.current_dialog.window
                    )
                    await asyncio.sleep(1)
                    return await self._handle_autologin()
            self._logger.error(f'Failed to login: {self._game_context.login_screen.model_dump()}')
            return None

        target_channel = self._game_context.channels.get(
            self.autologin_settings.channel_id
        )

        if not target_channel:
            # get the first channel
            target_channel = self._game_context.channels.get(0)

        if not target_channel:
            return None

        print('target_channel', target_channel)

        while target_channel.current_load >= 1:
            print('target_channel.current_load', target_channel.current_load)
            await asyncio.sleep(0.1)
            target_channel = self._game_context.channels.get(target_channel.id)

        self._game_action_handler.login_screen_select_channel(target_channel.id)
        await asyncio.sleep(1)

        char_selection_screen_id = self.meta.screen_mappings[GAME_CHAR_SELECTION_SCREEN]
        attempts = 0
        print('self._game_context.screen.screen_id', self._game_context.screen.screen_id)
        while not self._game_context.screen.screen_id == char_selection_screen_id:
            if attempts > 5:
                self._logger.error(f'Failed to login: {self._game_context.screen}')
                return None
            await asyncio.sleep(1)
            attempts += 1

        while not self._game_context.lobby_screen:
            await asyncio.sleep(1)

        print('character_slots', self._game_context.lobby_screen.character_slots)

        if not self._game_context.lobby_screen.character_slots:
            return None

        character_slot = self._game_context.lobby_screen.character_slots.get(
            self.autologin_settings.character_name.lower().strip(),
        )

        if character_slot is None:
            return None

        print('character_slot', character_slot)
        await asyncio.sleep(1)
        self._game_action_handler.lobby_screen_select_character(character_slot)
        await asyncio.sleep(1)

        attempts = 0
        game_player_screen_id = self.meta.screen_mappings[GAME_PLAYING_SCREEN]
        while not self._game_context.screen.screen_id == game_player_screen_id:
            if attempts > 5:
                self._logger.error(f'Failed to login: {self._game_context.screen}')
                return None
            await asyncio.sleep(1)

        if self.autologin_settings.start_training_after:
            while not self._game_context.local_player:
                await asyncio.sleep(1)
            await self.start_training()

        self._logger.info('Autologin successfully')
        return None

    async def start(self):
        await super().start()

        # disable game's default autologin behavior
        self._workers[
            self._disable_default_autologin.__name__
        ] = asyncio.create_task(self._disable_default_autologin())

        if self.autologin_settings and self.autologin_settings.enabled:
            # start auto login handler
            self._workers[
                self._handle_autologin.__name__
            ] = asyncio.create_task(self._handle_autologin())
