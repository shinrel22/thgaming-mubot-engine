import aiohttp
import asyncio
import json
import time
from pydantic import PrivateAttr
from functools import wraps
from typing import Optional, Dict, ClassVar
from aiohttp import (ClientError, ClientConnectionError,
                     ClientConnectorError,
                     ClientResponseError, ClientTimeout, ClientResponse)

from src.utils.json_encoders import CustomJsonEncoder
from src.utils import get_now
from src.bases.models import BaseModel


def request_connection_handler(max_retry=2):
    def decorator(func):
        @wraps(func)
        async def handle(*args, **kwargs):
            retry_count = 0
            error = None
            while retry_count < max_retry:
                try:
                    response = await func(*args, **kwargs)
                    if response and response.status == 504:
                        raise ClientResponseError(
                            response.request_info,
                            response.history,
                            status=504,
                            message="Gateway Timeout"
                        )
                except (ClientConnectionError,
                        ClientConnectorError,
                        ClientError,
                        asyncio.TimeoutError,
                        ClientResponseError) as e:
                    error = e
                else:
                    return response  # Successful response

                # Exponential backoff if error or 504
                retry_count += 1
                await asyncio.sleep(retry_count ** 2)

            raise error if error else Exception("Max retries exceeded")

        return handle

    return decorator


class Response(BaseModel):
    status_code: int
    text: str

    def to_dict(self):
        return json.loads(self.text)


class BaseService(BaseModel):
    BASE_URL: ClassVar[str]

    _trace_id: str | None = PrivateAttr()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._trace_id = None

    @property
    def trace_id(self) -> str | None:
        return self._trace_id

    def set_trace_id(self, value):
        self._trace_id = value

    # @request_connection_handler(max_retry=2)
    async def _do_request(
            self,
            method: str,
            endpoint: str,
            files: Optional[Dict] = None,
            timeout: float = 50,  # Timeout in seconds
            disable_rq_logging: bool = False,
            disable_rs_logging: bool = False,
            **kwargs
    ) -> Response:
        url = self.BASE_URL + endpoint

        # Serialize kwargs using custom encoder
        kwargs = json.loads(json.dumps(kwargs, cls=CustomJsonEncoder))

        # Handle file uploads
        if files:
            form_data = aiohttp.FormData()
            # Handle regular form data
            if 'data' in kwargs:
                data = kwargs.pop('data')
                if isinstance(data, dict):
                    for key, value in data.items():
                        form_data.add_field(key, str(value))
                else:
                    form_data.add_field('data', data)

            # Handle files
            for key, value in files.items():
                if isinstance(value, tuple):
                    if len(value) == 2:
                        filename, fileobj = value
                        content_type = None
                    elif len(value) == 3:
                        filename, fileobj, content_type = value
                    else:
                        raise ValueError("File tuple must be (filename, fileobj) or (filename, fileobj, content_type)")
                    form_data.add_field(
                        key,
                        fileobj,
                        filename=filename,
                        content_type=content_type
                    )
                else:
                    form_data.add_field(key, value)

            # Remove conflicting parameters
            for param in ['json', 'data']:
                if param in kwargs:
                    del kwargs[param]
            kwargs['data'] = form_data

        # Log request
        if self._logger and self._trace_id and not disable_rq_logging:
            self._logger.info(dict(
                message=f'HTTP Request - {method} - {url}',
                asctime=get_now().isoformat(),
                trace_id=self._trace_id,
                type='HttpRq',
                meta=dict(
                    client=self.__class__.__name__,
                    method=method,
                    url=url,
                    payload=kwargs,
                ),
            ))

        # Create timeout object
        timeout_obj = ClientTimeout(total=timeout)
        start_time = time.monotonic()

        try:
            async with aiohttp.ClientSession(timeout=timeout_obj) as session:
                async with session.request(method, url, **kwargs) as async_response:

                    response = Response(
                        status_code=async_response.status,
                        text=await async_response.text(),
                    )

                    # Log response
                    if self._trace_id and self._logger and not disable_rs_logging:
                        self._logger.info(dict(
                            message=f'HTTP Response - {method} - {url}',
                            asctime=get_now().isoformat(),
                            trace_id=self._trace_id,
                            type='HttpRs',
                            meta=dict(
                                client=self.__class__.__name__,
                                method=method,
                                url=url,
                                status_code=response.status_code,
                                response=response.to_dict(),
                                response_time=time.monotonic() - start_time,
                            ),
                        ))

                    return response
        except Exception as e:
            elapsed = time.monotonic() - start_time
            if self._trace_id and self._logger and not disable_rs_logging:
                self._logger.info(dict(
                    message=f'HTTP Error - {method} - {url}',
                    asctime=get_now().isoformat(),
                    trace_id=self._trace_id,
                    type='HttpRs',
                    meta=dict(
                        client=self.__class__.__name__,
                        method=method,
                        url=url,
                        error=str(e),
                        response_time=elapsed,
                    ),
                ))
            raise
