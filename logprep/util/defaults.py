"""Default values for logprep."""

from enum import IntEnum


class EXITCODES(IntEnum):
    """Exit codes for logprep."""

    SUCCESS = 0
    """Successful execution."""
    ERROR = 1
    """General unspecified error."""
    CONFIGURATION_ERROR = 2
    """An error in the configuration."""
    PIPELINE_ERROR = 3
    """An error during pipeline processing."""
    ERROR_OUTPUT_NOT_REACHABLE = 4
    """The configured error output is not reachable."""


DEFAULT_MESSAGE_BACKLOG_SIZE = 15000
DEFAULT_RESTART_COUNT = 5
DEFAULT_CONFIG_LOCATION = "file:///etc/logprep/pipeline.yml"
DEFAULT_LOG_FORMAT = "%(asctime)-15s %(process)-6s %(name)-10s %(levelname)-8s: %(message)s"
DEFAULT_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_AES_KEY_LENGTH = 32
DEFAULT_BATCH_SIZE = 1
DEFAULT_BATCH_TIME = 1.0
MIN_CONFIG_REFRESH_INTERVAL = 5

# dictconfig as described in
# https://docs.python.org/3/library/logging.config.html#configuration-dictionary-schema
DEFAULT_LOG_CONFIG: dict = {
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
