# pylint: disable=missing-module-docstring
# pylint: disable=protected-access
import json
import re
from abc import ABC
from logging import getLogger

from unittest import mock


from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.processor.base.processor import (
    BaseProcessor,
    ProcessingWarning,
    RuleBasedProcessor,
)
from logprep.processor.processor_strategy import ProcessStrategy
from logprep.util.helper import camel_to_snake
from logprep.util.time_measurement import TimeMeasurement


class BaseProcessorTestCase(ABC):

    mocks: dict = {}

    factory = None

    CONFIG: dict = {}

    logger = getLogger()

    object: BaseProcessor = None

    patchers: list = None

    specific_rules: list

    generic_rules: list

    @property
    def specific_rules_dirs(self):
        """
        gets the specific rules_dirs for the processor from CONFIG
        """
        return self.CONFIG.get("specific_rules")

    @property
    def generic_rules_dirs(self):
        """
        gets the generic rules_dirs for the processor from CONFIG
        """
        return self.CONFIG.get("generic_rules")

    def set_rules(self, rules_dirs):
        """
        sets the rules from the given rules_dirs
        """
        assert rules_dirs is not None
        assert isinstance(rules_dirs, list)
        rules = []

        for rules_dir in rules_dirs:
            rule_paths = RuleBasedProcessor._list_json_files_in_directory(  # pylint: disable=protected-access
                rules_dir
            )
            for rule_path in rule_paths:
                with open(rule_path, "r", encoding="utf8") as rule_file:
                    loaded_rules = json.load(rule_file)
                    for rule in loaded_rules:
                        rules.append(rule)

        return rules

    def setup_method(self) -> None:
        """
        setUp class for the imported TestCase
        """
        TimeMeasurement.TIME_MEASUREMENT_ENABLED = False
        TimeMeasurement.APPEND_TO_EVENT = False
        self.patchers = []
        for name, kwargs in self.mocks.items():
            patcher = mock.patch(name, **kwargs)
            patcher.start()
            self.patchers.append(patcher)
        if self.factory is not None:
            self.object = self.factory.create(
                name="Test Instance Name", configuration=self.CONFIG, logger=self.logger
            )
            self.specific_rules = self.set_rules(self.specific_rules_dirs)
            self.generic_rules = self.set_rules(self.generic_rules_dirs)

    def teardown_method(self) -> None:
        """teardown for all methods"""
        while len(self.patchers) > 0:
            patcher = self.patchers.pop()
            patcher.stop()

    def test_is_a_processor_implementation(self):
        assert isinstance(self.object, RuleBasedProcessor)

    def test_process(self):
        assert self.object.ps.processed_count == 0
        document = {
            "event_id": "1234",
            "message": "user root logged in",
        }
        count = self.object.ps.processed_count
        self.object.process(document)

        assert self.object.ps.processed_count == count + 1

    def test_describe(self):
        describe_string = self.object.describe()
        assert f"{self.object.__class__.__name__} (Test Instance Name)" == describe_string

    def test_generic_specific_rule_trees(self):
        assert isinstance(self.object._generic_tree, RuleTree)
        assert isinstance(self.object._specific_tree, RuleTree)

    def test_generic_specific_rule_trees_not_empty(self):
        assert self.object._generic_tree.get_size() > 0
        assert self.object._specific_tree.get_size() > 0

    def test_event_processed_count(self):
        assert isinstance(self.object.ps.processed_count, int)

    def test_events_processed_count_counts(self):
        assert self.object.ps.processed_count == 0
        document = {"foo": "bar"}
        for i in range(1, 11):
            try:
                self.object.process(document)
            except ProcessingWarning:
                pass
            assert self.object.ps.processed_count == i

    def test_get_dotted_field_value_returns_none_if_not_found(self):
        event = {"some": "i do not matter"}
        dotted_field = "i.do.not.exist"
        value = self.object._get_dotted_field_value(event, dotted_field)
        assert value is None

    def test_get_dotted_field_value_returns_value(self):
        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 1111,
                "event_data": {
                    "param1": "Do not normalize me!",
                    "test1": "Normalize me!",
                },
            }
        }
        dotted_field = "winlog.event_data.test1"
        value = self.object._get_dotted_field_value(event, dotted_field)
        assert value == "Normalize me!"

    def test_field_exists(self):
        event = {"a": {"b": "I do not matter"}}
        assert self.object._field_exists(event, "a.b")

    def test_add_rules_from_directory(self):
        generic_rules_size = self.object._generic_tree.get_size()
        specific_rules_size = self.object._specific_tree.get_size()
        self.object.add_rules_from_directory(
            specific_rules_dirs=self.generic_rules_dirs, generic_rules_dirs=self.specific_rules_dirs
        )
        new_generic_rules_size = self.object._generic_tree.get_size()
        new_specific_rules_size = self.object._specific_tree.get_size()
        assert new_generic_rules_size > generic_rules_size
        assert new_specific_rules_size > specific_rules_size

    def test_no_redundant_rules_are_added_to_rule_tree(self):
        """
        prevents a kind of DDOS where a big amount of same rules are placed into
        in the rules directories
        ensures that every rule in rule tree is unique
        """
        self.object.add_rules_from_directory(
            specific_rules_dirs=self.generic_rules_dirs, generic_rules_dirs=self.specific_rules_dirs
        )
        generic_rules_size = self.object._generic_tree.get_size()
        specific_rules_size = self.object._specific_tree.get_size()
        self.object.add_rules_from_directory(
            specific_rules_dirs=self.generic_rules_dirs, generic_rules_dirs=self.specific_rules_dirs
        )
        new_generic_rules_size = self.object._generic_tree.get_size()
        new_specific_rules_size = self.object._specific_tree.get_size()
        assert new_generic_rules_size == generic_rules_size
        assert new_specific_rules_size == specific_rules_size

    def test_specific_rules_returns_all_specific_rules(self):
        specific_rules = self.specific_rules
        object_specific_rules = self.object._specific_rules
        assert len(specific_rules) == len(object_specific_rules)

    def test_generic_rules_returns_all_generic_rules(self):
        generic_rules = self.generic_rules
        object_generic_rules = self.object._generic_rules
        assert len(generic_rules) == len(object_generic_rules)

    def test_rules_returns_all_specific_and_generic_rules(self):
        generic_rules = self.generic_rules
        specific_rules = self.specific_rules
        all_rules_count = len(generic_rules) + len(specific_rules)
        object_rules_count = len(self.object._rules)
        assert all_rules_count == object_rules_count

    def test_process_strategy_returns_strategy_object(self):
        assert isinstance(self.object._strategy, ProcessStrategy)

    def test_process_calls_strategy(self):
        """
        This test method needs to be overwritten in your ProcessorTests
        if your processor uses another strategy
        """
        with mock.patch(
            "logprep.processor.processor_strategy.SpecificGenericProcessStrategy.process"
        ) as mock_strategy_process:
            self.object.process({})
            mock_strategy_process.assert_called()

    def test_process_is_measured(self):
        TimeMeasurement.TIME_MEASUREMENT_ENABLED = True
        TimeMeasurement.APPEND_TO_EVENT = True
        event = {}
        self.object.process(event)
        processing_times = event.get("processing_times")
        assert processing_times

    def test_process_measurements_appended_under_processor_config_name(self):
        TimeMeasurement.TIME_MEASUREMENT_ENABLED = True
        TimeMeasurement.APPEND_TO_EVENT = True
        event = {}
        self.object.process(event)
        processing_times = event.get("processing_times")
        config_name = camel_to_snake(self.object.__class__.__name__)
        assert processing_times[config_name]
        assert isinstance(processing_times[config_name], float)
