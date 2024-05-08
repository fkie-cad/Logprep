"""Default values for logprep."""

DEFAULT_CONFIG_LOCATION = "file:///etc/logprep/pipeline.yml"
DEFAULT_LOG_FORMAT = "%(asctime)-15s %(name)-10s %(levelname)-8s: %(message)s"
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
        }
    },
    "loggers": {
        "root": {"level": "INFO", "handlers": ["console"]},
        "filelock": {"level": "ERROR", "handlers": ["console"]},
        "urllib3.connectionpool": {"level": "ERROR", "handlers": ["console"]},
        "elasticsearch": {"level": "ERROR", "handlers": ["console"]},
        "opensearch": {"level": "ERROR", "handlers": ["console"]},
        "logprep": {"level": "INFO", "handlers": ["console"]},
        "uvicorn": {"level": "INFO", "handlers": ["console"]},
        "uvicorn.access": {"level": "INFO", "handlers": ["console"]},
        "uvicorn.error": {"level": "INFO", "handlers": ["console"]},
    },
    "filters": {},
    "disable_existing_loggers": False,
}
ENV_NAME_LOGPREP_CREDENTIALS_FILE = "LOGPREP_CREDENTIALS_FILE"
