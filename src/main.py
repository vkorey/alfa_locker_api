from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any, AsyncGenerator, Dict

from fastapi import APIRouter
from fastapi import Depends
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import status
from fastapi.security import HTTPAuthorizationCredentials

from config import CONFIG
from logger_config import setup_logger
from models import CommandPulse
from models import ResponsePulse
from models import ResponseStatus
from models import TokenRequest
from models import TokenResponse
from relay import initialize_devices
from relay import pulse_lock
from relay import relaystatus
from security import authenticate_user
from security import create_access_token
from security import decode_token
from security import oauth2_scheme


logger = setup_logger()

description = """
Команды для управления замочной системой
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[Any, Any]:
    global devices
    devices = await initialize_devices(CONFIG)
    yield devices
    for device in devices.values():
        await device.disconnect()


app = FastAPI(
    title="Lockers API",
    description=description,
    lifespan=lifespan,
)
router_v1 = APIRouter(
    prefix="/api/v1",
)

devices: Dict[str, Any] = {}


@router_v1.post("/token", response_model=TokenResponse, summary="Method for getting access token")
async def login_for_access_token(form_data: TokenRequest) -> TokenResponse:
    user = authenticate_user(form_data.username, form_data.password)
    logger.info(f"User {form_data.username} attempted to login")
    if not user:
        logger.warning(f"Failed login attempt for user: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(days=14)
    logger.info(f"access_token_expires: {access_token_expires}")
    access_token = create_access_token(data={"sub": user}, expires_delta=access_token_expires)

    logger.info(f"User {user} get token successfully")
    return TokenResponse(access_token=access_token, token_type="bearer")


@router_v1.get("/users/me")
async def read_users_me(credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme)) -> dict:
    token_data = decode_token(credentials)
    logger.info(f"User {token_data.username} accessed protected route")
    return {"username": token_data.username}


@router_v1.post(
    "/pulse",
    tags=["Open"],
    description=("Открытие замка, и автоматическое " "закрытие через заданное время. " "ID устройства и время задаются в запросе."),
    response_model=ResponsePulse,
)
async def pulse(command: CommandPulse, credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme)) -> dict:
    token_data = decode_token(credentials)
    logger.info(f"Unlocking lock with ID: {command.id} by user {token_data.username}")
    await pulse_lock(devices, command.id)
    return {"message": f"Locker # {command.id} opened"}

@app.get("/health")
async def health_check():
    return {"status": "OK"}

@app.get("/ready")
async def readiness_check():
    return {"status": "OK"}

@router_v1.get(
    "/status",
    tags=["Status"],
    description=("Получить статус локеров тип C. " "True - закрыт, False - открыт, null - оффлайн. " "Будет возвращен статус всех замков в системе."),
    response_model=ResponseStatus,
)
async def lock_status(credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme)) -> dict:
    token_data = decode_token(credentials)
    logger.info(f"User {token_data.username} is checking lock status")
    return await relaystatus(devices)




app.include_router(router_v1)
