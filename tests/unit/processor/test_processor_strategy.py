# pylint: disable=missing-docstring
# pylint: disable=protected-access
from logging import getLogger
from unittest import mock

from logprep.abc.processor import Processor
from logprep.factory import Factory
from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.processor.dissector.rule import DissectorRule
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
        generic_tree = RuleTree()
        specific_tree = RuleTree()
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
        specific_tree.add_rule(rule_one)
        specific_tree.add_rule(rule_two)
        config = {
            "type": "dissector",
            "specific_rules": [],
            "generic_rules": [],
        }
        processor = Factory.create({"custom_lister": config}, getLogger("test-logger"))
        processor._specific_tree = specific_tree
        mock_metrics = Processor.ProcessorMetrics(
            labels={}, specific_rule_tree=[], generic_rule_tree=[]
        )

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
            generic_tree=generic_tree,
            specific_tree=specific_tree,
            callback=processor._apply_rules_wrapper,
            processor_stats=mock.Mock(),
            processor_metrics=mock_metrics,
        )
        assert expected_event == event
