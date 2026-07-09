"""
Runner module
"""

import asyncio
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from functools import partial

from attrs import asdict

from logprep.ng.manager import PipelineManager
from logprep.ng.metrics.exporter import PrometheusExporter
from logprep.ng.util.async_helpers import StoppableTask
from logprep.ng.util.config_refresh import StopConfigRefresh, wait_for_refreshed_config
from logprep.ng.util.configuration import Configuration
from logprep.ng.util.defaults import DEFAULT_LOG_CONFIG
from logprep.ng.util.logging_helpers import (
    decouple_logging_via_queue,
    inject_task_names_in_log_records,
)
from logprep.util.getter import RefreshableGetter

logger = logging.getLogger("Runner")


class Runner:
    """Class responsible for running the log processing pipeline."""

    def __init__(self, config: Configuration) -> None:
        self._config = config
        self._stop_event = asyncio.Event()
        self.prometheus_exporter: PrometheusExporter | None = None

    def _start_prometheus_exporter(self) -> None:
        if not self._config.metrics.enabled:
            return
        self.prometheus_exporter = PrometheusExporter(self._config.metrics)
        self.prometheus_exporter.restart()

    async def _run_pipeline_manager(self, stop_event: asyncio.Event, config: Configuration) -> None:
        self._start_prometheus_exporter()
        pipeline_manager = PipelineManager(config)
        await pipeline_manager.setup()
        if self.prometheus_exporter:
            self.prometheus_exporter.update_healthchecks(
                [c.health for c in pipeline_manager.components()]
            )
        await pipeline_manager.run(
            stop_event,
            config.graceful_orchestrator_shutdown_timeout_s,
            config.graceful_worker_shutdown_timeout_s,
        )

    async def _refresh_getters(self):
        while True:
            # TODO make getters async
            RefreshableGetter.refresh()
            try:
                async with asyncio.timeout(self._config.refreshable_getter_base_interval_s):
                    await self._stop_event.wait()
                logger.debug("stopped refreshing getters as the stop_event has been set")
                return
            except TimeoutError:
                pass

    async def _refresh_config(self, config: Configuration) -> Configuration | None:
        """
        Run config refresh until an actually changed config has been found.
        """
        try:
            return await wait_for_refreshed_config(self._stop_event, config)
        except StopConfigRefresh as exc:
            logger.info("config refresh stopped: %s", str(exc))
        await self._stop_event.wait()
        return None

    async def run(self) -> None:
        """Run the runner and continuously process events until stopped."""

        async with asyncio.TaskGroup() as tg:
            wait_for_stop = tg.create_task(self._stop_event.wait(), name="wait_for_stop")
            refresh_getters_loop = tg.create_task(self._refresh_getters(), name="refresh_getters")
            refresh_config = tg.create_task(
                self._refresh_config(self._config), name="refresh_config"
            )

            while not self._stop_event.is_set():

                logger.debug("Starting PipelineManager with current config")

                pipeline_manager = StoppableTask.from_callable(
                    partial(self._run_pipeline_manager, config=self._config),
                    partial(tg.create_task, name="pipeline_manager"),
                )

                logger.info("Startup complete")
                logger.debug("Waiting for long-running tasks to complete or fail")
                done, _ = await asyncio.wait(
                    [wait_for_stop, pipeline_manager.task, refresh_config, refresh_getters_loop],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if refresh_config in done:
                    new_config = await refresh_config
                    if new_config:
                        logger.debug("Config refresh done; apply config and schedule new refresh")
                        self._config = new_config
                        refresh_config = tg.create_task(
                            self._refresh_config(self._config), name="config_refresh"
                        )
                    else:
                        logger.debug("Config refresh task stopped while shutting down")
                        assert self._stop_event.is_set()

                logger.debug("Stopping PipelineManager")
                await pipeline_manager.stop_and_cancel(
                    self._config.hard_orchestrator_shutdown_timeout_s
                )

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

        if self.prometheus_exporter is not None:
            self.prometheus_exporter.shutdown()

        logger.info("Setting stop signal for the runner")
        self._stop_event.set()

    @contextmanager
    def with_configured_logging(self) -> Iterator[None]:
        """
        Setup the logging configuration. is called in the :code:`logprep.run_ng` module.
        """

        # TODO ensure asyncio exceptions are logged as json (e.g. ExceptionGroup)

        log_config = DEFAULT_LOG_CONFIG | asdict(self._config.logger)
        logging.config.dictConfig(log_config)

        with inject_task_names_in_log_records():
            with decouple_logging_via_queue():
                yield
