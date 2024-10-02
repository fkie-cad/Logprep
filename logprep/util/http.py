"""logprep http utils"""

import atexit
import inspect
import json
import logging
import os
import threading
import time

import uvicorn

from logprep.util.defaults import DEFAULT_LOG_CONFIG

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
        atexit.register(self.shut_down, wait=0.1)
        if (
            hasattr(self, "thread")
            and self.thread is not None
            and self.thread.is_alive()  # pylint: disable=access-member-before-definition
        ):
            self.shut_down()
        internal_uvicorn_config = {
            "lifespan": "off",
            "timeout_graceful_shutdown": 10,
            "loop": "uvloop",
            "http": "httptools",
        }
        uvicorn_config = {**internal_uvicorn_config, **uvicorn_config}
        self._logger_name = logger_name
        self._logger = logging.getLogger(self._logger_name)
        logprep_log_config = json.loads(
            os.environ.get("LOGPREP_LOG_CONFIG", json.dumps(DEFAULT_LOG_CONFIG))
        )
        self.uvicorn_config = uvicorn.Config(
            **uvicorn_config, app=app, log_config=logprep_log_config
        )
        logging.getLogger("uvicorn.access").name = self._logger_name
        logging.getLogger("uvicorn.error").name = self._logger_name
        self.server = None
        self.thread = None
        self.daemon = daemon

    def start(self):
        """Collect all configs, initiate application server and webserver
        and run thread with uvicorn+falcon http server and wait
        until it is up (started)"""
        self.server = uvicorn.Server(self.uvicorn_config)
        self.thread = threading.Thread(daemon=self.daemon, target=self.server.run)
        self.thread.start()
        while not self.server.started:
            continue

    def shut_down(self, wait: float = 1) -> None:
        """Stop thread with uvicorn+falcon http server, wait for uvicorn
        to exit gracefully and join the thread"""
        if self.thread is None or self.server is None:
            return
        self.server.should_exit = True
        while 1:
            self._logger.debug("Wait for server to exit gracefully...")
            if not self.thread.is_alive():
                time.sleep(wait)
                if not self.thread.is_alive():  # we have to double check if it is really dead
                    break
            time.sleep(wait)
        self.thread.join()

    def restart(self, wait: float = 1) -> None:
        """Restart the server by shutting down the existing server and
        starting a new one"""
        self.shut_down(wait=wait)
        self.start()
