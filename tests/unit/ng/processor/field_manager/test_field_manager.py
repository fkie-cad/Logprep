# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments


import logging
import re
from copy import deepcopy

import pytest

from logprep.ng.event.log_event import LogEvent
from logprep.ng.processor.field_manager.processor import FieldManager
from logprep.processor.base.exceptions import FieldExistsWarning
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.field_manager.test_field_manager import (
    failure_test_cases as non_ng_failure_test_cases,
)
from tests.unit.processor.field_manager.test_field_manager import (
    test_cases as non_ng_test_cases,
)

test_cases = deepcopy(non_ng_test_cases)
failure_test_cases = deepcopy(non_ng_failure_test_cases)


class TestFieldManager(BaseProcessorTestCase[FieldManager]):
    CONFIG: dict = {
        "type": "ng_field_manager",
        "rules": ["tests/testdata/unit/field_manager/rules"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    async def test_testcases(
        self, testcase, rule, event, expected
    ):  # pylint: disable=unused-argument
        await self._load_rule(rule)
        event = LogEvent(event, original=b"")
        await self.object.process(event)
        assert event.data == expected

    @pytest.mark.parametrize("testcase, rule, event, expected, error", failure_test_cases)
    async def test_testcases_failure_handling(self, testcase, rule, event, expected, error):
        await self._load_rule(rule)
        event = LogEvent(event, original=b"")
        result = await self.object.process(event)
        assert len(result.warnings) == 1
        assert re.match(error, str(result.warnings[0]))
        assert event.data == expected, testcase

    async def test_process_adds_field_exists_warning_if_target_field_exists_and_should_not_be_overwritten(
        self,
    ):
        rule = {
            "filter": "field.a",
            "field_manager": {
                "source_fields": ["field.a", "field.b"],
                "target_field": "target_field",
                "overwrite_target": False,
                "delete_source_fields": False,
            },
        }
        await self._load_rule(rule)
        document = {"field": {"a": "first", "b": "second"}, "target_field": "has already content"}
        event = LogEvent(document, original=b"")
        result = await self.object.process(event)
        assert isinstance(result.warnings[0], FieldExistsWarning)
        assert "target_field" in document
        assert event.data.get("target_field") == "has already content"
        assert event.data.get("tags") == ["_field_manager_failure"]

    async def test_process_adds_processing_warning_with_missing_fields(self):
        rule = {
            "filter": "field.a",
            "field_manager": {
                "source_fields": ["does.not.exists"],
                "target_field": "target_field",
            },
        }
        await self._load_rule(rule)
        document = {"field": {"a": "first", "b": "second"}}
        event = LogEvent(document, original=b"")
        result = await self.object.process(event)
        assert len(result.warnings) == 1
        assert re.match(
            r".*ProcessingWarning.*missing source_fields: \['does.not.exists'\]",
            str(result.warnings[0]),
        )

    async def test_process_raises_processing_warning_with_missing_fields_but_event_is_processed(
        self,
    ):
        rule = {
            "filter": "field.a",
            "field_manager": {
                "mapping": {
                    "field.a": "target_field",
                    "does.not.exists": "target_field",
                }
            },
        }
        await self._load_rule(rule)
        document = {"field": {"a": "first", "b": "second"}}
        event = LogEvent(document, original=b"")
        expected = {
            "field": {"a": "first", "b": "second"},
            "target_field": "first",
            "tags": ["_field_manager_missing_field_warning"],
        }
        result = await self.object.process(event)
        assert len(result.warnings) == 1
        assert re.match(
            r".*ProcessingWarning.*missing source_fields: \['does.not.exists'\]",
            str(result.warnings[0]),
        )
        assert event.data == expected

    async def test_process_dos_not_raises_processing_warning_with_missing_fields_and_event_is_processed(
        self, caplog
    ):
        rule = {
            "filter": "field.a",
            "field_manager": {
                "mapping": {
                    "field.a": "target_field",
                    "does.not.exists": "target_field",
                },
                "ignore_missing_fields": True,
            },
        }
        await self._load_rule(rule)
        document = {"field": {"a": "first", "b": "second"}}
        event = LogEvent(document, original=b"")
        expected = {
            "field": {"a": "first", "b": "second"},
            "target_field": "first",
        }
        with caplog.at_level(logging.WARNING):
            await self.object.process(event)
        assert not re.match(
            r".*ProcessingWarning.*missing source_fields: \['does.not.exists'\]", caplog.text
        )
        assert event.data == expected
