"""Logging to the console and a rotating file in the data directory."""

import logging
from logging.handlers import RotatingFileHandler

from jarvis.core.config import Settings

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging(settings: Settings) -> logging.Logger:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("jarvis")
    logger.setLevel(settings.log_level.upper())
    logger.handlers.clear()

    formatter = logging.Formatter(LOG_FORMAT)
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logfile = RotatingFileHandler(
        settings.data_dir / "jarvis.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    logfile.setFormatter(formatter)
    logger.addHandler(console)
    logger.addHandler(logfile)
    return logger
