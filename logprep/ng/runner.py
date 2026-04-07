"""
Runner module
"""

import asyncio
import json
import logging
import os
import warnings
from collections.abc import AsyncGenerator

from attrs import asdict

from logprep.ng.manager import PipelineManager
from logprep.ng.util.async_helpers import TerminateTaskGroup, restart_task_on_iter
from logprep.ng.util.configuration import Configuration
from logprep.ng.util.defaults import DEFAULT_LOG_CONFIG, MIN_CONFIG_REFRESH_INTERVAL

logger = logging.getLogger("Runner")


GRACEFUL_SHUTDOWN_TIMEOUT = 3
HARD_SHUTDOWN_TIMEOUT = 5


class Runner:
    """Class, a singleton runner, responsible for running the log processing pipeline."""

    instance: "Runner | None" = None

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super().__new__(cls)

        return cls.instance

    def __init__(self, configuration: Configuration) -> None:
        """Initialize the runner from the given `configuration`.

        Component wiring is deferred to `setup()` to preserve the required init order.
        """

        self.config = configuration
        self._running_config_version: None | str = None
        self._task_group = asyncio.TaskGroup()
        self._stop_event = asyncio.Event()

    async def _refresh_configuration_gen(self) -> AsyncGenerator[Configuration, None]:
        self._running_config_version = self.config.version
        refresh_interval = self.config.config_refresh_interval

        if refresh_interval is None:
            logger.debug("Config refresh has been disabled.")
            return

        loop = asyncio.get_running_loop()
        next_run = loop.time() + refresh_interval

        while True:
            sleep_time = next_run - loop.time()
            if sleep_time < 0:
                sleep_time = 0.0

            try:
                await asyncio.sleep(sleep_time)
            except asyncio.CancelledError:
                logger.debug("Config refresh cancelled. Exiting...")
                raise

            try:
                await self.config.reload()
            except asyncio.CancelledError:
                logger.debug("Config reload cancelled. Exiting...")
                raise
            except Exception:
                logger.exception("scheduled config reload failed")
                raise
            else:
                if self.config.version != self._running_config_version:
                    logger.info(f"Detected new config version: {self.config.version}")
                    self._running_config_version = self.config.version
                    yield self.config

            refresh_interval = self.config.config_refresh_interval
            if refresh_interval is None:
                logger.debug("Config refresh has been disabled.")
                break

            next_run += refresh_interval

    async def run(self) -> None:
        """Run the runner and continuously process events until stopped."""
        self._running_config_version = self.config.version

        try:
            async with self._task_group as tg:
                tg.create_task(TerminateTaskGroup.raise_on_event(self._stop_event))

                async def start_pipeline(config: Configuration) -> asyncio.Task:
                    pipeline_manager = PipelineManager(
                        config, shutdown_timeout_s=GRACEFUL_SHUTDOWN_TIMEOUT
                    )
                    await pipeline_manager.setup()

                    return tg.create_task(
                        pipeline_manager.run(),
                        name="pipeline_manager",
                    )

                try:
                    async for _ in restart_task_on_iter(
                        source=self._refresh_configuration_gen(),
                        task_factory=start_pipeline,
                        cancel_timeout_s=HARD_SHUTDOWN_TIMEOUT,
                        inital_task=await start_pipeline(self.config),
                    ):
                        logger.debug(
                            "A new pipeline task has been spawned based on the latest configuration"
                        )
                except TimeoutError:
                    logger.error(
                        "Could not gracefully shut down pipeline manager within timeframe",
                        exc_info=True,
                    )
                    raise
        except ExceptionGroup as eg:
            if not eg.exceptions or len(eg.exceptions) > 1:
                raise
            match list(eg.exceptions)[0]:
                case TerminateTaskGroup():
                    logger.debug("Task group terminated")
                case _:
                    raise

        logger.debug("End log processing.")

    def stop(self) -> None:
        """Stop the runner and signal the underlying processing pipeline to exit."""

        logger.info("Stopping runner and exiting...")
        self._stop_event.set()

    def setup_logging(self) -> None:
        """Setup the logging configuration.
        is called in the :code:`logprep.run_logprep` module.
        We have to write the configuration to the environment variable :code:`LOGPREP_LOG_CONFIG` to
        make it available for the uvicorn server in :code:'logprep.util.http'.
        """

        warnings.simplefilter("always", DeprecationWarning)
        logging.captureWarnings(True)
        log_config = DEFAULT_LOG_CONFIG | asdict(self.config.logger)
        os.environ["LOGPREP_LOG_CONFIG"] = json.dumps(log_config)
        logging.config.dictConfig(log_config)
