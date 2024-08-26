from pydantic import BaseModel
from pydantic import Field

from logger_config import setup_logger

logger = setup_logger()


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str | None = None


class TokenRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class CommandPulse(BaseModel):
    id: str = Field(title="ID замка")  # noqa
    time_ms: int = Field(title="Время открытия/закрытия в миллисекундах", gt=0, default=1000)

    class Config:
        json_schema_extra = {"example": {"id": 1, "time_ms": 10000}}


class ResponsePulse(BaseModel):
    message: str

    class Config:
        json_schema_extra = {"example": {"message": "Locker # 1 opened and closed for 10 seconds"}}


class ResponseStatus(BaseModel):
    id: dict  # noqa

    class Config:
        json_schema_extra = {
            "example": {
                "id": {
                    1: {"status": True},
                    2: {"status": False},
                    3: {"status": "offline"},
                }
            }
        }


logger.info("MODELS: defined successfully")
