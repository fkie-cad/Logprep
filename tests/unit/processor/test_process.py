# pylint: disable=missing-docstring
# pylint: disable=protected-access
import re
from unittest import mock
from unittest.mock import call

import pytest

from logprep.factory import Factory
from logprep.framework.pipeline import Pipeline
from logprep.processor.base.exceptions import FieldExistsWarning
from logprep.processor.dissector.rule import DissectorRule
from logprep.processor.generic_adder.rule import GenericAdderRule
from logprep.util.configuration import Configuration


class TestSpecificGenericProcessing:
    @mock.patch("logprep.abc.processor.Processor._process_rule_tree")
    def test_process(self, mock_process_rule_tree):
        processor = Factory.create(
            {
                "dummy": {
                    "type": "calculator",
                    "rules": [],
                }
            }
        )
        processor.process({})
        mock_process_rule_tree.assert_called()
        assert mock_process_rule_tree.call_count == 1

    def test_apply_processor_multiple_times_until_no_new_rule_matches(self):
        config = {
            "type": "dissector",
            "rules": [],
            "apply_multiple_times": True,
        }
        processor = Factory.create({"custom_lister": config})
        rule_one_dict = {
            "filter": "message",
            "dissector": {"mapping": {"message": "%{time} [%{protocol}] %{url}"}},
        }
        rule_two_dict = {
            "filter": "protocol",
            "dissector": {"mapping": {"protocol": "%{proto} %{col}"}},
        }
        rule_one = DissectorRule._create_from_dict(rule_one_dict)
        rule_two = DissectorRule._create_from_dict(rule_two_dict)
        processor._rule_tree.add_rule(rule_one)
        processor._rule_tree.add_rule(rule_two)
        event = {"message": "time [proto col] url"}
        expected_event = {
            "message": "time [proto col] url",
            "proto": "proto",
            "col": "col",
            "protocol": "proto col",
            "time": "time",
            "url": "url",
        }
        processor.process(event)
        assert event == expected_event

    def test_apply_processor_multiple_times_not_enabled(self):
        config = {"type": "dissector", "rules": []}
        processor = Factory.create({"custom_lister": config})
        rule_one_dict = {
            "filter": "message",
            "dissector": {"mapping": {"message": "%{time} [%{protocol}] %{url}"}},
        }
        rule_two_dict = {
            "filter": "protocol",
            "dissector": {"mapping": {"protocol": "%{proto} %{col}"}},
        }
        rule_one = DissectorRule._create_from_dict(rule_one_dict)
        rule_two = DissectorRule._create_from_dict(rule_two_dict)
        processor._rule_tree.add_rule(rule_one)
        processor._rule_tree.add_rule(rule_two)
        event = {"message": "time [proto col] url"}
        expected_event = {
            "message": "time [proto col] url",
            "protocol": "proto col",
            "time": "time",
            "url": "url",
        }
        processor.process(event)
        assert expected_event == event

    @pytest.mark.parametrize("execution_number", range(5))  # repeat test to ensure determinism
    def test_applies_rules_in_deterministic_order(self, execution_number):
        config = {"type": "generic_adder", "rules": []}
        processor = Factory.create({"custom_lister": config})
        rule_one_dict = {"filter": "val", "generic_adder": {"add": {"some": "value"}}}
        rule_two_dict = {"filter": "NOT something", "generic_adder": {"add": {"something": "else"}}}
        rule_one = GenericAdderRule._create_from_dict(rule_one_dict)
        rule_two = GenericAdderRule._create_from_dict(rule_two_dict)
        processor._rule_tree.add_rule(rule_one)
        processor._rule_tree.add_rule(rule_two)
        event = {"val": "content"}
        with mock.patch("logprep.abc.processor.Processor._apply_rules_wrapper") as mock_callback:
            expected_call_order = [call(event, rule_one), call(event, rule_two)]
            processor.process(event=event)
            mock_callback.assert_has_calls(expected_call_order, any_order=False)
