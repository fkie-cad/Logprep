# pylint: disable=missing-docstring
# pylint: disable=protected-access
from logging import getLogger
from unittest import mock
from unittest.mock import call

import pytest

from logprep.factory import Factory
from logprep.framework.pipeline import Pipeline
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
                    "generic_rules": [],
                    "specific_rules": [],
                }
            },
            mock.MagicMock(),
        )
        processor.process({})
        mock_process_rule_tree.assert_called()
        assert mock_process_rule_tree.call_count == 2

    @mock.patch("logprep.abc.processor.Processor._process_rule_tree")
    def test_process_specific_before_generic(self, mock_process_rule_tree):
        processor = Factory.create(
            {
                "dummy": {
                    "type": "calculator",
                    "generic_rules": [],
                    "specific_rules": [],
                }
            },
            mock.MagicMock(),
        )
        processor.process({})
        assert mock_process_rule_tree.call_count == 2
        mock_calls = [
            call({}, processor._specific_tree),
            call({}, processor._generic_tree),
        ]
        mock_process_rule_tree.assert_has_calls(mock_calls, any_order=False)

    def test_apply_processor_multiple_times_until_no_new_rule_matches(self):
        config = {
            "type": "dissector",
            "specific_rules": [],
            "generic_rules": [],
            "apply_multiple_times": True,
        }
        processor = Factory.create({"custom_lister": config}, getLogger("test-logger"))
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
        processor._specific_tree.add_rule(rule_one)
        processor._specific_tree.add_rule(rule_two)
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
        assert expected_event == event

    def test_apply_processor_multiple_times_not_enabled(self):
        config = {"type": "dissector", "specific_rules": [], "generic_rules": []}
        processor = Factory.create({"custom_lister": config}, getLogger("test-logger"))
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
        processor._specific_tree.add_rule(rule_one)
        processor._specific_tree.add_rule(rule_two)
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
        config = {"type": "generic_adder", "specific_rules": [], "generic_rules": []}
        processor = Factory.create({"custom_lister": config}, getLogger("test-logger"))
        rule_one_dict = {"filter": "val", "generic_adder": {"add": {"some": "value"}}}
        rule_two_dict = {"filter": "NOT something", "generic_adder": {"add": {"something": "else"}}}
        rule_one = GenericAdderRule._create_from_dict(rule_one_dict)
        rule_two = GenericAdderRule._create_from_dict(rule_two_dict)
        processor._specific_tree.add_rule(rule_one)
        processor._specific_tree.add_rule(rule_two)
        event = {"val": "content"}
        with mock.patch("logprep.abc.processor.Processor._apply_rules_wrapper") as mock_callback:
            expected_call_order = [call(event, rule_one), call(event, rule_two)]
            processor.process(event=event)
            mock_callback.assert_has_calls(expected_call_order, any_order=False)

    @mock.patch("logging.Logger.warning")
    def test_processes_generic_rules_after_processor_error_in_specific_rules(self, mock_warning):
        config = Configuration()
        config.pipeline = [
            {"adder": {"type": "generic_adder", "specific_rules": [], "generic_rules": []}}
        ]
        specific_rule_one_dict = {
            "filter": "val",
            "generic_adder": {"add": {"first": "value", "second": "value"}},
        }
        specific_rule_two_dict = {
            "filter": "val",
            "generic_adder": {"add": {"third": "value", "fourth": "value"}},
        }
        generic_rule_dict = {
            "filter": "val",
            "generic_adder": {"add": {"fifth": "value", "sixth": "value"}},
        }
        specific_rule_one = GenericAdderRule._create_from_dict(specific_rule_one_dict)
        specific_rule_two = GenericAdderRule._create_from_dict(specific_rule_two_dict)
        generic_rule = GenericAdderRule._create_from_dict(generic_rule_dict)
        event = {"val": "content", "first": "exists already"}
        expected_event = {
            "val": "content",
            "first": "exists already",
            "second": "value",
            "third": "value",
            "fourth": "value",
            "fifth": "value",
            "sixth": "value",
            "tags": ["_generic_adder_failure"],
        }
        pipeline = Pipeline(config=config)
        pipeline._pipeline[0]._generic_tree.add_rule(generic_rule)
        pipeline._pipeline[0]._specific_tree.add_rule(specific_rule_two)
        pipeline._pipeline[0]._specific_tree.add_rule(specific_rule_one)
        pipeline.process_event(event)
        assert (
            "The following fields could not be written, "
            "because one or more subfields existed and could not be extended: first"
            in mock_warning.call_args[0][0]
        )
        assert event == expected_event
