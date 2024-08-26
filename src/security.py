from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Optional
import uuid

import bcrypt
from fastapi import HTTPException
from fastapi import status
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.security import HTTPBearer
from jose import jwt
from jose import JWTError

from config import ALGORITHM
from config import PASSWORD_HASH
from config import SECRET_KEY
from config import USERNAME
from logger_config import setup_logger
from models import TokenData

active_tokens = {}

logger = setup_logger()

oauth2_scheme = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        result = bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
        logger.info(f"Password verification result: {result}")
        return result
    except ValueError as e:
        logger.error(f"Password verification failed: {e}")
        return False


def authenticate_user(username: str, password: str) -> Optional[str]:
    if username == USERNAME and verify_password(password, PASSWORD_HASH):
        logger.info(f"User authenticated: {username}")
        return username
    logger.warning(f"Authentication failed for user: {username}")
    return None


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    token_id = str(uuid.uuid4())
    to_encode.update({"jti": token_id})
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    active_tokens[to_encode["sub"]] = token_id

    logger.info("Access token created")
    return token


def decode_token(credentials: HTTPAuthorizationCredentials) -> TokenData:
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub", "")
        token_id: str = payload.get("jti", "")

        if not username or active_tokens.get(username) != token_id:
            raise credentials_exception

        logger.info("Token decoded successfully")
        return TokenData(username=username)
    except JWTError:
        logger.error("Token decoding failed")
        raise credentials_exception
