"""logprep http utils"""

import asyncio
import inspect
import logging

import uvicorn

ENFORCED_UV_CONFIG = {
    "lifespan": "off",  # not required, logprep manages the lifecycle
    "http": "httptools",  # better performance as per docs (not pypy compatible)
    "log_level": None,  # managed by logprep log configuration
    "log_config": None,  # managed by logprep log configuration
}

DEFAULT_UV_CONFIG = {
    # TODO should be set in accordance with parent lifecycle grace periods
    "timeout_graceful_shutdown": 10,
}

DISALLOWED_CONFIG_KEYS = {
    "app",  # set explicitly by us
    "loop",  # not used and misleading, we integrate uvicorn into the existing loop
    *ENFORCED_UV_CONFIG.keys(),
}

uvicorn_parameter_keys = inspect.signature(uvicorn.Config).parameters.keys()
UVICORN_CONFIG_KEYS = [
    parameter for parameter in uvicorn_parameter_keys if parameter not in DISALLOWED_CONFIG_KEYS
]

logger = logging.getLogger("AsyncHTTPServer")


class AsyncHTTPServer:
    """
    Simple wrapper around a uvicorn server which is hooked into the currently running asyncio loop.
    """

    def __init__(self, uvicorn_config: dict, app) -> None:
        logging.getLogger("uvicorn").parent = logger

        resolved_config = {**DEFAULT_UV_CONFIG, **uvicorn_config, **ENFORCED_UV_CONFIG}
        self.uvicorn_config = uvicorn.Config(app=app, **resolved_config)
        self._server = uvicorn.Server(self.uvicorn_config)

    async def run(self) -> None:
        """Run the uvicorn server and serve the ASGI app. Blocks until server is stopped"""
        await self._server.serve()

    async def wait_until_started(self, poll_interval: float = 0.05) -> None:
        """Wait until the server (which has been `run()` already) is ready to serve by polling an internal flag

        Parameters
        ----------
        poll_interval : float, optional
            poll interval in seconds, by default 0.05
        """
        while not self._server.started:
            await asyncio.sleep(poll_interval)

    def stop(self) -> None:
        """Set a one-shot stop signal for the server to gracefully shut down"""
        self._server.should_exit = True
        logger.debug("Wait for server to exit gracefully...")
