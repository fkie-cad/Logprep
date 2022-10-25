# pylint: disable=missing-docstring
import pytest
from tests.unit.processor.base import BaseProcessorTestCase


class TestDeleter(BaseProcessorTestCase):

    CONFIG = {
        "type": "deleter",
        "specific_rules": ["tests/testdata/unit/deleter/rules/specific/"],
        "generic_rules": ["tests/testdata/unit/deleter/rules/generic/"],
    }

    @pytest.mark.parametrize(
        "event, testcase",
        [
            ({"not_needed_message": "i am not needed anymore"}, "deletes simple event"),
            (
                {"not_needed_message": {"nested_block": {"deeper": "string"}}},
                "deletes nested events",
            ),
            ({}, "deletes empty event"),
        ],
    )
    def test_process_deletes_event(self, event, testcase):
        self.object.process(event)
        assert not event, testcase
        assert isinstance(event, dict), testcase
