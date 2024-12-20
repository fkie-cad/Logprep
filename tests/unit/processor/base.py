# pylint: disable=missing-module-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init

import itertools
import json
from copy import deepcopy
from logging import getLogger
from pathlib import Path
from unittest import mock

import pytest
import requests
import responses
from attrs import asdict
from ruamel.yaml import YAML

from logprep.abc.processor import Processor, ProcessorResult
from logprep.factory import Factory
from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.metrics.metrics import CounterMetric, HistogramMetric
from logprep.processor.base.exceptions import ProcessingCriticalError
from logprep.processor.base.rule import Rule
from logprep.util.json_handling import list_json_files_in_directory
from tests.unit.component.base import BaseComponentTestCase

yaml = YAML(typ="safe", pure=True)


class BaseProcessorTestCase(BaseComponentTestCase):
    mocks: dict = {}

    CONFIG: dict = {}

    logger = getLogger()

    object: Processor = None

    patchers: list = None

    rules: list

    @property
    def rules_dirs(self):
        """
        gets the rules_dirs for the processor from CONFIG
        """
        return self.CONFIG.get("rules")

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

    def _load_rule(self, rule: dict | Rule):
        self.object._rule_tree = RuleTree()
        rule = self.object.rule_class._create_from_dict(rule) if isinstance(rule, dict) else rule
        self.object._rule_tree.add_rule(rule)

    def setup_method(self) -> None:
        """
        setUp class for the imported TestCase
        """
        self.patchers = []
        for name, kwargs in self.mocks.items():
            patcher = mock.patch(name, **kwargs)
            patcher.start()
            self.patchers.append(patcher)
        super().setup_method()
        self.rules = self.set_rules(self.rules_dirs)
        self.match_all_event = {
            "message": "event",
            "winlog": {
                "event_id": 1,
                "provider_name": "Microsoft-Windows-Sysmon",
                "event_data": {"IpAddress": "127.0.0.54"},
            },
            "field1": "foo",
            "field2": "bar",
            "another_random_field": "baz",
            "@timestamp": "2021-01-01T00:00:00.000Z",
            "delete_event": "does not matter",
            "irrelevant": "does not matter",
            "url": "http://example.local",
            "drop_me": "does not matter",
            "add_generic_test": "does not matter",
            "anything": "does not matter",
            "client": {"ip": "127.0.0.54"},
            "ips": ["127.0.0.54", "192.168.4.33"],
            "applyrule": "yes",
            "A": "foobarfoo",
        }  # this is an event that can be used in all processor tests, cause it matches everywhere

    def teardown_method(self) -> None:
        """teardown for all methods"""
        while len(self.patchers) > 0:
            patcher = self.patchers.pop()
            patcher.stop()

    def test_is_a_processor_implementation(self):
        assert isinstance(self.object, Processor)

    def test_rule_tree(self):
        assert isinstance(self.object._rule_tree, RuleTree)

    def test_rule_tree_not_empty(self):
        assert self.object._rule_tree.get_size() > 0

    def test_field_exists(self):
        event = {"a": {"b": "I do not matter"}}
        assert self.object._field_exists(event, "a.b")

    @mock.patch("logging.Logger.isEnabledFor", return_value=True)
    @mock.patch("logging.Logger.debug")
    def test_load_rules_with_debug(self, mock_debug, _):
        self.object.load_rules(
            rules_targets=self.rules_dirs,
        )
        mock_debug.assert_called()

    def test_load_rules(self):
        self.object._rule_tree = RuleTree()
        rules_size = self.object._rule_tree.get_size()
        self.object.load_rules(self.rules_dirs)
        new_rules_size = self.object._rule_tree.get_size()
        assert new_rules_size > rules_size

    def test_load_rules_calls_getter_factory(self):
        with mock.patch("logprep.util.getter.GetterFactory.from_string") as getter_factory:
            with pytest.raises(
                TypeError, match="must be str, bytes or bytearray, not .*MagicMock.*"
            ):
                self.object.load_rules(rules_targets=self.rules_dirs)
            getter_factory.assert_called()

    @responses.activate
    def test_accepts_http_in_rules_config(self):
        responses.add(responses.GET, "https://this.is.not.existent/bla.yml", mock.MagicMock())
        responses.add(responses.GET, "http://does.not.matter", mock.MagicMock())
        myconfig = deepcopy(self.CONFIG)
        myconfig.update(
            {"rules": ["http://does.not.matter", "https://this.is.not.existent/bla.yml"]}
        )
        with pytest.raises(TypeError, match="not .*MagicMock.*"):
            Factory.create({"http_rule_processor": myconfig})

    def test_no_redundant_rules_are_added_to_rule_tree(self):
        """
        prevents a kind of DDOS where a big amount of same rules are placed into
        in the rules directories
        ensures that every rule in rule tree is unique
        """
        self.object.load_rules(rules_targets=self.rules_dirs)
        rules_size = self.object._rule_tree.get_size()
        self.object.load_rules(rules_targets=self.rules_dirs)
        new_rules_size = self.object._rule_tree.get_size()
        assert new_rules_size == rules_size

    def test_rules_returns_all_rules(self):
        rules = self.rules
        object_rules = self.object.rules
        assert len(rules) == len(object_rules)

    @mock.patch("logging.Logger.debug")
    def test_process_writes_debug_messages(self, mock_debug):
        event = {}
        self.object.process(event)
        mock_debug.assert_called()

    def test_config_attribute_is_config_object(self):
        assert isinstance(self.object._config, self.object.Config)

    def test_config_object_is_kw_only(self):
        attr_attributes = self.object._config.__attrs_attrs__
        for attr in attr_attributes:
            assert attr.kw_only

    @pytest.mark.parametrize("rule_list", ["rules"])
    def test_validation_raises_if_not_a_list(self, rule_list):
        config = deepcopy(self.CONFIG)
        config.update({rule_list: "i am not a list"})
        with pytest.raises(TypeError, match=r"must be <class 'list'>"):
            Factory.create({"test instance": config})

    @pytest.mark.parametrize("rule_list", ["rules"])
    def test_validation_raises_if_elements_does_not_exist(self, rule_list):
        config = deepcopy(self.CONFIG)
        config.update({rule_list: ["/i/do/not/exist"]})
        with pytest.raises(FileNotFoundError):
            Factory.create({"test instance": config})

    def test_validation_raises_if_tree_config_is_not_a_str(self):
        config = deepcopy(self.CONFIG)
        config.update({"tree_config": 12})
        with pytest.raises(TypeError, match=r"must be <class 'str'>"):
            Factory.create({"test instance": config})

    def test_validation_raises_if_tree_config_is_not_exist(self):
        config = deepcopy(self.CONFIG)
        config.update({"tree_config": "/i/am/not/a/file/path"})
        with pytest.raises(FileNotFoundError):
            Factory.create({"test instance": config})

    @responses.activate
    def test_accepts_tree_config_from_http(self):
        config = deepcopy(self.CONFIG)
        config.update({"tree_config": "http://does.not.matter.bla/tree_config.yml"})
        tree_config = Path("tests/testdata/unit/tree_config.json").read_text()
        responses.add(responses.GET, "http://does.not.matter.bla/tree_config.yml", tree_config)
        processor = Factory.create({"test instance": config})
        tree_config = json.loads(tree_config)
        assert processor._rule_tree.tree_config.priority_dict == tree_config.get("priority_dict")

    @responses.activate
    def test_raises_http_error(self):
        config = deepcopy(self.CONFIG)
        config.update({"tree_config": "http://does.not.matter.bla/tree_config.yml"})
        responses.add(responses.GET, "http://does.not.matter.bla/tree_config.yml", status=404)
        with pytest.raises(requests.HTTPError):
            Factory.create({"test instance": config})

    @pytest.mark.parametrize(
        "metric_name, metric_class",
        [
            ("number_of_processed_events", CounterMetric),
            ("processing_time_per_event", HistogramMetric),
            ("number_of_warnings", CounterMetric),
            ("number_of_errors", CounterMetric),
        ],
    )
    def test_rule_has_metric(self, metric_name, metric_class):
        metric_instance = getattr(self.object.rules[0].metrics, metric_name)
        assert isinstance(metric_instance, metric_class)

    def test_no_metrics_with_same_name(self):
        metric_attributes = asdict(
            self.object.rules[0].metrics, filter=self.asdict_filter, recurse=False
        )
        pairs = itertools.combinations(metric_attributes.values(), 2)
        for metric1, metric2 in pairs:
            assert metric1.name != metric2.name, f"{metric1.name} == {metric2.name}"

    def test_process_return_result_object(self):
        event = {"some": "event"}
        result = self.object.process(event)
        assert isinstance(result, ProcessorResult)
        assert isinstance(result.data, list)
        assert isinstance(result.errors, list)
        assert result.processor_name == "Test Instance Name"

    def test_process_collects_errors_in_result_object(self):
        with mock.patch.object(
            self.object,
            "_apply_rules",
            side_effect=ProcessingCriticalError("side effect", rule=self.object.rules[0]),
        ):
            result = self.object.process(self.match_all_event)
        assert len(result.errors) > 0, "minimum one error should be in result object"

    def test_result_object_has_reference_to_event(self):
        result = self.object.process(self.match_all_event)
        assert result.event is self.match_all_event
