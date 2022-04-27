"""This module provides the abstract base class for all processors.

New processors are created by implementing it.

"""

from typing import List, Union, Optional

from abc import abstractmethod
from os import walk, path
from logging import Logger


from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.processor.processor_strategy import SpecificGenericProcessStrategy
from logprep.util.time_measurement import TimeMeasurement


class ProcessingError(BaseException):
    """Base class for exceptions related to processing events."""

    def __init__(self, name: str, message: str):
        super().__init__(f"{name}: ({message})")


class ProcessingWarning(ProcessingError):
    """An minor error occurred - log the error but continue processing the event."""

    def __init__(self, message: str):
        super().__init__("ProcessingWarning", message)


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

        self.has_custom_tests = False

    @property
    def name(self):
        """Name of Processor as property"""
        return self._name

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
        return "undescribed processor"

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

    def shut_down(self):
        """Stop processing of this processor.

        Optional: Called when stopping the pipeline

        """

    @staticmethod
    def _get_dotted_field_value(event: dict, dotted_field: str) -> Optional[Union[dict, list, str]]:
        fields = dotted_field.split(".")
        dict_ = event
        for field in fields:
            if field in dict_:
                dict_ = dict_[field]
            else:
                return None
        return dict_

    @staticmethod
    def _field_exists(event: dict, dotted_field: str) -> bool:
        fields = dotted_field.split(".")
        dict_ = event
        for field in fields:
            if field in dict_ and isinstance(dict_, dict):
                dict_ = dict_[field]
            else:
                return False
        return True


class RuleBasedProcessor(BaseProcessor):
    """Responsible for processing log events."""

    _strategy = SpecificGenericProcessStrategy()

    def __init__(self, name: str, tree_config: str, logger: Logger):
        super().__init__(name, logger)
        self._specific_tree = RuleTree(config_path=tree_config)
        self._generic_tree = RuleTree(config_path=tree_config)

    def setup(self):
        """Set the processor up.

        Optional: Called before processing starts.

        """

    @property
    def _specific_rules(self):
        """
        returns all specific rules

        Returns
        -------
        specific_rules: list[Rule]
        """
        return self._specific_tree.rules

    @property
    def _generic_rules(self):
        """
        returns all generic rules

        Returns
        -------
        generic_rules: list[Rule]
        """
        return self._generic_tree.rules

    @property
    def _rules(self):
        """
        returns all rules

        Returns
        -------
        rules: list[Rule]
        """
        return [*self._generic_rules, *self._specific_rules]

    def describe(self) -> str:
        """Provide a brief name-like description of the processor.

        The description is indicating its type _and_ the name provided when creating it.

        Examples
        --------

        >>> Labeler(name)

        """
        return f"{self.__class__.__name__} ({self._name})"

    @TimeMeasurement.measure_time()
    def process(self, event: dict):
        """
        Process a log event by calling the implemented `process` method of the
        strategy object set in  `_strategy` attribute.

        Parameters
        ----------
        event : dict
           A dictionary representing a log event.

        """

        self._strategy.process(
            event,
            generic_tree=self._generic_tree,
            specific_tree=self._specific_tree,
            callback=self._apply_rules,
            processor_stats=self.ps,
        )

    @abstractmethod
    def _apply_rules(self, event, rule):
        ...

    def shut_down(self):
        """Stop processing of this processor.

        Optional: Called when stopping the pipeline

        """

    @abstractmethod
    def add_rules_from_directory(self, *args, **kwargs):
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
            for file_name in [
                file
                for file in files
                if (
                    (file.endswith(".json") or file.endswith(".yml"))
                    and not file.endswith("_test.json")
                )
            ]:
                valid_file_paths.append(path.join(root, file_name))
        return valid_file_paths
