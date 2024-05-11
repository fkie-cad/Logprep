"""Default values for logprep."""

DEFAULT_CONFIG_LOCATION = "file:///etc/logprep/pipeline.yml"
DEFAULT_LOG_FORMAT = "%(asctime)-15s %(process)-6s %(name)-10s %(levelname)-8s: %(message)s"
DEFAULT_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

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
        "multiprocess": {
            "class": "logging.handlers.QueueHandler",
            "queue": "ext://logprep.util.logging.logqueue",
        },
        "string": {"class": "logging.StreamHandler", "level": "WARNING"},
    },
    "loggers": {
        "root": {"level": "INFO", "handlers": ["console"]},
        "filelock": {"level": "ERROR"},
        "urllib3.connectionpool": {"level": "ERROR"},
        "elasticsearch": {"level": "ERROR"},
        "opensearch": {"level": "ERROR"},
        "Pipeline": {"level": "INFO", "handlers": ["multiprocess"], "propagate": "0"},
        "uvicorn": {"level": "INFO", "handlers": ["multiprocess"], "propagate": "0"},
        "uvicorn.access": {"level": "INFO", "handlers": ["multiprocess"], "propagate": "0"},
        "uvicorn.error": {"level": "INFO", "handlers": ["multiprocess"], "propagate": "0"},
        "corpustester": {
            "level": "WARNING",
            "handlers": ["string"],
            "propagate": "1",
        },
    },
    "filters": {},
    "disable_existing_loggers": False,
}
ENV_NAME_LOGPREP_CREDENTIALS_FILE = "LOGPREP_CREDENTIALS_FILE"
