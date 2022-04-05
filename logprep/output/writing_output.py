"""This module contains an output that writes documents to a file."""

from typing import TextIO
import json

from logprep.output.output import Output


class WritingOutput(Output):
    """An output that can writes the documents it was initialized with into a file.

    Parameters
    ----------
    documents : list
       A list of documents that should be written into a file.
    output_path : str
       The path for the output file.
    replace : bool, optional
       Determines if the output file should be replaced when instantiating a writer.

    """

    def __init__(
        self, output_path: str, output_path_custom: str = None, output_path_error: str = None
    ):
        self.last_timeout = None

        self.events = []
        self.failed_events = []

        self._output_file = open(output_path, "a+")
        self._output_file_custom = open(output_path_custom, "a+") if output_path_custom else None
        self._output_file_error = open(output_path_error, "a+") if output_path_error else None

    def describe_endpoint(self) -> str:
        return "writer"

    @staticmethod
    def _write_json(file: TextIO, line: dict):
        file.write("{}\n".format(json.dumps(line)))

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

    def shut_down(self):
        self._output_file.close()
        if self._output_file_custom:
            self._output_file_custom.close()
        if self._output_file_error:
            self._output_file_error.close()
