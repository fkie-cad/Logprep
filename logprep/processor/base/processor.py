"""This module provides the abstract base class for all processors.

New processors are created by implementing it.

"""

from typing import List, Union, Optional

from abc import abstractmethod
from os import walk, path
from logging import Logger

from logprep.framework.rule_tree.rule_tree import RuleTree


class ProcessingError(BaseException):
    """Base class for exceptions related to processing events."""

    def __init__(self, name: str, message: str):
        super().__init__(f'{name}: ({message})')


class ProcessingWarning(ProcessingError):
    """An minor error occurred - log the error but continue processing the event."""

    def __init__(self, message: str):
        super().__init__('ProcessingWarning', message)


class ProcessingWarningCollection(ProcessingError):
    """A collection of ProcessingWarnings."""

    def __init__(self, processing_warnings):
        self.processing_warnings = processing_warnings


class BaseProcessor:
    """Responsible for processing log events."""

    def __init__(self, name, logger):
        self._name = name
        self._logger = logger

        self.ps = None
        self._event = None
        self._events_processed = 0

        self.has_custom_tests = False

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

        return self._events_processed

    def shut_down(self):
        """Stop processing of this processor.

        Optional: Called when stopping the pipeline

        """

    @staticmethod
    def _get_dotted_field_value(event: dict, dotted_field: str) -> Optional[Union[dict, list, str]]:
        fields = dotted_field.split('.')
        dict_ = event
        for field in fields:
            if field in dict_:
                dict_ = dict_[field]
            else:
                return None
        return dict_

    @staticmethod
    def _field_exists(event: dict, dotted_field: str) -> bool:
        fields = dotted_field.split('.')
        dict_ = event
        for field in fields:
            if field in dict_ and isinstance(dict_, dict):
                dict_ = dict_[field]
            else:
                return False
        return True


class RuleBasedProcessor(BaseProcessor):
    """Responsible for processing log events."""

    def __init__(self, name: str, tree_config: str, logger: Logger):
        super().__init__(name, logger)
        self._rules = []
        self._tree = RuleTree(config_path=tree_config)

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

    def test_rules(self) -> dict:
        """Perform custom rule tests.

        Returns a dict with a list of test results as tuples containing a result and an expected
        result for each rule, i.e. {'RULE REPR': [('Result string', 'Expected string')]}
        Optional: Can be used in addition to regular rule tests.

        """

    @staticmethod
    def _list_json_files_in_directory(directory: str) -> List[str]:
        valid_file_paths = []
        for root, _, files in walk(directory):
            for file_name in [file for file in files if ((file.endswith('.json')
                                                         or file.endswith('.yml'))
                                                         and not file.endswith('_test.json'))]:
                valid_file_paths.append(path.join(root, file_name))
        return valid_file_paths
