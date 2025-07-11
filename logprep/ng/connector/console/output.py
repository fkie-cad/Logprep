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
from pprint import pprint

from logprep.ng.abc.event import Event
from logprep.ng.abc.output import Output


class ConsoleOutput(Output):
    """A console output that pretty prints documents instead of storing them."""

    def store(self, event: Event):
        pprint(event)
        self.metrics.number_of_processed_events += 1

    def store_custom(self, event: dict, target: str):
        pprint(event, stream=getattr(sys, target))
        self.metrics.number_of_processed_events += 1
