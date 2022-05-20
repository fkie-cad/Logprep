# pylint: disable=missing-docstring
from copy import deepcopy
import pytest
from logprep.processor.delete.factory import DeleteFactory
from tests.unit.processor.base import BaseProcessorTestCase


class TestDelete(BaseProcessorTestCase):
    factory = DeleteFactory

    CONFIG = {
        "type": "delete",
        "specific_rules": ["tests/testdata/unit/delete/rules/specific/"],
        "generic_rules": ["tests/testdata/unit/delete/rules/generic/"],
        "i_really_want_to_delete_all_log_events": "I really do",
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

    def test_value_error_raised_if_ensurance_setting_not_set(self):
        config = deepcopy(self.CONFIG)
        config.pop("i_really_want_to_delete_all_log_events")
        with pytest.raises(ValueError):
            _ = DeleteFactory.create("testname", config, self.logger)
