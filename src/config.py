import json
import os
from typing import Any, Dict

from dotenv import load_dotenv

from logger_config import setup_logger

logger = setup_logger()

load_dotenv()

SECRET_KEY: str = os.getenv("SECRET_KEY") or "0511e09a13eeb1b552b86fff313ad7c53fa0bb0828ce5df9fbd09b2faea4ade7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 14

USERNAME: str = os.getenv("USERNAME") or ""
PASSWORD_HASH: str = os.getenv("PASSWORD_HASH") or ""

if not USERNAME or not PASSWORD_HASH:
    logger.error("USERNAME and PASSWORD_HASH must be set in environment variables")
    raise ValueError("USERNAME and PASSWORD_HASH must be set in environment variables")

DEFAULT_CONFIG_FILENAME = "config.json"


def read_config_json(filename: str = DEFAULT_CONFIG_FILENAME) -> Dict[str, Any]:
    with open(filename) as jsonfile:
        config = json.load(jsonfile)
    logger.info("CONFIGURATION: loaded successfully")
    return config


CONFIG = read_config_json()
RELAYS_IP = list(CONFIG.keys())


logger.info("CONFIGURATION: loaded successfully")
