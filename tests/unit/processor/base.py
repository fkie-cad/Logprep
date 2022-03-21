# pylint: disable=missing-module-docstring
from abc import ABC, abstractmethod
from encodings import utf_8
from logging import getLogger
import json
from logprep.processor.base.processor import RuleBasedProcessor


class BaseProcessorTestCase(ABC):

    factory = None

    CONFIG = {}

    logger = getLogger()

    object = None

    @property
    @abstractmethod
    def specific_rules_dirs(self):
        """
        the specific rules_dirs for the processor
        has to be implemented
        """
        ...

    @property
    @abstractmethod
    def generic_rules_dirs(self):
        """
        the generic rules_dirs for the processor
        has to be implemented
        """
        ...

    def set_rules(self, rules_dirs):
        """
        sets the rules from the given rules_dirs
        """
        specific_rules = list()

        for specific_rules_dir in rules_dirs:
            rule_paths = RuleBasedProcessor._list_json_files_in_directory(  # pylint: disable=protected-access
                specific_rules_dir
            )
            for rule_path in rule_paths:
                with open(rule_path, "r", encoding=utf_8) as rule_file:
                    rules = json.load(rule_file)
                    for rule in rules:
                        specific_rules.append(rule)

        return specific_rules

    def setUp(self) -> None:  # pylint: disable=invalid-name
        """
        setUp class for the imported TestCase
        """
        super().setUp()  # pylint: disable=no-member
        if self.factory is not None:
            self.object = self.factory.create(
                "Test Instance Name", self.CONFIG, self.logger
            )
            self.specific_rules = self.set_rules(self.specific_rules_dirs)
            self.generic_rules = self.set_rules(self.generic_rules_dirs)

    def test_my_false(self):
        assert True
        if self.factory is None:
            assert False
