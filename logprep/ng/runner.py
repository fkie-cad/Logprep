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
from logprep.ng.util.configuration import Configuration
from logprep.ng.util.defaults import DEFAULT_LOG_CONFIG

logger = logging.getLogger("Runner")


GRACEFUL_SHUTDOWN_TIMEOUT = 10
MAX_CONFIG_REFRESH_INTERVAL_DEVIATION_PERCENT = 0.05


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

        self.configuration = configuration
        self._running_config_version: None | str = None
        self._main_task: asyncio.Task | None = None

        self._pipeline_manager: PipelineManager | None = None

    async def _refresh_configuration_gen(self) -> AsyncGenerator[Configuration, None]:
        self.configuration.schedule_config_refresh()
        refresh_interval = self.configuration.config_refresh_interval
        while True:
            self.configuration.refresh()

            if self.configuration.version != self._running_config_version:
                yield self.configuration
                self._running_config_version = self.configuration.version
                refresh_interval = self.configuration.config_refresh_interval

            if refresh_interval is not None:
                try:
                    await asyncio.sleep(
                        # realistic bad case: starting to sleep just a moment before scheduled time
                        # unlikely worst case: starting to sleep even after scheduled time
                        #                      (if yield takes some time and interval is short)
                        # --> compensate bad case by giving an upper boundary to the deviation
                        refresh_interval
                        * MAX_CONFIG_REFRESH_INTERVAL_DEVIATION_PERCENT
                    )
                except asyncio.CancelledError:
                    logger.debug("Config refresh cancelled. Exiting...")
                    raise
            else:
                logger.debug("Config refresh has been disabled.")
                break

    async def _run_pipeline(self, config: Configuration) -> tuple[PipelineManager, asyncio.Task]:
        manager = PipelineManager(config)
        manager_task = asyncio.create_task(manager.run(), name="pipeline_manager")
        return manager, manager_task

    async def _shut_down_pipeline(
        self, manager: PipelineManager, manager_task: asyncio.Task
    ) -> None:
        await manager.shut_down()
        try:
            await asyncio.wait_for(manager_task, GRACEFUL_SHUTDOWN_TIMEOUT)
            logger.info("graceful shut down of pipeline manager succeeded")
        except TimeoutError:
            logger.error(
                "could not gracefully shut down pipeline manager within timeframe", exc_info=True
            )

    async def _run(self) -> None:
        logger.debug("Running _run")
        try:
            manager, manager_task = await self._run_pipeline(self.configuration)

            async for refreshed_config in self._refresh_configuration_gen():
                logger.debug("Configuration change detected. Restarting pipeline...")
                await self._shut_down_pipeline(manager, manager_task)
                manager, manager_task = await self._run_pipeline(refreshed_config)

            logger.debug("Configuration refresh disabled. Waiting for ")
            await manager_task
        except asyncio.CancelledError:
            if manager is not None and manager_task is not None:
                await self._shut_down_pipeline(manager, manager_task)

        logger.debug("End of _run")

    async def run(self) -> None:
        """Run the runner and continuously process events until stopped."""
        self._running_config_version = self.configuration.version

        self._main_task = asyncio.create_task(self._run(), name="config_refresh")

        await self._main_task

        self.shut_down()
        logger.debug("End log processing.")

    def stop(self) -> None:
        """Stop the runner and signal the underlying processing pipeline to exit."""

        logger.info("Stopping runner and exiting...")
        if self._main_task is not None:
            logger.debug("Cancelling runner main task")
            self._main_task.cancel()
        else:
            logger.debug("Attempting to stop inactive runner")

    def shut_down(self) -> None:
        """Shut down runner components, and required runner attributes."""

        logger.info("Runner shut down complete.")

    def setup_logging(self) -> None:
        """Setup the logging configuration.
        is called in the :code:`logprep.run_logprep` module.
        We have to write the configuration to the environment variable :code:`LOGPREP_LOG_CONFIG` to
        make it available for the uvicorn server in :code:'logprep.util.http'.
        """

        warnings.simplefilter("always", DeprecationWarning)
        logging.captureWarnings(True)
        log_config = DEFAULT_LOG_CONFIG | asdict(self.configuration.logger)
        os.environ["LOGPREP_LOG_CONFIG"] = json.dumps(log_config)
        logging.config.dictConfig(log_config)
