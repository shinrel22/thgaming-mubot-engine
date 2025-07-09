import logging
from pydantic import BaseModel as _BaseModel, PrivateAttr, Field, EmailStr

from src.utils import logger


class BaseModel(_BaseModel):
    _logger: logging.Logger = PrivateAttr()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._logger = logger


class GaiaAuthentication(_BaseModel):
    account_id: str
    token: str
    email: EmailStr
    hardware_id: str
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


