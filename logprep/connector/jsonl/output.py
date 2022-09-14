"""
JsonlOutput
----------------------

The JsonlOutput Connector can be used to write processed documents to .jsonl
files.

Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    output:
      my_jsonl_output:
        type: jsonl_output
        output_file = path/to/output.file
        output_file_custom = ""
        output_file_error = ""
"""

import json
from logging import Logger

from attrs import define, field, validators

from logprep.abc.output import Output


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
        output_file_error = field(validator=validators.instance_of(str), default="")

    last_timeout: float
    events: list
    failed_events: list

    __slots__ = [
        "ast_timeout",
        "events",
        "failed_events",
    ]

    def __init__(self, name: str, configuration: "Output.Config", logger: Logger):
        super().__init__(name, configuration, logger)
        self.events = []
        self.failed_events = []

    def setup(self):
        super().setup()
        open(self._config.output_file, "a+", encoding="utf8").close()
        if self._config.output_file_custom:
            open(self._config.output_file_custom, "a+", encoding="utf8").close()
        if self._config.output_file_error:
            open(self._config.output_file_error, "a+", encoding="utf8").close()

    @staticmethod
    def _write_json(filepath: str, line: dict):
        """writes processed document to configured file"""
        with open(filepath, "a+", encoding="utf8") as file:
            file.write(f"{json.dumps(line)}\n")

    def store(self, document: dict):
        self.events.append(document)
        JsonlOutput._write_json(self._config.output_file, document)
        self.metrics.number_of_processed_events += 1
        if self.input_connector:
            self.input_connector.batch_finished_callback()

    def store_custom(self, document: dict, target: str):
        document = {target: document}
        self.events.append(document)

        if self._config.output_file_custom:
            JsonlOutput._write_json(self._config.output_file_custom, document)

    def store_failed(self, error_message: str, document_received: dict, document_processed: dict):
        self.failed_events.append((error_message, document_received, document_processed))

        if self._config.output_file_error:
            JsonlOutput._write_json(
                self._config.output_file_error,
                {
                    "error_message": error_message,
                    "document_received": document_received,
                    "document_processed": document_processed,
                },
            )
