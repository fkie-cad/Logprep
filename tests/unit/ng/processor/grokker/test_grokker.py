# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments

import re
from copy import deepcopy
from unittest import mock

import pytest

from logprep.factory import Factory
from logprep.ng.event.log_event import LogEvent
from logprep.processor.base.exceptions import ProcessingCriticalError
from logprep.util.getter import GetterFactory
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.grokker.test_grokker import (
    failure_test_cases as non_ng_failure_test_cases,
)
from tests.unit.processor.grokker.test_grokker import test_cases as non_ng_test_cases

test_cases = deepcopy(non_ng_test_cases)

failure_test_cases = deepcopy(non_ng_failure_test_cases)


class TestGrokker(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "ng_grokker",
        "rules": ["tests/testdata/unit/grokker/rules"],
    }

    @pytest.mark.parametrize("rule, event, expected", test_cases)
    def test_testcases(self, rule, event, expected):
        self._load_rule(rule)
        self.object.setup()
        event = LogEvent(event, original=b"")
        self.object.process(event)
        assert event.data == expected

    @pytest.mark.parametrize("rule, event, expected, error", failure_test_cases)
    def test_testcases_failure_handling(self, rule, event, expected, error):
        self._load_rule(rule)
        self.object.setup()
        event = LogEvent(event, original=b"")
        if isinstance(error, str):
            result = self.object.process(event)
            assert len(result.warnings) == 1
            assert re.match(rf".*{error}", str(result.warnings[0]))
            assert event.data == expected
        else:
            result = self.object.process(event)
            assert isinstance(result.errors[0], ProcessingCriticalError)

    def test_load_custom_patterns_from_http_as_zip_file(self):
        rule = {
            "filter": "message",
            "grokker": {"mapping": {"message": "this is %{ID:userfield}"}},
        }

        event = {"message": "this is user-456"}
        expected = {"message": "this is user-456", "userfield": "user-456"}
        archive_data = GetterFactory.from_string(
            "tests/testdata/unit/grokker/patterns.zip"
        ).get_raw()
        with mock.patch("logprep.util.getter.HttpGetter.get_raw") as mock_getter:
            mock_getter.return_value = archive_data
            config = deepcopy(self.CONFIG)
            config["custom_patterns_dir"] = (
                "http://localhost:8000/tests/testdata/unit/grokker/patterns.zip"
            )
            self.object = Factory.create({"grokker": config})
            self._load_rule(rule)
            self.object.setup()
        event = LogEvent(event, original=b"")
        self.object.process(event)
        assert event.data == expected

    def test_loads_patterns_without_custom_patterns_dir(self):
        config = deepcopy(self.CONFIG)
        config |= {
            "custom_patterns_dir": "",
        }
        grokker = Factory.create({"grokker": config})
        assert len(grokker.rules) > 0

    def test_loads_custom_patterns(self):
        rule = {
            "filter": "winlog.event_id: 123456789",
            "grokker": {"mapping": {"winlog.event_data.normalize me!": "%{ID:normalized}"}},
        }
        event = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "id-1"},
            }
        }
        expected = {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"normalize me!": "id-1"},
            },
            "normalized": "id-1",
        }
        config = deepcopy(self.CONFIG)
        config["custom_patterns_dir"] = "tests/testdata/unit/grokker/patterns/"
        self.object = Factory.create({"grokker": config})
        self._load_rule(rule)
        self.object.setup()
        event = LogEvent(event, original=b"")
        self.object.process(event)
        assert event.data == expected
