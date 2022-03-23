"""This module contains donothing processor that can be used for testing purposes."""

from typing import Optional, Any
from logging import Logger

from logprep.processor.base.processor import BaseProcessor
from logprep.util.processor_stats import ProcessorStats


class DoNothing(BaseProcessor):
    """A processor that does nothing with log events.

    I does return either None or extra_data if it was provided.

    Parameters
    ----------
    errors : list, optional
       A list of errors that will be raised.

    extra_data : dict, optional
       A dictionary with extra data.

    """

    def __init__(self, name: str, logger: Logger, errors: Optional[list] = None,
                 extra_data: Any = None):
        super().__init__(name, logger)
        self._logger = logger
        self.ps = ProcessorStats()

        self._errors = errors if errors is not None else []
        self._extra_data = extra_data

        self.setup_called_count = 0
        self.shut_down_called_count = 0

    def describe(self) -> str:
        return 'DoNothing'

    def process(self, event: dict) -> Any:
        if self._errors:
            error = self._errors.pop(0)
            if error is not None:
                raise error

        self.ps.increment_processed_count()
        return self._extra_data

    def setup(self):
        self.setup_called_count += 1

    def shut_down(self):
        self.shut_down_called_count += 1
