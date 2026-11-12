# pylint: disable=missing-docstring
# pylint: disable=protected-access
import uuid
from copy import deepcopy
from unittest import mock

import pytest

from logprep.ng.abc.event import InputMeta, LogEvent
from logprep.ng.processor.selective_extractor.extracted_event import ExtractedEvent
from logprep.ng.processor.selective_extractor.processor import SelectiveExtractor
from logprep.processor.base.exceptions import ProcessingCriticalError, ProcessingWarning
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.selective_extractor.test_selective_extractor import (
    test_cases as non_ng_test_cases,
)

test_cases = deepcopy(non_ng_test_cases)


class TestSelectiveExtractor(BaseProcessorTestCase[SelectiveExtractor]):
    CONFIG = {
        "type": "selective_extractor",
        "rules": ["tests/testdata/unit/selective_extractor/rules"],
    }

    @pytest.mark.parametrize(["rule", "event", "expected", "context"], test_cases)
    async def test_testcases(self, rule, event, expected, context, provision_context):
        provision_context(context)
        await self._load_rule(rule)
        original_data = deepcopy(event)
        event = LogEvent(event, original=b"", input_meta=InputMeta())
        await self.object.process(event)
        if expected == {} and rule["selective_extractor"].get("ignore_missing_fields") is False:
            assert event.data == original_data
            assert event.extra_data == []
            assert event.warnings == []
            assert len(event.errors) == 1
            assert isinstance(event.errors[0], ProcessingCriticalError)
            return
        if "_selective_extractor_missing_field_warning" in expected.get("tags", []):
            assert event.data == expected
            assert event.extra_data == []
            assert event.errors == []
            assert len(event.warnings) == 1
            assert isinstance(event.warnings[0], ProcessingWarning)
            return
        if "event_template" in rule["selective_extractor"]:
            expected_events = [
                ExtractedEvent(expected, output_name=output_name, output_target=output_target)
                for output in rule["selective_extractor"]["outputs"]
                for output_name, output_target in output.items()
                if expected
            ]
            assert event.extra_data == expected_events
            assert event.data == original_data
            assert event.errors == []
            assert event.warnings == []
        else:
            assert event.data == expected

    async def test_selective_extractor_does_not_change_orig_doc(self):
        document = {"user": "test_user", "other": "field"}
        exp_document = {"user": "test_user", "other": "field"}
        event = LogEvent(document, original=document, input_meta=InputMeta())
        await self.object.process(event)

        assert document == exp_document

    async def test_process_adds_extracted_event_to_extra_data(self):
        document = {"message": "test_message", "field1": 1, "field2": 2}
        event = LogEvent(document, original=document, input_meta=InputMeta())
        event = await self.object.process(event)
        assert len(event.extra_data) == 1
        extracted_event = event.extra_data[0]
        assert isinstance(extracted_event, ExtractedEvent)

    async def test_process_returns_event_extra_data_with_extraction_fields_from_rule(self):
        field_name = f"{uuid.uuid4()}"
        rule = {
            "filter": field_name,
            "selective_extractor": {
                "source_fields": [field_name],
                "outputs": [{"kafka": "topic"}],
            },
        }
        await self._load_rule(rule)
        document = {field_name: "the value"}
        event = LogEvent(document, original=document, input_meta=InputMeta())
        event = await self.object.process(event)
        extracted_event = event.extra_data[0]
        assert field_name in extracted_event.data

    async def test_process_returns_selective_extractor_outputs(self):
        field_name = f"{uuid.uuid4()}"
        rule = {
            "filter": field_name,
            "selective_extractor": {
                "source_fields": [field_name],
                "outputs": [{"opensearch": "my topic"}],
            },
        }
        await self._load_rule(rule)
        document = {field_name: "test_message", "other": "field"}
        event = LogEvent(document, original=document, input_meta=InputMeta())
        event = await self.object.process(event)
        extracted_event = event.extra_data[0]
        assert extracted_event.output_name == "opensearch"
        assert extracted_event.output_target == "my topic"

    async def test_process_returns_extracted_fields(self):
        document = {"message": "test_message", "other": "field"}
        expected = {"message": "test_message"}
        rule = {
            "filter": "message",
            "selective_extractor": {
                "source_fields": ["message"],
                "outputs": [{"opensearch": "index"}],
            },
        }
        await self._load_rule(rule)
        event = LogEvent(document, original=document, input_meta=InputMeta())
        event = await self.object.process(event)
        extracted_event = event.extra_data[0]
        assert isinstance(extracted_event, ExtractedEvent)
        assert extracted_event.data == expected

    async def test_process_returns_none_when_no_extraction_field_matches(self):
        document = {"nomessage": "test_message", "other": "field"}
        event = LogEvent(document, original=document, input_meta=InputMeta())
        result = await self.object.process(event)
        assert isinstance(result, LogEvent)
        assert result.extra_data == []
        assert result.errors == []

    async def test_gets_matching_rules_from_rules_tree(self):
        matching_rules = self.object._rule_tree.get_matching_rules({"message": "the message"})
        assert isinstance(matching_rules, list)
        assert len(matching_rules) > 0

    async def test_apply_rules_is_called(self):
        with mock.patch(
            f"{self.object.__module__}.{self.object.__class__.__name__}._apply_rules"
        ) as mock_apply_rules:
            event = LogEvent({"message": "the message"}, original=b"", input_meta=InputMeta())
            await self.object.process(event)
            mock_apply_rules.assert_called()

    async def test_process_extracts_dotted_fields(self):
        rule = {
            "filter": "message",
            "selective_extractor": {
                "source_fields": ["other.message", "message"],
                "outputs": [{"opensearch": "index"}],
            },
        }
        await self._load_rule(rule)
        document = {"message": "test_message", "other": {"message": "my message value"}}
        event = LogEvent(document, original=document, input_meta=InputMeta())
        result = await self.object.process(event)
        extracted_event = result.extra_data[0]
        assert extracted_event.data.get("other", {}).get("message") is not None

    async def test_process_clears_internal_extracted_events_list_before_every_event(self):
        document = {"message": "test_message", "field1": 1, "field2": 2}
        event = LogEvent(document, original=document, input_meta=InputMeta())
        _ = await self.object.process(event)
        assert len(self.object._event.extra_data) == 1
        event = LogEvent(document, original=document, input_meta=InputMeta())
        _ = await self.object.process(event)
        assert len(self.object._event.extra_data) == 1
