"""
This module contains functionality to extract selectively fields from an incoming event. The events will be returned
and written to a specified kafka topic. As the processor is applied to all events it does not need further filtering by
rules.
"""

import os.path
from logging import Logger, DEBUG

from logprep.processor.base.processor import BaseProcessor
from logprep.util.helper import add_field_to
from logprep.util.processor_stats import ProcessorStats
from logprep.util.time_measurement import TimeMeasurement


class SelectiveExtractorError(BaseException):
    """Base class for Selective Extractor related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"Selective Extractor ({name}): {message}")


class SelectiveExtractorConfigurationError(SelectiveExtractorError):
    """Generic Selective Extractor configuration error."""


class SelectiveExtractor(BaseProcessor):
    """Processor used to selectively extract fields from log events."""

    def __init__(
        self,
        name: str,
        selective_extractor_topic: str,
        extractor_list_file_path: str,
        logger: Logger,
    ):
        super().__init__(name, logger)
        self._logger = logger
        self.ps = ProcessorStats()

        self._name = name
        self._selective_extractor_topic = selective_extractor_topic
        self._event = None

        self._load_extraction_fields(extractor_list_file_path)

    def _load_extraction_fields(self, extractor_list_file_path):
        if os.path.isfile(extractor_list_file_path) and extractor_list_file_path.endswith(".txt"):
            with open(extractor_list_file_path, "r", encoding="utf8") as f:
                extraction_fields = f.read().splitlines()
                self.extraction_fields = [
                    field for field in extraction_fields if not field.startswith("#")
                ]
        else:
            raise SelectiveExtractorConfigurationError(
                self._name,
                "The given extraction_list file does not exist or " "is not a valid '.txt' file.",
            )

    def describe(self) -> str:
        return f"Selective Extractor ({self._name})"

    @TimeMeasurement.measure_time("selective_extractor")
    def process(self, event: dict) -> tuple:
        self._event = event

        if self._logger.isEnabledFor(DEBUG):
            self._logger.debug("{} processing matching event".format(self.describe()))

        filtered_event = self._generate_filtered_event(event)

        self.ps.increment_processed_count()
        if filtered_event:
            return ([filtered_event], self._selective_extractor_topic)
        return None

    def _generate_filtered_event(self, event):
        """
        Generates a filtered event based on the incoming event and the configured extraction_fields list. The filtered
        fields are written to a new document that will be returned.

        Parameters
        ----------
        event: dict
            The incoming event that is currently being processed by logprep.

        Returns
        -------
        dict
            A filtered event containing only the fields from the original incoming event that were specified by the
            'extraction_fields' list.
        """

        filtered_event = {}

        for field in self.extraction_fields:
            field_value = self._get_dotted_field_value(event, field)
            if field_value is not None:
                add_field_to(filtered_event, field, field_value)

        return filtered_event
