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

from logprep.abc.processor import Processor
from logprep.factory import Factory
from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.metrics.metrics import CounterMetric, HistogramMetric
from logprep.util.json_handling import list_json_files_in_directory
from tests.unit.component.base import BaseComponentTestCase

yaml = YAML(typ="safe", pure=True)


class BaseProcessorTestCase(BaseComponentTestCase):
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
        self.patchers = []
        for name, kwargs in self.mocks.items():
            patcher = mock.patch(name, **kwargs)
            patcher.start()
            self.patchers.append(patcher)
        super().setup_method()
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

    def test_generic_specific_rule_trees(self):
        assert isinstance(self.object._generic_tree, RuleTree)
        assert isinstance(self.object._specific_tree, RuleTree)

    def test_generic_specific_rule_trees_not_empty(self):
        assert self.object._generic_tree.get_size() > 0
        assert self.object._specific_tree.get_size() > 0

    def test_field_exists(self):
        event = {"a": {"b": "I do not matter"}}
        assert self.object._field_exists(event, "a.b")

    @mock.patch("logging.Logger.isEnabledFor", return_value=True)
    @mock.patch("logging.Logger.debug")
    def test_load_rules_with_debug(self, mock_debug, _):
        self.object.load_rules(
            specific_rules_targets=self.specific_rules_dirs,
            generic_rules_targets=self.generic_rules_dirs,
        )
        mock_debug.assert_called()

    def test_load_rules(self):
        self.object._generic_tree = RuleTree()
        self.object._specific_tree = RuleTree()
        generic_rules_size = self.object._generic_tree.get_size()
        specific_rules_size = self.object._specific_tree.get_size()
        self.object.load_rules(
            specific_rules_targets=self.specific_rules_dirs,
            generic_rules_targets=self.generic_rules_dirs,
        )
        new_generic_rules_size = self.object._generic_tree.get_size()
        new_specific_rules_size = self.object._specific_tree.get_size()
        assert new_generic_rules_size > generic_rules_size
        assert new_specific_rules_size > specific_rules_size

    def test_load_rules_calls_getter_factory(self):
        with mock.patch("logprep.util.getter.GetterFactory.from_string") as getter_factory:
            with pytest.raises(
                TypeError, match="must be str, bytes or bytearray, not .*MagicMock.*"
            ):
                self.object.load_rules(
                    specific_rules_targets=self.specific_rules_dirs,
                    generic_rules_targets=self.generic_rules_dirs,
                )
            getter_factory.assert_called()

    @responses.activate
    def test_accepts_http_in_rules_config(self):
        responses.add(responses.GET, "https://this.is.not.existent/bla.yml", mock.MagicMock())
        responses.add(responses.GET, "http://does.not.matter", mock.MagicMock())
        myconfig = deepcopy(self.CONFIG)
        myconfig.update(
            {"specific_rules": ["http://does.not.matter", "https://this.is.not.existent/bla.yml"]}
        )
        myconfig.update(
            {"generic_rules": ["http://does.not.matter", "https://this.is.not.existent/bla.yml"]}
        )
        with pytest.raises(TypeError, match="not .*MagicMock.*"):
            Factory.create({"http_rule_processor": myconfig}, self.logger)

    def test_no_redundant_rules_are_added_to_rule_tree(self):
        """
        prevents a kind of DDOS where a big amount of same rules are placed into
        in the rules directories
        ensures that every rule in rule tree is unique
        """
        self.object.load_rules(
            specific_rules_targets=self.specific_rules_dirs,
            generic_rules_targets=self.generic_rules_dirs,
        )
        generic_rules_size = self.object._generic_tree.get_size()
        specific_rules_size = self.object._specific_tree.get_size()
        self.object.load_rules(
            specific_rules_targets=self.specific_rules_dirs,
            generic_rules_targets=self.generic_rules_dirs,
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
        object_rules_count = len(self.object.rules)
        assert all_rules_count == object_rules_count

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

    @pytest.mark.parametrize("rule_list", ["specific_rules", "generic_rules"])
    def test_validation_raises_if_not_a_list(self, rule_list):
        config = deepcopy(self.CONFIG)
        config.update({rule_list: "i am not a list"})
        with pytest.raises(TypeError, match=r"must be <class 'list'>"):
            Factory.create({"test instance": config}, self.logger)

    @pytest.mark.parametrize("rule_list", ["specific_rules", "generic_rules"])
    def test_validation_raises_if_elements_does_not_exist(self, rule_list):
        config = deepcopy(self.CONFIG)
        config.update({rule_list: ["/i/do/not/exist"]})
        with pytest.raises(FileNotFoundError):
            Factory.create({"test instance": config}, self.logger)

    def test_validation_raises_if_tree_config_is_not_a_str(self):
        config = deepcopy(self.CONFIG)
        config.update({"tree_config": 12})
        with pytest.raises(TypeError, match=r"must be <class 'str'>"):
            Factory.create({"test instance": config}, self.logger)

    def test_validation_raises_if_tree_config_is_not_exist(self):
        config = deepcopy(self.CONFIG)
        config.update({"tree_config": "/i/am/not/a/file/path"})
        with pytest.raises(FileNotFoundError):
            Factory.create({"test instance": config}, self.logger)

    @responses.activate
    def test_accepts_tree_config_from_http(self):
        config = deepcopy(self.CONFIG)
        config.update({"tree_config": "http://does.not.matter.bla/tree_config.yml"})
        tree_config = Path("tests/testdata/unit/tree_config.json").read_text()
        responses.add(responses.GET, "http://does.not.matter.bla/tree_config.yml", tree_config)
        processor = Factory.create({"test instance": config}, self.logger)
        assert (
            processor._specific_tree._processor_config.tree_config
            == "http://does.not.matter.bla/tree_config.yml"
        )
        tree_config = json.loads(tree_config)
        assert processor._specific_tree.priority_dict == tree_config.get("priority_dict")

    @responses.activate
    def test_raises_http_error(self):
        config = deepcopy(self.CONFIG)
        config.update({"tree_config": "http://does.not.matter.bla/tree_config.yml"})
        responses.add(responses.GET, "http://does.not.matter.bla/tree_config.yml", status=404)
        with pytest.raises(requests.HTTPError):
            Factory.create({"test instance": config}, self.logger)

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
