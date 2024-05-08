"""Default values for logprep."""

import multiprocessing

log_queue = multiprocessing.Queue(-1)

DEFAULT_CONFIG_LOCATION = "file:///etc/logprep/pipeline.yml"
DEFAULT_LOG_FORMAT = "%(asctime)-15s %(process)-6s %(name)-10s %(levelname)-8s: %(message)s"
DEFAULT_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
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
            "queue": "ext://logprep.util.defaults.log_queue",
        },
    },
    "loggers": {
        "root": {"level": "INFO", "handlers": ["console"]},
        "filelock": {"level": "ERROR", "handlers": ["console"]},
        "urllib3.connectionpool": {"level": "ERROR", "handlers": ["console"]},
        "elasticsearch": {"level": "ERROR", "handlers": ["console"]},
        "opensearch": {"level": "ERROR", "handlers": ["console"]},
        "logprep": {"level": "INFO", "handlers": ["console"]},
        "Pipeline": {"level": "INFO", "handlers": ["multiprocess"]},
        "uvicorn": {"level": "INFO", "handlers": ["multiprocess"]},
        "uvicorn.access": {"level": "INFO", "handlers": ["multiprocess"]},
        "uvicorn.error": {"level": "INFO", "handlers": ["multiprocess"]},
    },
    "filters": {},
    "disable_existing_loggers": False,
}
ENV_NAME_LOGPREP_CREDENTIALS_FILE = "LOGPREP_CREDENTIALS_FILE"
