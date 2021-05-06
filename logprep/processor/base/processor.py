"""This module provides the abstract base class for all processors.

New processors are created by implementing it.

"""

from typing import List

from abc import ABCMeta, abstractmethod
from os import walk, path


class ProcessingError(BaseException):
    """Base class for exceptions related to processing events."""

    def __init__(self, name: str, message: str):
        super().__init__(f'{name}: ({message})')


class ProcessingWarning(ProcessingError):
    """An minor error occurred - log the error but continue processing the event."""

    def __init__(self, message: str):
        super().__init__('ProcessingWarning', message)


class BaseProcessor(metaclass=ABCMeta):
    """Responsible for processing log events."""

    def __init__(self):
        self.ps = None

    def setup(self):
        """Set the processor up.

        Optional: Called before processing starts.

        """

    @abstractmethod
    def describe(self):
        """Provide a brief name-like description of the processor.

        The description is indicating its type _and_ the name provided when creating it.

        Examples
        --------

        >>> Labeler(name)

        """
        return 'undescribed processor'

    @abstractmethod
    def process(self, event: dict):
        """Process a log event by modifying its values in place.

        To prevent any further processing/delete an event, remove all its contents.

        Parameters
        ----------
        event : dict
           A dictionary representing a log event.

        """

        raise NotImplementedError

    @abstractmethod
    def events_processed_count(self) -> int:
        """Return the count of documents processed by a specific instance.

        This is used for diagnostics.

        """
        return 0

    def shut_down(self):
        """Stop processing of this processor.

        Optional: Called when stopping the pipeline

        """


class RuleBasedProcessor(BaseProcessor):
    """Responsible for processing log events."""

    def setup(self):
        """Set the processor up.

        Optional: Called before processing starts.

        """

    @abstractmethod
    def describe(self) -> str:
        """Provide a brief name-like description of the processor.

        The description is indicating its type _and_ the name provided when creating it.

        Examples
        --------

        >>> Labeler(name)

        """
        return 'undescribed processor'

    @abstractmethod
    def process(self, event: dict):
        """Process a log event by modifying its values in place.

        To prevent any further processing/delete an event, remove all its contents.

        Parameters
        ----------
        event : dict
           A dictionary representing a log event.

        """

        raise NotImplementedError

    @abstractmethod
    def events_processed_count(self) -> int:
        """Return the count of documents processed by a specific instance.

        This is used for diagnostics.

        """
        return 0

    def shut_down(self):
        """Stop processing of this processor.

        Optional: Called when stopping the pipeline

        """

    @abstractmethod
    def add_rules_from_directory(*args, **kwargs):
        """Add rule from lists of directories.

        So far this can be for 'rules' or 'specific_rules' and 'generic_rules'

        """
        raise NotImplementedError

    @staticmethod
    def _list_json_files_in_directory(directory: str) -> List[str]:
        valid_file_paths = []
        for root, _, files in walk(directory):
            for file_name in [file for file in files if (file.endswith('.json') or file.endswith('.yml')) and not file.endswith('_test.json')]:
                valid_file_paths.append(path.join(root, file_name))
        return valid_file_paths
