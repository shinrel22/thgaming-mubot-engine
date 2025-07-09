import pydantic
import uvicorn
import asyncio
from fastapi import FastAPI, HTTPException, Body, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic_core import PydanticUndefinedType

from src.bases.engines.data_models import EngineAutologinSettings
from src.constants import engine as engine_constants
from src.constants import trainer as trainer_constants
from src.bases.errors import Error
from src.bases.trainers.prototypes import RestfulServerPrototype


class RestfulServer(RestfulServerPrototype):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._api = FastAPI()

    async def _load_game_file(self, filepath: str = Body(embed=True)):
        try:
            result = await self.trainer.load_game_file(filepath)
        except Error as e:
            raise HTTPException(
                status_code=500,
                detail=e.output()
            )

        return result

    async def _get_server_info(self):
        game_server = None
        game_database = None

        if self.trainer.game_server:
            game_server = self.trainer.game_server.model_dump()
        if self.trainer.game_database:
            game_database = self.trainer.game_database.model_dump()

        return dict(
            game_server=game_server,
            game_database=game_database,
        )

    async def _get_engine_settings(self):
        if not self.trainer.game_server:
            raise HTTPException(
                status_code=400,
                detail=dict(message='Please load server game file first')
            )

        if self.trainer.engines:
            engine = list(self.trainer.engines.values())[0]
        else:
            engine = None

        try:
            settings = self.trainer.load_engine_settings(
                engine=engine,
            )

        except pydantic.ValidationError as e:
            raise HTTPException(
                status_code=400,
                detail=e.errors()
            )

        except Error as e:
            raise HTTPException(
                status_code=500,
                detail=e.output()
            )

        return settings

    async def _toggle_game_visibility(self):
        if not self.trainer.engines:
            raise HTTPException(
                status_code=400,
                detail={
                    'message': 'No engine found. Please start a game first.'
                }
            )

        engine = list(self.trainer.engines.values())[0]

        try:
            engine.toggle_game_visibility()

        except pydantic.ValidationError as e:
            raise HTTPException(
                status_code=400,
                detail=e.errors()
            )

        except Error as e:
            raise HTTPException(
                status_code=500,
                detail=e.output()
            )

        return dict(success=True)

    async def _get_player_skills(self):
        result = []
        if self.trainer.engines.values():
            engine = list(self.trainer.engines.values())[0]
            result = await engine.game_context_synchronizer.load_player_active_skills()
            result = list(result.values())
        return result

    async def _start_game(self,
                          autologin_settings: dict = Body(default_factory=dict, embed=True),
                          ):
        try:
            autologin_settings = EngineAutologinSettings(**autologin_settings)
        except pydantic.ValidationError:
            autologin_settings = None
        try:
            engine_id, engine = await self.trainer.start_engine(
                autologin_settings=autologin_settings
            )
        except Error as e:
            raise HTTPException(
                status_code=500,
                detail=e.output()
            )

        return self.trainer.parse_engine_data_for_client(engine_id, engine)

    def setup_exception_handlers(self):
        app = self._api

        @app.exception_handler(Exception)
        def handle_generic_err(_req: Request, exc: Exception) -> JSONResponse:
            """Handle generic errors."""
            self._logger.exception(exc)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=dict(
                    message=jsonable_encoder(
                        str(exc),
                        custom_encoder={
                            PydanticUndefinedType: lambda _: None,
                        },
                    ),
                    code='UnknownError',
                )
            )

        @app.exception_handler(Error)
        def handle_generic_err(_req: Request, exc: Error) -> JSONResponse:
            """Handle generic errors."""
            self._logger.exception(exc)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=jsonable_encoder(
                    exc.output(),
                    custom_encoder={
                        PydanticUndefinedType: lambda _: None,
                    },
                )
            )

        @app.exception_handler(RequestValidationError)
        def handle_rq_validation_err(
                _req: Request, exc: RequestValidationError
        ) -> JSONResponse:
            """Handle request validation errors."""
            self._logger.exception(exc)
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=dict(
                    message=jsonable_encoder(
                        exc.errors(),
                        custom_encoder={
                            PydanticUndefinedType: lambda _: None,
                        },
                    ),
                    code='BadRequestParams'
                ),
            )

    def setup_api(self):
        self._api.add_middleware(
            CORSMiddleware,
            allow_methods=['*'],
            allow_headers=['*'],
            allow_origins=[self.ui_origin],
            allow_credentials=True,
        )
        self._api.add_api_route(
            path='/get-constants',
            endpoint=self._get_constants,
            methods=['GET']
        )
        self._api.add_api_route(
            path='/load-game-file',
            endpoint=self._load_game_file,
            methods=['POST']
        )
        self._api.add_api_route(
            path='/get-server-info',
            endpoint=self._get_server_info,
            methods=['GET']
        )
        self._api.add_api_route(
            path='/get-engine-settings',
            endpoint=self._get_engine_settings,
            methods=['GET']
        )
        self._api.add_api_route(
            path='/get-player-skills',
            endpoint=self._get_player_skills,
            methods=['GET']
        )
        self._api.add_api_route(
            path='/start-game',
            endpoint=self._start_game,
            methods=['POST']
        )
        self._api.add_api_route(
            path='/update-engine-settings',
            endpoint=self._update_engine_settings,
            methods=['PATCH']
        )
        self._api.add_api_route(
            path='/start-training',
            endpoint=self._start_training,
            methods=['POST']
        )
        self._api.add_api_route(
            path='/stop-training',
            endpoint=self._stop_training,
            methods=['POST']
        )
        self._api.add_api_route(
            path='/toggle-game-visibility',
            endpoint=self._toggle_game_visibility,
            methods=['POST']
        )

    async def _get_constants(self):
        engine = dict()
        trainer = dict()

        for i in dir(engine_constants):
            if not i.isupper():
                continue
            engine[i] = getattr(engine_constants, i)

        for i in dir(trainer_constants):
            if not i.isupper():
                continue
            trainer[i] = getattr(trainer_constants, i)

        return dict(
            engine=engine,
            trainer=trainer
        )

    async def _start_training(self):
        if not self.trainer.engines:
            raise HTTPException(
                status_code=400,
                detail={
                    'message': 'No engine found. Please start a game first.'
                }
            )
        engine = list(self.trainer.engines.values())[0]
        try:
            await self.trainer.start_training(
                engine=engine,
            )

        except pydantic.ValidationError as e:
            raise HTTPException(
                status_code=400,
                detail=e.errors()
            )

        except Error as e:
            raise HTTPException(
                status_code=500,
                detail=e.output()
            )

        return dict(success=True)

    async def _stop_training(self):
        if not self.trainer.engines:
            raise HTTPException(
                status_code=400,
                detail={
                    'message': 'No engine found. Please start the game first.'
                }
            )
        engine = list(self.trainer.engines.values())[0]
        try:
            await self.trainer.stop_training(
                engine=engine,
            )

        except pydantic.ValidationError as e:
            raise HTTPException(
                status_code=400,
                detail=e.errors()
            )

        except Error as e:
            raise HTTPException(
                status_code=500,
                detail=e.output()
            )

        return dict(success=True)

    def _load_engine_settings(self):
        if not self.trainer.engines:
            raise HTTPException(
                status_code=400,
                detail={
                    'message': 'No engine found. Please start a game first.'
                }
            )

        engine = list(self.trainer.engines.values())[0]

        try:
            settings = self.trainer.load_engine_settings(
                engine=engine,
            )

        except pydantic.ValidationError as e:
            raise HTTPException(
                status_code=400,
                detail=e.errors()
            )

        except Error as e:
            raise HTTPException(
                status_code=500,
                detail=e.output()
            )

        return settings

    def _update_engine_settings(self,
                                settings: dict = Body(embed=True)
                                ):
        if not self.trainer.engines:
            raise HTTPException(
                status_code=400,
                detail={
                    'message': 'No engine found. Please start a game first.'
                }
            )
        engine = list(self.trainer.engines.values())[0]

        try:
            self.trainer.update_engine_settings(
                engine=engine,
                settings=settings
            )

        except pydantic.ValidationError as e:
            raise HTTPException(
                status_code=400,
                detail=e.errors()
            )

        except Error as e:
            raise HTTPException(
                status_code=500,
                detail=e.output()
            )

        return dict(success=True)

    def setup_server(self):
        config = uvicorn.Config(self._api, host='localhost', port=self.port)
        server = uvicorn.Server(config)
        self._server = server

    async def run(self):
        self.setup_api()
        self.setup_exception_handlers()
        self.setup_server()

        server_worker = asyncio.create_task(self._server.serve())

        while not self.trainer.shutdown_event.is_set():
            await asyncio.sleep(1)

        await server_worker
