# pylint: disable=duplicate-code
# pylint: disable=protected-access
# pylint: disable=missing-docstring

from logprep.ng.event.log_event import LogEvent
from tests.unit.ng.processor.base import BaseProcessorTestCase


class TestGenericResolver(BaseProcessorTestCase):
    CONFIG = {
        "type": "ng_generic_resolver",
        "rules": ["tests/testdata/unit/generic_resolver/rules"],
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }

    expected_metrics: list = []

    def test_resolve_generic_instantiates(self):
        rule = {"filter": "anything", "generic_resolver": {"field_mapping": {}}}
        self._load_rule(rule)
        document = {"anything": "test"}
        log_event = LogEvent(document, original=b"test_message")
        self.object.process(log_event)
        assert log_event.data == document
