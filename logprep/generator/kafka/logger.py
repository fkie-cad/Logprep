"""This module contains logger functionality."""

from logging import (
    CRITICAL,
    DEBUG,
    ERROR,
    FATAL,
    INFO,
    NOTSET,
    WARNING,
    Logger,
    basicConfig,
    getLogger,
)
from logging.handlers import SysLogHandler
from pathlib import Path

LOG_PATH = Path("/dev/log")


def create_logger(logging_level: str) -> Logger:
    """Create a logger (with a syslog handler if possible).

    Parameters
    ----------
    logging_level : str
        Logging level for the logger.

    Returns
    -------
    logger : logging.Logger
        Logger (with syslog handler if possible)

    """
    name_to_level = {
        "CRITICAL": CRITICAL,
        "FATAL": FATAL,
        "ERROR": ERROR,
        "WARN": WARNING,
        "WARNING": WARNING,
        "INFO": INFO,
        "DEBUG": DEBUG,
        "NOTSET": NOTSET,
    }

    basicConfig()
    logging_level = logging_level.upper()
    logger = getLogger("LoadTester")

    if LOG_PATH.exists():
        logger.handlers = []
        logger.addHandler(SysLogHandler(address=str(LOG_PATH)))

    if logging_level.upper() not in name_to_level:
        logger.setLevel("INFO")
        logger.debug("Invalid log level '%s', defaulting to 'INFO'", logging_level)
    else:
        logger.setLevel(name_to_level[logging_level])
        logger.debug("Log level set to '%s'", logging_level)

    return logger
