# pylint: disable=missing-module-docstring
# pylint: disable=protected-access

import json
from abc import ABC
from copy import deepcopy
from logging import getLogger
from typing import Iterable
from unittest import mock

import pytest
from ruamel.yaml import YAML

from logprep.abc.processor import Processor
from logprep.factory import Factory
from logprep.factory_error import InvalidConfigurationError
from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.processor.base.exceptions import ProcessingWarning
from logprep.processor.processor_strategy import ProcessStrategy
from logprep.util.helper import camel_to_snake
from logprep.util.json_handling import list_json_files_in_directory
from logprep.util.time_measurement import TimeMeasurement

yaml = YAML(typ="safe", pure=True)


class BaseProcessorTestCase(ABC):

    mocks: dict = {}

    CONFIG: dict = {}

    logger = getLogger()

    object: Processor = None

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

    @staticmethod
    def set_rules(rules_dirs):
        """
        sets the rules from the given rules_dirs
        """
        assert rules_dirs is not None
        assert isinstance(rules_dirs, list)
        rules = []
        for rules_dir in rules_dirs:
            rule_paths = list_json_files_in_directory(rules_dir)
            for rule_path in rule_paths:
                with open(rule_path, "r", encoding="utf8") as rule_file:
                    loaded_rules = []
                    if rule_path.endswith(".yml"):
                        loaded_rules = yaml.load_all(rule_file)
                    elif rule_path.endswith(".json"):
                        loaded_rules = json.load(rule_file)
                    for rule in loaded_rules:
                        rules.append(rule)
        return rules

    def _load_specific_rule(self, rule):
        self.object._generic_tree = RuleTree()
        self.object._specific_tree = RuleTree()
        specific_rule = self.object.rule_class._create_from_dict(rule)
        self.object._specific_tree.add_rule(specific_rule, self.logger)

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
        config = {"Test Instance Name": self.CONFIG}
        self.object = Factory.create(configuration=config, logger=self.logger)
        self.specific_rules = self.set_rules(self.specific_rules_dirs)
        self.generic_rules = self.set_rules(self.generic_rules_dirs)

    def teardown_method(self) -> None:
        """teardown for all methods"""
        while len(self.patchers) > 0:
            patcher = self.patchers.pop()
            patcher.stop()

    def test_is_a_processor_implementation(self):
        assert isinstance(self.object, Processor)

    def test_process(self):
        assert self.object.metrics.number_of_processed_events == 0
        document = {
            "event_id": "1234",
            "message": "user root logged in",
        }
        count = self.object.metrics.number_of_processed_events
        self.object.process(document)

        assert self.object.metrics.number_of_processed_events == count + 1

    def test_uses_python_slots(self):
        assert isinstance(self.object.__slots__, Iterable)

    def test_describe(self):
        describe_string = self.object.describe()
        assert f"{self.object.__class__.__name__} (Test Instance Name)" == describe_string

    def test_snake_type(self):
        assert str(self.object) == camel_to_snake(self.object.__class__.__name__)

    def test_generic_specific_rule_trees(self):
        assert isinstance(self.object._generic_tree, RuleTree)
        assert isinstance(self.object._specific_tree, RuleTree)

    def test_generic_specific_rule_trees_not_empty(self):
        assert self.object._generic_tree.get_size() > 0
        assert self.object._specific_tree.get_size() > 0

    def test_event_processed_count(self):
        assert isinstance(self.object.metrics.number_of_processed_events, int)

    def test_events_processed_count_counts(self):
        assert self.object.metrics.number_of_processed_events == 0
        document = {"foo": "bar"}
        for i in range(1, 11):
            try:
                self.object.process(document)
            except ProcessingWarning:
                pass
            assert self.object.metrics.number_of_processed_events == i

    def test_field_exists(self):
        event = {"a": {"b": "I do not matter"}}
        assert self.object._field_exists(event, "a.b")

    @mock.patch("logging.Logger.isEnabledFor", return_value=True)
    @mock.patch("logging.Logger.debug")
    def test_add_rules_from_directory_with_debug(self, mock_debug, _):
        self.object.add_rules_from_directory(
            specific_rules_dirs=self.specific_rules_dirs, generic_rules_dirs=self.generic_rules_dirs
        )
        mock_debug.assert_called()

    def test_add_rules_from_directory(self):
        self.object._generic_tree = RuleTree()
        self.object._specific_tree = RuleTree()
        generic_rules_size = self.object._generic_tree.get_size()
        specific_rules_size = self.object._specific_tree.get_size()
        self.object.add_rules_from_directory(
            specific_rules_dirs=self.specific_rules_dirs, generic_rules_dirs=self.generic_rules_dirs
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
            specific_rules_dirs=self.specific_rules_dirs, generic_rules_dirs=self.generic_rules_dirs
        )
        generic_rules_size = self.object._generic_tree.get_size()
        specific_rules_size = self.object._specific_tree.get_size()
        self.object.add_rules_from_directory(
            specific_rules_dirs=self.specific_rules_dirs, generic_rules_dirs=self.generic_rules_dirs
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

    @mock.patch("logging.Logger.debug")
    @mock.patch("logging.Logger.isEnabledFor", return_value=True)
    def test_process_writes_debug_messages(self, mock_is_enabled, mock_debug):
        event = {}
        self.object.process(event)
        mock_is_enabled.assert_called()
        mock_debug.assert_called()

    def test_config_attribute_is_config_object(self):
        assert isinstance(self.object._config, self.object.Config)

    def test_config_object_is_kw_only(self):
        attr_attributes = self.object._config.__attrs_attrs__
        for attr in attr_attributes:
            assert attr.kw_only

    @pytest.mark.parametrize("rule_list", ["specific_rules", "generic_rules"])
    def test_validation_raises_if_not_a_list(self, rule_list):
        config = deepcopy(self.CONFIG)
        config.update({rule_list: "i am not a list"})
        with pytest.raises(InvalidConfigurationError, match=r"not a list"):
            Factory.create({"test instance": config}, self.logger)

    @pytest.mark.parametrize("rule_list", ["specific_rules", "generic_rules"])
    def test_validation_raises_on_empty_rules_list(self, rule_list):
        config = deepcopy(self.CONFIG)
        config.update({rule_list: []})
        with pytest.raises(InvalidConfigurationError, match=rf"{rule_list} is empty"):
            Factory.create({"test instance": config}, self.logger)

    @pytest.mark.parametrize("rule_list", ["specific_rules", "generic_rules"])
    def test_validation_raises_if_elements_does_not_exist(self, rule_list):
        config = deepcopy(self.CONFIG)
        config.update({rule_list: ["/i/do/not/exist"]})
        with pytest.raises(
            InvalidConfigurationError, match=r"'\/i\/do\/not\/exist' does not exist"
        ):
            Factory.create({"test instance": config}, self.logger)

    @mock.patch("os.path.exists", return_value=True)
    @mock.patch("os.path.isdir", return_value=False)
    def test_validation_raises_if_element_is_not_a_directory(self, _, __):
        config = deepcopy(self.CONFIG)
        config.update({"specific_rules": ["/i/am/not/a/directory"]})
        config.update({"generic_rules": ["/i/am/not/a/directory"]})
        with pytest.raises(
            InvalidConfigurationError, match=r"'\/i\/am\/not\/a\/directory' is not a directory"
        ):
            Factory.create({"test instance": config}, self.logger)

    def test_validation_raises_if_tree_config_is_not_a_str(self):
        config = deepcopy(self.CONFIG)
        config.update({"tree_config": 12})
        with pytest.raises(InvalidConfigurationError, match=r"tree_config is not a str"):
            Factory.create({"test instance": config}, self.logger)

    def test_validation_raises_if_tree_config_is_not_exist(self):
        config = deepcopy(self.CONFIG)
        config.update({"tree_config": "/i/am/not/a/file/path"})
        with pytest.raises(
            InvalidConfigurationError,
            match=r"tree_config file '\/i\/am\/not\/a\/file\/path' does not exist",
        ):
            Factory.create({"test instance": config}, self.logger)

    def test_processor_metrics_counts_processed_events(self):
        assert self.object.metrics.number_of_processed_events == 0
        event = {}
        self.object.process(event)
        assert self.object.metrics.number_of_processed_events == 1

    @mock.patch("logprep.framework.rule_tree.rule_tree.RuleTree.get_matching_rules")
    def test_metrics_update_mean_processing_times_and_sample_counter(self, get_matching_rules_mock):
        get_matching_rules_mock.return_value = [mock.MagicMock()]
        self.object._apply_rules = mock.MagicMock()
        assert self.object.metrics.mean_processing_time_per_event == 0
        assert self.object.metrics._mean_processing_time_sample_counter == 0
        event = {"test": "event"}
        self.object.process(event)
        assert self.object.metrics.mean_processing_time_per_event > 0
        assert self.object.metrics._mean_processing_time_sample_counter == 2
