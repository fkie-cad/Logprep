"""
ConsoleOutput
=============

This section describes the ConsoleOutput, which pretty prints documents to the
console and can be used for testing.

Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    output:
      my_console_output:
        type: console_output
"""

import sys
from collections.abc import Sequence
from pprint import pprint

from logprep.ng.abc.event import Event
from logprep.ng.abc.output import Output


class ConsoleOutput(Output):
    """A console output that pretty prints documents instead of storing them."""

    async def _store_batch(
        self, events: Sequence[Event], target: str | None = None
    ) -> Sequence[Event]:
        for event in events:
            if target:
                pprint(event.data)
            else:
                pprint(event.data, stream=getattr(sys, target))
            self.metrics.number_of_processed_events += 1
        return events
