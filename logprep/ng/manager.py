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
from logprep.ng.workflow import create_orchestrator

logger = logging.getLogger("PipelineManager")


BATCH_SIZE = 1000
BATCH_INTERVAL_S = 5
MAX_QUEUE_SIZE = BATCH_SIZE


class PipelineManager:
    """Orchestrator class managing pipeline inputs, processors and outputs"""

    def __init__(self, configuration: Configuration, shutdown_timeout_s: float) -> None:
        """Initialize the component from the given `configuration`."""

        self.configuration = configuration
        self._shutdown_timeout_s = shutdown_timeout_s

    async def setup(self) -> None:
        """Setup the pipeline manager."""

        with Factory.record() as recorder:
            input_connector = cast(Input, recorder.create(self.configuration.input))

            processors = [
                cast(Processor, recorder.create(processor_config))
                for processor_config in self.configuration.pipeline
            ]

            named_outputs = {
                output_name: cast(Output, recorder.create({output_name: output}))
                for output_name, output in self.configuration.output.items()
            }

            processors = [
                cast(Processor, recorder.create(processor_config))
                for processor_config in self.configuration.pipeline
            ]

            error_output = (
                cast(Output, Factory.create(self.configuration.error_output))
                if self.configuration.error_output
                else None
            )

            self._components = recorder.components

        default_output = [output for output in named_outputs.values() if output.default][0]

        if error_output is None:
            logger.warning("No error output configured.")

        await asyncio.gather(*(component.setup() for component in self._components))

        self._orchestrator = create_orchestrator(
            input_connector, processors, default_output, named_outputs, error_output
        )

    async def run(self, stop_event: asyncio.Event) -> None:
        """Run the runner and continuously process events until stopped."""

        try:
            await self._orchestrator.run(stop_event, self._shutdown_timeout_s)
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
