"""Default values for logprep."""

from enum import IntEnum
from typing import Literal


class EXITCODES(IntEnum):
    """Exit codes for logprep.

    Attributes:
        SUCCESS (int): Successful execution.
        ERROR (int): General unspecified error.
        CONFIGURATION_ERROR (int): An error in the configuration.
        PIPELINE_ERROR (int): An error during pipeline processing.
        ERROR_OUTPUT_NOT_REACHABLE (int): The configured error output is not reachable.
    """

    SUCCESS = 0
    ERROR = 1
    CONFIGURATION_ERROR = 2
    PIPELINE_ERROR = 3
    ERROR_OUTPUT_NOT_REACHABLE = 4

    def to_bytes(
        self, length: int, byteorder: Literal["big", "little"] = "big", signed: bool = False
    ) -> bytes:
        """Return the integer as a bytes object.

        Args:
            length (int): Length of the resulting bytes object.
            byteorder (Literal["big", "little"]): Byte order.
            signed (bool): Whether the number is signed.

        Returns:
            bytes: The integer represented as a byte sequence.
        """
        return int(self).to_bytes(length, byteorder, signed=signed)

    @classmethod
    def from_bytes(
        cls, bytes_obj: bytes, byteorder: Literal["big", "little"] = "big", signed: bool = False
    ) -> "EXITCODES":
        """Convert a bytes object back to an EXITCODES enum value.

        Args:
            bytes_obj (bytes): The bytes object representing an integer.
            byteorder (Literal["big", "little"]): Byte order.
            signed (bool): Whether the number is signed.

        Returns:
            EXITCODES: The corresponding enum value.
        """
        return cls(int.from_bytes(bytes_obj, byteorder, signed=signed))


DEFAULT_MESSAGE_BACKLOG_SIZE = 15000
DEFAULT_RESTART_COUNT = 5
DEFAULT_CONFIG_LOCATION = "file:///etc/logprep/pipeline.yml"
DEFAULT_LOG_FORMAT = "%(asctime)-15s %(process)-6s %(name)-10s %(levelname)-8s: %(message)s"
DEFAULT_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_AES_KEY_LENGTH = 32
DEFAULT_BATCH_SIZE = 1
DEFAULT_BATCH_TIME = 1.0


# dictconfig as described in
# https://docs.python.org/3/library/logging.config.html#configuration-dictionary-schema
DEFAULT_LOG_CONFIG = {
    "version": 1,
    "formatters": {
        "logprep": {
            "class": "logprep.util.logging.LogprepFormatter",
            "format": DEFAULT_LOG_FORMAT,
            "datefmt": DEFAULT_LOG_DATE_FORMAT,
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "logprep",
            "stream": "ext://sys.stdout",
        },
        "queue": {
            "class": "logging.handlers.QueueHandler",
            "queue": "ext://logprep.util.logging.logqueue",
        },
    },
    "loggers": {
        "root": {"level": "INFO", "handlers": ["queue"]},
        "console": {"handlers": ["console"]},
        "filelock": {"level": "ERROR"},
        "urllib3.connectionpool": {"level": "ERROR"},
        "opensearch": {"level": "ERROR"},
    },
    "filters": {},
    "disable_existing_loggers": False,
}
ENV_NAME_LOGPREP_CREDENTIALS_FILE = "LOGPREP_CREDENTIALS_FILE"

DEFAULT_HEALTH_STATE = False  # unhealthy

DEFAULT_HEALTH_TIMEOUT = 1  # seconds

RULE_FILE_EXTENSIONS = {".yml", ".yaml", ".json"}
