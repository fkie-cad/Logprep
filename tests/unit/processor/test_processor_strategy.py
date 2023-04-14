# pylint: disable=missing-docstring
# pylint: disable=protected-access
import re
from logging import getLogger
from unittest import mock
from unittest.mock import call

import pytest

from logprep.abc.processor import Processor
from logprep.factory import Factory
from logprep.framework.pipeline import Pipeline
from logprep.processor.dissector.rule import DissectorRule
from logprep.processor.generic_adder.rule import GenericAdderRule
from logprep.processor.processor_strategy import SpecificGenericProcessStrategy


class TestSpecificGenericProcessStrategy:
    @mock.patch(
        "logprep.processor.processor_strategy.SpecificGenericProcessStrategy._process_generic"
    )
    @mock.patch(
        "logprep.processor.processor_strategy.SpecificGenericProcessStrategy._process_specific"
    )
    def test_process(self, mock_process_specific, mock_process_generic):
        mock_metrics = Processor.ProcessorMetrics(
            labels={}, specific_rule_tree=[], generic_rule_tree=[]
        )
        strategy = SpecificGenericProcessStrategy()
        strategy.process({}, processor_stats=mock.Mock(), processor_metrics=mock_metrics)
        mock_process_generic.assert_called()
        mock_process_specific.assert_called()

    @mock.patch(
        "logprep.processor.processor_strategy.SpecificGenericProcessStrategy._process_generic"
    )
    @mock.patch(
        "logprep.processor.processor_strategy.SpecificGenericProcessStrategy._process_specific"
    )
    def test_process_specific_before_generic(self, mock_process_specific, mock_process_generic):
        call_order = []
        mock_process_specific.side_effect = lambda *a, **kw: call_order.append(
            mock_process_specific
        )
        mock_process_generic.side_effect = lambda *a, **kw: call_order.append(mock_process_generic)
        mock_metrics = Processor.ProcessorMetrics(
            labels={}, specific_rule_tree=[], generic_rule_tree=[]
        )
        strategy = SpecificGenericProcessStrategy()
        strategy.process({}, processor_stats=mock.Mock(), processor_metrics=mock_metrics)
        assert call_order == [mock_process_specific, mock_process_generic]

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
        processor._strategy.process(
            event,
            generic_tree=processor._generic_tree,
            specific_tree=processor._specific_tree,
            callback=processor._apply_rules_wrapper,
            processor_stats=mock.Mock(),
            processor_metrics=mock.MagicMock(),
        )
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
        processor._strategy.process(
            event,
            generic_tree=processor._generic_tree,
            specific_tree=processor._specific_tree,
            callback=processor._apply_rules_wrapper,
            processor_stats=mock.Mock(),
            processor_metrics=mock.MagicMock(),
        )
        assert expected_event == event

    @pytest.mark.parametrize("execution_number", range(5))  # repeat test to ensure determinism
    def test_strategy_applies_rules_in_deterministic_order(self, execution_number):
        config = {"type": "generic_adder", "specific_rules": [], "generic_rules": []}
        processor = Factory.create({"custom_lister": config}, getLogger("test-logger"))
        rule_one_dict = {"filter": "val", "generic_adder": {"add": {"some": "value"}}}
        rule_two_dict = {"filter": "NOT something", "generic_adder": {"add": {"something": "else"}}}
        rule_one = GenericAdderRule._create_from_dict(rule_one_dict)
        rule_two = GenericAdderRule._create_from_dict(rule_two_dict)
        processor._specific_tree.add_rule(rule_one)
        processor._specific_tree.add_rule(rule_two)
        event = {"val": "content"}
        mock_callback = mock.MagicMock()
        processor._strategy.process(
            event=event,
            generic_tree=processor._generic_tree,
            specific_tree=processor._specific_tree,
            callback=mock_callback,
            processor_stats=mock.Mock(),
            processor_metrics=mock.MagicMock(),
        )
        expected_call_order = [call(event, rule_one), call(event, rule_two)]
        assert (
            mock_callback.mock_calls == expected_call_order
        ), f"Wrong call order in test {execution_number}"

    def test_strategy_processes_generic_rules_after_processor_error_in_specific_rules(self, capsys):
        config = {
            "pipeline": [
                {"adder": {"type": "generic_adder", "specific_rules": [], "generic_rules": []}}
            ]
        }
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
        captured = capsys.readouterr()
        assert re.match("FieldExistsWarning in GenericAdder.*first", captured.err)
        assert event == expected_event
