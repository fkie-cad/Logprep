"""
Runner module
"""

import asyncio
import json
import logging
import os
import warnings

from attrs import asdict

from logprep.ng.manager import PipelineManager
from logprep.ng.util.async_helpers import (
    StoppableTask,
    restart_stoppable_task_on_iter,
    restart_task_on_iter,
)
from logprep.ng.util.config_refresh import config_refresh_gen
from logprep.ng.util.configuration import Configuration
from logprep.ng.util.defaults import DEFAULT_LOG_CONFIG

logger = logging.getLogger("Runner")


GRACEFUL_SHUTDOWN_TIMEOUT = 10
HARD_SHUTDOWN_TIMEOUT = 15


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
        self._stop_event = asyncio.Event()

    async def run(self) -> None:
        """Run the runner and continuously process events until stopped."""

        # TODO refresh refreshable getter

        async with asyncio.TaskGroup() as tg:

            async def run_pipeline_manager(config: Configuration) -> StoppableTask:
                pipeline_manager = PipelineManager(
                    config, shutdown_timeout_s=GRACEFUL_SHUTDOWN_TIMEOUT
                )
                # TODO move setup into task runner
                await pipeline_manager.setup()

                return StoppableTask.from_runner(
                    pipeline_manager,
                    lambda pipeline_run: tg.create_task(pipeline_run, name="pipeline_manager"),
                )

            try:
                pipeline_gen = restart_stoppable_task_on_iter(
                    source=config_refresh_gen(self.config, self._stop_event),
                    task_factory=run_pipeline_manager,
                    cancel_timeout_s=HARD_SHUTDOWN_TIMEOUT,
                )

                async def run_task_stopper_on_stop_event(task: StoppableTask) -> asyncio.Task:
                    return tg.create_task(
                        task.stop_on_event(self._stop_event),
                        name=f"{task.get_name()}-stopper",
                    )

                async for _ in restart_task_on_iter(
                    source=pipeline_gen,
                    task_factory=run_task_stopper_on_stop_event,
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

    def stop(self) -> None:
        """Stop the runner and signal the underlying processing pipeline to exit."""

        logger.info("Setting stop signal for the runner")
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
