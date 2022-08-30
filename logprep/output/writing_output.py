"""This module contains an output that writes documents to a file."""

import json

from logprep.output.output import Output


class WritingOutput(Output):
    """An output that can writes the documents it was initialized with into a file.

    Parameters
    ----------
    output_path : str
        The path for the output file.
    output_path_custom: str
        The path to store custom
    output_path_error: str
        The path to store error
    """

    def __init__(
        self, output_path: str, output_path_custom: str = None, output_path_error: str = None
    ):
        self.last_timeout = None

        self.events = []
        self.failed_events = []

        self._output_file = output_path
        open(self._output_file, "a+", encoding="utf8").close()
        self._output_file_custom = output_path_custom
        if self._output_file_custom:
            open(self._output_file_custom, "a+", encoding="utf8").close()
        self._output_file_error = output_path_error
        if self._output_file_error:
            open(self._output_file_error, "a+", encoding="utf8").close()

    def describe_endpoint(self) -> str:
        return "writer"

    @staticmethod
    def _write_json(filepath: str, line: dict):
        with open(filepath, "a+", encoding="utf8") as file:
            file.write(f"{json.dumps(line)}\n")

    def store(self, document: dict):
        self.events.append(document)

        WritingOutput._write_json(self._output_file, document)

    def store_custom(self, document: dict, target: str):
        self.events.append(document)

        if self._output_file_custom:
            WritingOutput._write_json(self._output_file_custom, document)

    def store_failed(self, error_message: str, document_received: dict, document_processed: dict):
        self.failed_events.append((error_message, document_received, document_processed))

        if self._output_file_error:
            WritingOutput._write_json(
                self._output_file_error,
                {
                    "error_message": error_message,
                    "document_received": document_received,
                    "document_processed": document_processed,
                },
            )
