# pylint: disable=missing-docstring
from copy import deepcopy

import pytest

from logprep.factory import Factory
from tests.unit.processor.base import BaseProcessorTestCase


class TestDeleter(BaseProcessorTestCase):
    CONFIG = {
        "type": "deleter",
        "rules": ["tests/testdata/unit/deleter/rules"],
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
        processor = Factory.create({"test instance": deepcopy(self.CONFIG)})
        processor.setup()

        processor.process(event)
        assert not event, testcase
        assert isinstance(event, dict), testcase
