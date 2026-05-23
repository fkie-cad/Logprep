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
import typing
from collections.abc import Sequence

from attrs import define, field, validators

from logprep.ng.abc.output import Event, Output


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

    @property
    def config(self) -> Config:
        """Provides the properly typed configuration object"""
        return typing.cast(JsonlOutput.Config, self._config)

    async def setup(self):
        await super().setup()
        open(self.config.output_file, "a+", encoding="utf8").close()
        if self.config.output_file_custom:
            open(self.config.output_file_custom, "a+", encoding="utf8").close()

    @staticmethod
    def _write_json(filepath: str, line: dict):
        """writes processed document to configured file"""
        with open(filepath, "a+", encoding="utf8") as file:
            file.write(f"{json.dumps(line)}\n")

    def _store_single(self, event: Event) -> None:
        """Store the event in the output destination."""
        document = event.data if event.output_target is None else {event.output_target: event.data}
        events_file = (
            self.config.output_file
            if event.output_target is None
            else self.config.output_file_custom
        )

        self.events.append(document)
        JsonlOutput._write_json(events_file, document)
        self.metrics.number_of_processed_events += 1

    async def store(self, events: Sequence[Event]) -> Sequence[Event]:
        for event in events:
            self._store_single(event)
        return events
