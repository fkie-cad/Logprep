from abc import ABC, abstractmethod
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
        pass

    @property
    @abstractmethod
    def generic_rules_dirs(self):
        pass

    def set_rules(self, rules_dirs):
        specific_rules = list()

        for specific_rules_dir in rules_dirs:
            rule_paths = RuleBasedProcessor._list_json_files_in_directory(
                specific_rules_dir
            )
            for rule_path in rule_paths:
                with open(rule_path, "r") as rule_file:
                    rules = json.load(rule_file)
                    for rule in rules:
                        specific_rules.append(rule)

        return specific_rules

    def setUp(self) -> None:
        super().setUp()
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
