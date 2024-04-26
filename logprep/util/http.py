"""logprep http utils"""

import inspect
import logging
import threading

import uvicorn

from logprep.util import defaults

uvicorn_parameter_keys = inspect.signature(uvicorn.Config).parameters.keys()
UVICORN_CONFIG_KEYS = [
    parameter for parameter in uvicorn_parameter_keys if parameter not in ["app", "log_level"]
]


class ThreadingHTTPServer:  # pylint: disable=too-many-instance-attributes
    """Singleton Wrapper Class around Uvicorn Thread that controls
    lifecycle of Uvicorn HTTP Server. During Runtime this singleton object
    is stateful and therefore we need to check for some attributes during
    __init__ when multiple consecutive reconfigurations are happening.
    """

    _instance = None
    _lock = threading.Lock()

    @property
    def _log_config(self) -> dict:
        """Use for Uvicorn same log formatter like for Logprep"""
        log_config = uvicorn.config.LOGGING_CONFIG
        log_config["formatters"]["default"]["fmt"] = defaults.DEFAULT_LOG_FORMAT
        log_config["formatters"]["access"]["fmt"] = defaults.DEFAULT_LOG_FORMAT
        log_config["handlers"]["default"]["stream"] = "ext://sys.stdout"
        return log_config

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(ThreadingHTTPServer, cls).__new__(cls)
        return cls._instance

    def __init__(
        self, uvicorn_config: dict, app, daemon=True, logger_name="Logprep HTTPServer"
    ) -> None:
        """
        Creates object attributes with necessary configuration.
        As this class creates a singleton object, the existing server
        will be stopped and restarted on consecutively creations

        Parameters
        ----------
        uvicorn_config: dict
            Holds server config for config change checks
        app:
            The app instance that the server should provide
        daemon: bool
            Whether the server is in daemon mode or not
        logger_name: str
            Name of the logger instance
        """

        if hasattr(self, "thread"):
            if self.thread.is_alive():  # pylint: disable=access-member-before-definition
                self._stop()
        internal_uvicorn_config = {
            "lifespan": "off",
            "loop": "asyncio",
            "timeout_graceful_shutdown": 5,
        }
        uvicorn_config = {**internal_uvicorn_config, **uvicorn_config}
        self._logger_name = logger_name
        uvicorn_config = uvicorn.Config(**uvicorn_config, app=app, log_config=self._log_config)
        self.server = uvicorn.Server(uvicorn_config)
        self._override_runtime_logging()
        self.thread = threading.Thread(daemon=daemon, target=self.server.run)

    def start(self):
        """Collect all configs, initiate application server and webserver
        and run thread with uvicorn+falcon http server and wait
        until it is up (started)"""

        self.thread.start()
        while not self.server.started:
            continue

    def _stop(self):
        """Stop thread with uvicorn+falcon http server, wait for uvicorn
        to exit gracefully and join the thread"""
        if self.thread.is_alive():
            self.server.should_exit = True
            while self.thread.is_alive():
                continue
        self.thread.join()

    def _override_runtime_logging(self):
        """Uvicorn doesn't provide API to change name and handler beforehand
        needs to be done during runtime"""
        for logger_name in ["uvicorn", "uvicorn.access"]:
            registered_handlers = logging.getLogger(logger_name).handlers
            if not registered_handlers:
                continue
            logging.getLogger(logger_name).removeHandler(registered_handlers[0])
            logging.getLogger(logger_name).addHandler(
                logging.getLogger("Logprep").parent.handlers[0]
            )
        logging.getLogger("uvicorn.access").name = self._logger_name
        logging.getLogger("uvicorn.error").name = self._logger_name

    def shut_down(self):
        """Shutdown method to trigger http server shutdown externally"""
        self._stop()
