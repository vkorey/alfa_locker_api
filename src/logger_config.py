import datetime
import os
import sys
from typing import Any

from dotenv import load_dotenv
from loguru import logger

load_dotenv()

logger_initialized: bool = False


class Rotator:
    def __init__(self, *, size: float, at: datetime.time) -> None:
        now = datetime.datetime.now()
        self._size_limit: float = size
        self._time_limit: datetime.datetime = now.replace(hour=at.hour, minute=at.minute, second=at.second)

        if now >= self._time_limit:
            self._time_limit += datetime.timedelta(days=7)

    def should_rotate(self, message: Any, log_file: Any) -> bool:
        log_file.seek(0, 2)
        if log_file.tell() + len(message) > self._size_limit:
            return True
        excess = message.record["time"].timestamp() - self._time_limit.timestamp()
        if excess >= 0:
            elapsed_days = datetime.timedelta(seconds=excess).days
            self._time_limit += datetime.timedelta(days=elapsed_days + 1)
            return True
        return False


rotator: Rotator = Rotator(size=5e8, at=datetime.time(0, 0, 0))


def setup_logger() -> Any:
    global logger_initialized
    if not logger_initialized:
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        logger.add(
            sys.stdout,
            enqueue=True,
            level=log_level,
            format="{time:DD.MM.YYYY HH:mm:ss:SSSS} | {level: <8} | {message: <50} | {name}:{function}:{line}",
            colorize=True,
            backtrace=True,
        )
        logger.add(
            sys.stderr,
            enqueue=True,
            level="ERROR",
            format="{time:DD.MM.YYYY HH:mm:ss:SSSS} | {level: <8} | {message: <50} | {name}:{function}:{line}",
            colorize=True,
            backtrace=True,
        )
        logger_initialized = True
    return logger
