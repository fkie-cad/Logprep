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

    @Output._handle_errors
    def store(self, event: Event) -> None:
        """Store a document to the console."""
        event.state.next_state()
        pprint(event.data)
        self.metrics.number_of_processed_events += 1
        event.state.next_state(success=True)

    @Output._handle_errors
    def store_custom(self, event: Event, target: str) -> None:
        """Store a custom document to the console."""
        event.state.next_state()
        pprint(event.data, stream=getattr(sys, target))
        self.metrics.number_of_processed_events += 1
        event.state.next_state(success=True)

    def flush(self):
        """Flush the console output.
        Do nothing as console output does not have a backlog.
        """
