""" abstract module for processors"""
import os
from abc import ABC, abstractmethod
from logging import DEBUG, Logger
from multiprocessing import current_process
from typing import List, Optional, Union

from attr import define, field, validators


from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.processor.base.rule import Rule

from logprep.processor.processor_strategy import SpecificGenericProcessStrategy
from logprep.util.helper import camel_to_snake
from logprep.util.json_handling import list_json_files_in_directory
from logprep.util.processor_stats import ProcessorStats
from logprep.util.time_measurement import TimeMeasurement


class Processor(ABC):
    """Abstract Processor Class to define the Interface"""

    @define(kw_only=True)
    class Config:
        """config field description"""

        type: str = field(validator=validators.instance_of(str))
        specific_rules: List[str] = field(validator=validators.instance_of(list))
        generic_rules: List[str] = field(validator=validators.instance_of(list))
        tree_config: Optional[str] = field(
            default=None, validator=validators.optional(validators.instance_of(str))
        )

    __slots__ = [
        "name",
        "rule_class",
        "ps",
        "has_custom_tests",
        "_logger",
        "_event",
        "_specific_tree",
        "_generic_tree",
        "_config",
    ]

    name: str
    rule_class: Rule
    ps: ProcessorStats
    has_custom_tests: bool
    _config: Config
    _logger: Logger
    _event: dict
    _specific_tree: RuleTree
    _generic_tree: RuleTree

    _strategy = SpecificGenericProcessStrategy()

    def __init__(self, name: str, configuration: "Processor.Config", logger: Logger):
        self._config = configuration
        self.has_custom_tests = False
        self.name = name
        self._logger = logger
        self.ps = ProcessorStats()
        self._specific_tree = RuleTree(config_path=self._config.tree_config)
        self._generic_tree = RuleTree(config_path=self._config.tree_config)
        self.add_rules_from_directory(
            generic_rules_dirs=self._config.generic_rules,
            specific_rules_dirs=self._config.specific_rules,
        )

    def __repr__(self):
        return camel_to_snake(self.__class__.__name__)

    def setup(self):
        """Set the processor up.

        Optional: Called before processing starts.

        """

    @property
    def _specific_rules(self):
        """Returns all specific rules

        Returns
        -------
        specific_rules: list[Rule]
        """
        return self._specific_tree.rules

    @property
    def _generic_rules(self):
        """Returns all generic rules

        Returns
        -------
        generic_rules: list[Rule]
        """
        return self._generic_tree.rules

    @property
    def _rules(self):
        """Returns all rules

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
        return f"{self.__class__.__name__} ({self.name})"

    @TimeMeasurement.measure_time()
    def process(self, event: dict):
        """Process a log event by calling the implemented `process` method of the
        strategy object set in  `_strategy` attribute.

        Parameters
        ----------
        event : dict
           A dictionary representing a log event.

        """
        if self._logger.isEnabledFor(DEBUG):
            self._logger.debug("%s process event %s", self, event)
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

    def test_rules(self) -> dict:
        """Perform custom rule tests.

        Returns a dict with a list of test results as tuples containing a result and an expected
        result for each rule, i.e. {'RULE REPR': [('Result string', 'Expected string')]}
        Optional: Can be used in addition to regular rule tests.

        """

    def add_rules_from_directory(
        self, specific_rules_dirs: List[str], generic_rules_dirs: List[str]
    ):
        """method to add rules from directory"""
        for specific_rules_dir in specific_rules_dirs:
            rule_paths = list_json_files_in_directory(specific_rules_dir)
            for rule_path in rule_paths:
                rules = self.rule_class.create_rules_from_file(rule_path)
                for rule in rules:
                    self._specific_tree.add_rule(rule, self._logger)
        for generic_rules_dir in generic_rules_dirs:
            rule_paths = list_json_files_in_directory(generic_rules_dir)
            for rule_path in rule_paths:
                rules = self.rule_class.create_rules_from_file(rule_path)
                for rule in rules:
                    self._generic_tree.add_rule(rule, self._logger)
        if self._logger.isEnabledFor(DEBUG):
            self._logger.debug(
                f"{self.describe()} loaded {self._specific_tree.rule_counter} "
                f"specific rules ({current_process().name})"
            )
            self._logger.debug(
                f"{self.describe()} loaded {self._generic_tree.rule_counter} generic rules "
                f"generic rules ({current_process().name})"
            )
        self.ps.setup_rules(
            [None] * self._generic_tree.rule_counter + [None] * self._specific_tree.rule_counter
        )

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

    def _list_json_files_in_directory(self, directory: str) -> List[str]:
        """
        Collects all json and yaml files from a given directory and it's subdirectories.

        Parameters
        ----------
        directory: str
            Path to a directory which should be scanned

        Returns
        -------
        List[str]
            List of filenames in the given directory
        """
        valid_file_paths = []
        for root, _, files in os.walk(directory):
            for file_name in [
                file
                for file in files
                if (
                    (file.endswith(".json") or file.endswith(".yml"))
                    and not file.endswith("_test.json")
                )
            ]:
                valid_file_paths.append(os.path.join(root, file_name))
        return valid_file_paths
