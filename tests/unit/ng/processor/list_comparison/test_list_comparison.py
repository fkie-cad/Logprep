# pylint: disable=missing-docstring

from logprep.ng.event.log_event import LogEvent
from tests.unit.ng.processor.base import BaseProcessorTestCase


class TestListComparison(BaseProcessorTestCase):
    CONFIG = {
        "type": "ng_list_comparison",
        "rules": ["tests/testdata/unit/list_comparison/rules"],
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
        "list_search_base_path": "tests/testdata/unit/list_comparison/rules",
    }

    expected_metrics: list = []

    def test_list_comparison_instantiates(self):
        rule = {
            "filter": "value",
            "list_comparison": {
                "source_fields": ["value"],
                "target_field": "matched",
                "ignore_case": True,
            },
        }
        self._load_rule(rule)
        document = {"value": "test"}
        log_event = LogEvent(document, original=b"test_message")
        self.object.process(log_event)
        assert "value" in log_event.data
