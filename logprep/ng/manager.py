"""
Runner module
"""

import asyncio
import logging
from asyncio import CancelledError
from typing import cast

from logprep.factory import Factory
from logprep.ng.abc.input import Input
from logprep.ng.abc.output import Output
from logprep.ng.abc.processor import Processor
from logprep.ng.util.async_helpers import raise_from_gather
from logprep.ng.util.configuration import Configuration
from logprep.ng.util.workflow.config import WorkflowConfig
from logprep.ng.util.workflow.workflow import create_orchestrator

logger = logging.getLogger("PipelineManager")


class PipelineManager:
    """Orchestrator class managing pipeline inputs, processors and outputs"""

    def __init__(self, configuration: Configuration) -> None:
        """Initialize the component from the given `configuration`."""

        self.configuration = configuration

    async def setup(self) -> None:
        """Setup the pipeline manager."""

        with Factory.recorder() as recorder:
            input_connector = cast(Input, recorder.create(self.configuration.input))
            # TODO find a better way to inject global config version info in nested component
            input_connector.preprocessor.set_config_version_info(self.configuration.version)

            processors = [
                cast(Processor, recorder.create(processor_config))
                for processor_config in self.configuration.pipeline
            ]

            named_outputs = {
                output_name: cast(Output, recorder.create({output_name: output}))
                for output_name, output in self.configuration.output.items()
            }

            error_output = (
                cast(Output, Factory.create(self.configuration.error_output))
                if self.configuration.error_output
                else None
            )

            self._components = recorder.components

        default_outputs = [output for output in named_outputs.values() if output.default]

        if not default_outputs:
            logger.warning("No default output configured")

        if error_output is None:
            logger.warning("No error output configured")

        await asyncio.gather(*(component.setup() for component in self._components))

        workflow_config = WorkflowConfig.from_dict_or_default(self.configuration.workflow)

        self._orchestrator = create_orchestrator(
            input_connector,
            processors,
            default_outputs,
            named_outputs,
            error_output,
            workflow_config,
        )

    async def run(self, stop_event: asyncio.Event, shutdown_timeout_s: float) -> None:
        """Run the runner and continuously process events until stopped."""

        try:
            await self._orchestrator.run(stop_event, shutdown_timeout_s)
            if not stop_event.is_set():
                logger.info("Worker orchestration stopped internally; shutting down...")
        except (CancelledError, Exception):
            logger.error("PipelineManager.run cancelled or failed; shutting down...", exc_info=True)
            await self._shut_down()
            raise
        await self._shut_down()

    async def _shut_down(self) -> None:
        """Shut down runner components, and required runner attributes."""

        raise_from_gather(
            await asyncio.gather(
                *(component.shut_down() for component in self._components), return_exceptions=True
            ),
            "failure while shutting down components",
        )

        logger.info("Manager shut down complete.")
