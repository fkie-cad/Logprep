"""
Runner module
"""

import asyncio
import logging
import warnings
from functools import partial

from attrs import asdict

from logprep.ng.manager import PipelineManager
from logprep.ng.util.async_helpers import StoppableTask
from logprep.ng.util.config_refresh import wait_for_refreshed_config
from logprep.ng.util.configuration import Configuration
from logprep.ng.util.defaults import DEFAULT_LOG_CONFIG
from logprep.util.getter import RefreshableGetter

logger = logging.getLogger("Runner")

# TODO make configurable via config
GRACEFUL_SHUTDOWN_TIMEOUT = 10
HARD_SHUTDOWN_TIMEOUT = 15
REFRESHABLE_GETTER_BASE_INTERVAL = 1


class Runner:
    """Class responsible for running the log processing pipeline."""

    def __init__(self, config: Configuration) -> None:
        self._config = config
        self._stop_event = asyncio.Event()

    async def _run_pipeline_manager(self, stop_event: asyncio.Event, config: Configuration) -> None:
        pipeline_manager = PipelineManager(config)
        await pipeline_manager.setup()
        await pipeline_manager.run(stop_event, GRACEFUL_SHUTDOWN_TIMEOUT)

    async def _refresh_getters(self):
        while not self._stop_event.is_set():
            # TODO make getters async
            RefreshableGetter.refresh()
            await asyncio.sleep(REFRESHABLE_GETTER_BASE_INTERVAL)

    async def _refresh_config(self, config: Configuration) -> Configuration | None:
        return await wait_for_refreshed_config(config, self._stop_event)

    async def run(self) -> None:
        """Run the runner and continuously process events until stopped."""

        async with asyncio.TaskGroup() as tg:
            config = self._config

            wait_for_stop = tg.create_task(self._stop_event.wait(), name="wait_for_stop")
            refresh_getters_loop = tg.create_task(self._refresh_getters(), name="refresh_getters")
            refresh_config = tg.create_task(self._refresh_config(config), name="refresh_config")

            while not self._stop_event.is_set():

                logger.debug("Starting PipelineManager with current config")

                pipeline_manager = StoppableTask.from_callable(
                    partial(self._run_pipeline_manager, config=config),
                    partial(tg.create_task, name="pipeline_manager"),
                )

                logger.info("Startup complete")
                logger.debug("Waiting for long-running tasks to complete or fail")
                done, _ = await asyncio.wait(
                    [wait_for_stop, pipeline_manager.task, refresh_config, refresh_getters_loop],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if refresh_config in done:
                    logger.debug("Config refresh done; collect config and schedule new refresh")
                    new_config = await refresh_config
                    if new_config:
                        config = new_config
                        refresh_config = tg.create_task(
                            self._refresh_config(config), name="config_refresh"
                        )

                logger.debug("Stopping PipelineManager for restart")
                await pipeline_manager.stop_and_cancel(HARD_SHUTDOWN_TIMEOUT)

                if pipeline_manager.task in done:
                    logger.debug(
                        "PipelineManager did stop by itself (error or input exhaustion). Exiting..."
                    )
                    self._stop_event.set()

                if refresh_getters_loop in done:
                    logger.warning("Getter refresh loop stopped unexpectedly. Exiting...")
                    self._stop_event.set()

    def stop(self) -> None:
        """Stop the runner and signal the underlying processing pipeline to exit."""

        logger.info("Setting stop signal for the runner")
        self._stop_event.set()

    def setup_logging(self) -> None:
        """Setup the logging configuration.
        is called in the :code:`logprep.run_logprep` module.
        """

        # TODO ensure asyncio exceptions are logged as json (e.g. ExceptionGroup)
        warnings.simplefilter("always", DeprecationWarning)
        logging.captureWarnings(True)
        log_config = DEFAULT_LOG_CONFIG | asdict(self._config.logger)
        logging.config.dictConfig(log_config)
