"""
ConsoleOutput
----------------------

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

from logprep.abc.output import Output


class ConsoleOutput(Output):
    """A console output that pretty prints documents instead of storing them."""

    def store(self, document: dict):
        pprint(document)
        self.metrics.number_of_processed_events += 1
        if self.input_connector:
            self.input_connector.batch_finished_callback()

    def store_custom(self, document: dict, target: str):
        pprint(document, stream=getattr(sys, target))

    def store_failed(self, error_message: str, document_received: dict, document_processed: dict):
        pprint(f"{error_message}: {document_received}, {document_processed}", stream=sys.stderr)
