import asyncio
import concurrent.futures
import json
import os.path
import subprocess
from pydantic import Field, PrivateAttr
from pathlib import Path

from src.bases.trainers.prototypes import TrainerPrototype, Message
from src.constants.trainer import (
    ENGINE_TERMINATION_WS_MSG_TYPE, STARTING_ENGINE_PROGRESS_WS_MSG_TYPE
)
from src.bases.engines.data_models import EngineAutologinSettings, GameFunction
from src.bases.engines.prototypes import EnginePrototype
from src.os.windows import WindowsAPI
from src.bases.errors import Error
from src.bases.engines import EngineMeta, GameServer, GameDatabase, EngineSettings
from src.engines.unity_megamu import UnityMegaMUEngine, UnityMegaMUEngineMeta, UnityMegaMUSettings
from src.constants.engine.unity_megamu import FUNC_ADD_STATS
from src.constants import DATA_DIR, TMP_DIR
from src.utils import scan_string, compress_data, decompress_data, hex_string_to_int_list, load_data_file
from config import ENVIRONMENT, ROOT_DIR, SECRET_KEY

from .restful_servers import RestfulServer
from .websocket_servers import WebsocketServer


class Trainer(TrainerPrototype):
    engines: dict[int, EnginePrototype | UnityMegaMUEngine] = Field(default_factory=dict)

    _engine_meta: EngineMeta | UnityMegaMUEngineMeta | None = PrivateAttr()
    _engine_settings: EngineSettings | UnityMegaMUSettings | None = PrivateAttr()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._shutdown_event = asyncio.Event()
        self._os_api = WindowsAPI()

        self._game_server = None
        self._game_database = None
        self._event_loop = None

        self._restful_server = RestfulServer(
            trainer=self,
            port=self.restful_server_port,
            ui_origin=self.ui_origin
        )
        self._websocket_server = WebsocketServer(
            trainer=self,
            port=self.websocket_server_port
        )

        self._workers = {}

    async def shutdown(self):
        print("Shutting down trainer")
        self._shutdown_event.set()

        for worker in self._workers.values():
            worker.cancel()
        try:
            await asyncio.gather(*self._workers.values(), return_exceptions=True)
        except asyncio.CancelledError:
            pass

        for pid, engine in self.engines.items():
            await engine.stop()
            del self.engines[pid]

            self._os_api.terminate_process(engine.h_process)

    def _load_game_database(self) -> GameDatabase:
        data = {}
        for k in GameDatabase.model_fields.keys():
            filepath = os.path.join(
                DATA_DIR,
                self._game_server.code,
                f'{k}.json'
            )
            value = load_data_file(filepath)

            data[k] = value

        return GameDatabase(**data)

    def update_engine_settings(self, engine: EnginePrototype, settings: dict):
        engine.settings = engine.settings.__class__(**settings)
        self._save_engine_settings(engine)

    def _make_engine_setting_filepath(self, engine: EnginePrototype) -> str:
        filepath = os.path.join(
            TMP_DIR,
            self._game_server.code,
            'settings',
            f'{engine.game_context.local_player.name}.json',
        )
        return filepath

    def _load_default_settings(self) -> dict:
        filepath = os.path.join(
            DATA_DIR,
            self._game_server.code,
            'default_settings.json',
        )

        return load_data_file(filepath)

    def load_engine_settings(self, engine: EnginePrototype = None) -> dict:
        data = self._load_default_settings()
        if not engine or not engine.game_context or not engine.game_context.local_player:
            return EngineSettings(**data).model_dump()

        filepath = self._make_engine_setting_filepath(engine)

        if os.path.exists(filepath):
            data = json.load(open(filepath))

        return EngineSettings(**data).model_dump()

    def _save_engine_settings(self, engine: EnginePrototype):
        if not engine.game_context.local_player:
            return

        filepath = self._make_engine_setting_filepath(engine)
        file_dir = os.path.dirname(filepath)
        os.makedirs(file_dir, exist_ok=True)

        with open(filepath, 'w') as fw:
            fw.write(engine.settings.model_dump_json())

    def _handle_process_terminated(self, pid: int):
        print("Process terminated", pid)
        engine = self.engines[pid]
        del self.engines[pid]
        if self._event_loop:
            asyncio.run_coroutine_threadsafe(engine.stop(), self._event_loop)
            asyncio.run_coroutine_threadsafe(self._websocket_server.send_message(
                client_connection=self._websocket_server.client_connection,
                message=Message(
                    type=ENGINE_TERMINATION_WS_MSG_TYPE,
                    data=dict(engine_id=pid)
                )
            ), self._event_loop)

    async def _dump_il2cpp(self,
                           filepath: str,
                           meta_filepath: str,
                           output_filepath: str) -> str:
        dumper = os.path.join(ROOT_DIR, 'Il2CppDumper', 'run.exe')

        def handle():

            output_dir = os.path.dirname(output_filepath)

            dump_result_filepath = os.path.join(
                output_dir,
                'script.json'
            )

            dumping_result = subprocess.run(
                [dumper, filepath, meta_filepath, output_dir],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if not os.path.exists(dump_result_filepath):
                raise Error(
                    code='FailedToDumpIl2cpp',
                    message=dumping_result
                )

            with open(dump_result_filepath, 'r') as fr:
                dump_data = json.load(fr)

            with open(output_filepath, 'w') as fw:
                for func_struct in dump_data['ScriptMethod']:
                    func_name = func_struct['Name']

                    if func_name.startswith('System.'):
                        continue

                    if func_name.startswith('UnityEngine.'):
                        continue

                    if func_name.startswith('XInputDotNetPure.'):
                        continue

                    if func_name.startswith('CodeStage.AntiCheat.'):
                        continue

                    if func_name.startswith('HorizonBasedAmbientOcclusion.'):
                        continue

                    if func_name.startswith('QFX.IFX.'):
                        continue

                    if func_name.startswith('MagicalFX.'):
                        continue

                    if func_name.startswith('Facebook.'):
                        continue

                    if func_name.startswith('Sirenix.'):
                        continue

                    if func_name.startswith('Unity.'):
                        continue

                    if func_name.startswith('Org.'):
                        continue

                    if func_name.startswith('Newtonsoft.'):
                        continue

                    if func_name.startswith('UnityEngineInternal.'):
                        continue

                    if func_name.startswith('I18N.'):
                        continue

                    if func_name.startswith('EnableDepthBuffer$$'):
                        continue

                    if func_name.startswith('ProductRowPrefab$$'):
                        continue

                    if func_name.startswith('PurchaseRowPrefab$$'):
                        continue

                    if func_name.startswith('ARPGFX.ARPGFXRotation$$'):
                        continue

                    offset = func_struct['Address']
                    signature = func_struct['Signature']
                    fw.write(
                        json.dumps({
                            'signature': signature,
                            'offset': offset,
                            'name': func_name,
                        }) + '\n'
                    )

            return output_filepath

        return handle()

    async def load_game_file(self, filepath: str):
        file_parser = Path(filepath)
        filename = file_parser.name
        filedir = str(file_parser.parent.absolute())

        if filename == 'MEGAMU.exe':
            gs_name = 'MegaMU'
            gs_code = 'MegaMU'
            game_assembly_filepath = os.path.join(filedir, 'bin\\GameAssembly.dll')
            # Unity version
            if os.path.exists(
                    game_assembly_filepath
            ):
                gs_version = 'Unity'
                target_filepath = os.path.join(filedir, f'bin\\{filename}')
                file_version = self._os_api.get_file_version(target_filepath)
                if not file_version:
                    raise Error(message='Failed to load file version')

                il2cpp_meta_filepath = os.path.join(
                    filedir,
                    'bin',
                    'MEGAMU_Data',
                    'il2cpp_data',
                    'MetaData',
                    'global-metadata.dat'
                )
                cache_dir = os.path.join(
                    TMP_DIR,
                    gs_code,
                    gs_version,
                    file_version
                )
                os.makedirs(cache_dir, exist_ok=True)

                il2cpp_dump_dir = os.path.join(
                    cache_dir,
                    'il2cpp_dumps'
                )
                os.makedirs(il2cpp_dump_dir, exist_ok=True)
                func_struct_filepath = os.path.join(
                    il2cpp_dump_dir,
                    'func_structs.jsonl'
                )

                if not os.path.exists(func_struct_filepath):
                    await self._dump_il2cpp(
                        filepath=game_assembly_filepath,
                        meta_filepath=il2cpp_meta_filepath,
                        output_filepath=func_struct_filepath
                    )

                self._game_server = GameServer(
                    name=gs_name,
                    code=gs_code,
                    version=gs_version,
                    patch_version=file_version,
                    filepath=filepath,
                    target_filepath=target_filepath,
                    game_assembly_filepath=game_assembly_filepath,
                    il2cpp_meta_filepath=il2cpp_meta_filepath,
                    il2cpp_dump_dir=il2cpp_dump_dir,
                    func_struct_filepath=func_struct_filepath,
                    filename=filename,
                    filedir=filedir,
                    cache_dir=cache_dir,
                    has_rr_system=True,
                    max_rr=200,
                    potion_cooldown=10
                )

                self._game_database = self._load_game_database()

        else:
            raise Error(
                code='UnsupportedVersion',
                message='Version is not supported yet'
            )

        if not self._game_server or not self._game_database:
            raise Error(
                code='UnsupportedVersion',
                message='Version is not supported yet'
            )

        return dict(
            game_server=self._game_server.model_dump(),
            game_database=self._game_database.model_dump(),
        )

    @staticmethod
    def parse_engine_data_for_client(engine_id: int, engine: EnginePrototype) -> dict:
        result: dict = {
            'engine_id': engine_id,
            'engine': {
                'mode': engine.mode,
                'game_hidden': engine.game_hidden,
            },
            'stat_mappings': engine.meta.stat_mappings,
            'screen_mappings': engine.meta.screen_mappings,
        }

        if engine.game_context:
            result['channel_id'] = engine.game_context.channel_id

            if engine.game_context.screen:
                result['screen'] = engine.game_context.screen.model_dump()

            if engine.game_context.local_player:
                result['player'] = engine.game_context.local_player.model_dump()

            if engine.game_context.viewport:
                result['viewport'] = engine.game_context.viewport.model_dump()

            if engine.game_context.player_inventory:
                result['player_inventory'] = engine.game_context.player_inventory.model_dump()

            if engine.game_context.party_manager:
                result['party_manager'] = engine.game_context.party_manager.model_dump()

        return result

    async def start_training(self, engine: EnginePrototype):
        await engine.start_training()

    async def stop_training(self, engine: EnginePrototype):
        await engine.stop_training()

    async def _load_game_modules(self, pid: int, wait_for_modules: list[str] = None) -> dict:
        modules = self.os_api.list_modules(pid=pid)

        if wait_for_modules:
            for module in wait_for_modules:
                while module not in modules:
                    await asyncio.sleep(1)
                    modules = self.os_api.list_modules(pid=pid)

        return modules

    async def start_engine(self,
                           autologin_settings: EngineAutologinSettings = None
                           ) -> tuple[int, EnginePrototype | UnityMegaMUEngine]:
        if not self._game_server or not self._game_database:
            raise Error(
                code='ServerInfoNotLoadedYet',
                message='Server info is not loaded'
            )

        first_time = False

        func_offsets = dict()
        func_offset_filepath = os.path.join(
            self._game_server.cache_dir,
            'func_offsets.dat'
        )
        if os.path.exists(func_offset_filepath):
            with open(func_offset_filepath, 'rb') as rf:
                func_offsets = json.loads(
                    decompress_data(rf.read(), encryption_key=SECRET_KEY)
                )
        else:
            first_time = True

        if self._game_server.code == 'MegaMU':
            if self._game_server.version == 'Unity':
                if ENVIRONMENT == 'PRD':
                    meta_filepath = os.path.join(
                        DATA_DIR,
                        self._game_server.code,
                        self._game_server.version,
                        'meta.json'
                    )
                    game_func_filepath = os.path.join(
                        DATA_DIR,
                        self._game_server.code,
                        self._game_server.version,
                        'game_funcs.json'
                    )
                    game_functions = load_data_file(game_func_filepath)
                    engine_meta = UnityMegaMUEngineMeta(**load_data_file(meta_filepath))

                else:
                    from tmp.MegaMU.Unity.meta import DevUnityMegaMUEngineMeta
                    from tmp.MegaMU.Unity.game_funcs import GAME_FUNCTIONS

                    engine_meta = DevUnityMegaMUEngineMeta()
                    game_functions = GAME_FUNCTIONS

                process = subprocess.Popen([self._game_server.target_filepath])

                # Get the PID
                pid = process.pid
                h_process = self._os_api.get_h_process(pid)

                game_assembly_module_name = 'GameAssembly.dll'

                game_modules = await self._load_game_modules(pid, wait_for_modules=[
                    game_assembly_module_name
                ])

                self._os_api.suspend_all_threads(pid)

                func_struct_filepath = self._game_server.func_struct_filepath
                func_structs = dict()
                with open(func_struct_filepath, 'r') as rf:
                    for line in rf:
                        if not line:
                            continue
                        func_struct = json.loads(line)
                        func_structs[func_struct['signature']] = func_struct

                total_funcs = len(game_functions)
                scanned_funcs = 0

                for f_code, f in game_functions.items():

                    gf = GameFunction(**f)

                    if f_code in func_offsets:
                        scanned_funcs += 1
                        continue

                    target_scan_results = 1
                    if f_code == FUNC_ADD_STATS:
                        target_scan_results = 3

                    offsets_to_check = []

                    if gf.signature_pattern:
                        for f_signature, f_struct in func_structs.items():
                            f_offset = f_struct['offset']

                            if f_signature == gf.signature_pattern:
                                offsets_to_check.append(f_offset)
                                break

                            if f_signature == gf.signature_pattern:
                                offsets_to_check.append(f_offset)
                                break

                            if not scan_string(f_signature, gf.signature_pattern):
                                continue

                            offsets_to_check.append(f_offset)

                    game_assembly_module_addr = game_modules[game_assembly_module_name]

                    scan_results = []

                    if len(offsets_to_check) == 1:
                        scan_results.append(offsets_to_check[0] + game_assembly_module_addr)
                    else:
                        if offsets_to_check:
                            gf_length = len(hex_string_to_int_list(
                                ''.join(gf.bytecodes)
                            ))
                            for otc in offsets_to_check:
                                srs = await self._event_loop.run_in_executor(
                                    concurrent.futures.ThreadPoolExecutor(),
                                    self._os_api.scan_memory,
                                    h_process,
                                    gf.bytecodes,
                                    game_assembly_module_addr + otc,
                                    game_assembly_module_addr + otc + (gf_length * 2),
                                )
                                if srs:
                                    scan_results.append(srs[0])
                        else:
                            game_assembly_filesize = os.path.getsize(self._game_server.game_assembly_filepath)
                            scan_results = await self._event_loop.run_in_executor(
                                concurrent.futures.ThreadPoolExecutor(),
                                self._os_api.scan_memory,
                                h_process,
                                gf.bytecodes,
                                game_assembly_module_addr,
                                game_assembly_module_addr + game_assembly_filesize,
                                target_scan_results
                            )

                    if not scan_results or len(scan_results) < target_scan_results:
                        raise Error(
                            code='FailedToScanFunction',
                            message=f'Failed to scan function: {f_code}, scan results: {len(scan_results)}'
                        )
                    func_offsets[f_code] = scan_results[-1] - game_assembly_module_addr
                    scanned_funcs += 1

                    await self._websocket_server.send_message(
                        self._websocket_server.client_connection,
                        message=Message(
                            type=STARTING_ENGINE_PROGRESS_WS_MSG_TYPE,
                            data=dict(
                                progress=scanned_funcs / total_funcs,
                                first_time=first_time
                            )
                        )
                    )

                engine = UnityMegaMUEngine(
                    autologin_settings=autologin_settings,
                    game_server=self._game_server,
                    game_database=self._game_database,
                    h_process=h_process,
                    pid=pid,
                    os_api=self._os_api,
                    meta=engine_meta,
                    settings=UnityMegaMUSettings(**self._load_default_settings()),
                    func_offsets=func_offsets,
                    game_modules=game_modules,
                    game_funcs=game_functions,
                )
            else:
                raise Error(
                    code='UnsupportedGameServerVersion',
                    message=f'Unsupported game server: {self._game_server.version}'
                )

        else:
            raise Error(
                code='UnsupportedGameServer',
                message=f'Unsupported game server: {self._game_server.code}'
            )

        self._os_api.set_process_termination_callback(
            h_process=h_process,
            callback=self._handle_process_terminated,
            context=pid
        )

        self.engines[pid] = engine

        await engine.start()

        self._os_api.resume_all_threads(pid)

        await self._websocket_server.send_message(
            self._websocket_server.client_connection,
            message=Message(
                type=STARTING_ENGINE_PROGRESS_WS_MSG_TYPE,
                data=dict(progress=1, first_time=first_time)
            )
        )

        with open(func_offset_filepath, 'wb') as wf:
            wf.write(compress_data(
                json.dumps(func_offsets).encode(),
                encryption_key=SECRET_KEY
            ))

        return pid, engine

    def _start_workers(self):
        pass

    async def run(self):
        self._event_loop = asyncio.get_event_loop()
        self._shutdown_event.clear()

        self._start_workers()

        websocket_server_worker = asyncio.create_task(self._websocket_server.run())
        restful_server_worker = asyncio.create_task(self._restful_server.run())

        while not self._shutdown_event.is_set():
            await asyncio.sleep(1)

        await websocket_server_worker
        await restful_server_worker
