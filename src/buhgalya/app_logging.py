"""Safe application logging configuration."""

import logging
import sys
from pathlib import Path

from loguru import logger

from buhgalya.config import get_settings


class InterceptHandler(logging.Handler):
    """Forward standard-library logs, including Uvicorn logs, to Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())


def configure_logging() -> None:
    """Configure colored console logs and rotated persistent file logs."""
    logger.remove()
    settings = get_settings()
    common = dict(
        level=settings.log_level.upper(),
        backtrace=False,
        diagnose=False,
        enqueue=True,
    )
    logger.add(
        sys.stderr,
        **common,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level:<8}</level> | "
            "<cyan>{name}:{function}:{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )
    log_dir = Path(settings.log_dir)
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_dir / "buhgalya_{time:YYYY-MM-DD}.log",
            **common,
            format=(
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | "
                "{name}:{function}:{line} | {message}"
            ),
            rotation="10 MB",
            retention="14 days",
            compression="zip",
        )
    except OSError:
        # Logging to stderr must remain available if the optional file volume is unavailable.
        logger.warning("Could not initialize file logging in {}", log_dir)
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
