"""
JsonlOutput
===========

The JsonlOutput Connector can be used to write processed documents to .jsonl
files.

Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    output:
      my_jsonl_output:
        type: jsonl_output
        output_file: path/to/output.file
        output_file_custom: ""
        output_file_error: ""
"""

import json

from attrs import define, field, validators

from logprep.ng.abc.event import Event
from logprep.ng.abc.output import Output


class JsonlOutput(Output):
    """An output that writes the documents it was initialized with to a file.

    Parameters
    ----------
    output_path : str
        The path for the output file.
    output_path_custom : str
        The path to store custom
    output_path_error : str
        The path to store error
    """

    @define(kw_only=True)
    class Config(Output.Config):
        """Common Configurations"""

        output_file = field(validator=validators.instance_of(str))
        output_file_custom = field(validator=validators.instance_of(str), default="")

    last_timeout: float
    events: list[dict]
    failed_events: list[dict]

    __slots__ = [
        "last_timeout",
        "events",
        "failed_events",
    ]

    def __init__(self, name: str, configuration: "Output.Config"):
        super().__init__(name, configuration)
        self.events = []
        self.failed_events = []

    def setup(self):
        super().setup()
        open(self._config.output_file, "a+", encoding="utf8").close()
        if self._config.output_file_custom:
            open(self._config.output_file_custom, "a+", encoding="utf8").close()

    @staticmethod
    def _write_json(filepath: str, line: dict):
        """writes processed document to configured file"""
        with open(filepath, "a+", encoding="utf8") as file:
            file.write(f"{json.dumps(line)}\n")

    @Output._handle_errors
    def store(self, event: Event) -> None:
        """Store the event in the output destination."""
        event.state.next_state()
        self.events.append(event.data)
        JsonlOutput._write_json(self._config.output_file, event.data)
        self.metrics.number_of_processed_events += 1
        event.state.next_state(success=True)

    @Output._handle_errors
    def store_custom(self, event: Event, target: str) -> None:
        """Store the event in the output destination with a custom target."""
        event.state.next_state()
        document = {target: event.data}
        self.events.append(document)

        if self._config.output_file_custom:
            JsonlOutput._write_json(self._config.output_file_custom, document)
        self.metrics.number_of_processed_events += 1
        event.state.next_state(success=True)

    def flush(self):
        """Flush is not implemented because it has no backlog."""
