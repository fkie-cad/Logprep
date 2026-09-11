# pylint: disable=missing-docstring
# pylint: disable=protected-access
import uuid
from copy import deepcopy
from unittest import mock

import pytest

from logprep.ng.abc.event import InputMeta, LogEvent
from logprep.ng.processor.selective_extractor.filtered_event import FilteredEvent
from logprep.ng.processor.selective_extractor.processor import SelectiveExtractor
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
        event = LogEvent(event, original=b"", input_meta=InputMeta())
        await self.object.process(event)
        assert event.data == expected

    async def test_selective_extractor_does_not_change_orig_doc(self):
        document = {"user": "test_user", "other": "field"}
        exp_document = {"user": "test_user", "other": "field"}
        event = LogEvent(document, original=document, input_meta=InputMeta())
        await self.object.process(event)

        assert document == exp_document

    async def test_process_adds_filtered_event_to_extra_data(self):
        document = {"message": "test_message", "other": "field"}
        event = LogEvent(document, original=document, input_meta=InputMeta())
        event = await self.object.process(event)
        assert len(event.extra_data) == 1
        filtered_event = event.extra_data[0]
        assert isinstance(filtered_event, FilteredEvent)

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
        filtered_event = event.extra_data[0]
        assert field_name in filtered_event.data

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
        filtered_event = event.extra_data[0]
        assert filtered_event.output_name == "opensearch"
        assert filtered_event.output_target == "my topic"

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
        filtered_event = event.extra_data[0]
        assert isinstance(filtered_event, FilteredEvent)
        assert filtered_event.data == expected

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
        filtered_event = result.extra_data[0]
        assert filtered_event.data.get("other", {}).get("message") is not None

    async def test_process_clears_internal_filtered_events_list_before_every_event(self):
        document = {"message": "test_message", "other": {"message": "my message value"}}
        event = LogEvent(document, original=document, input_meta=InputMeta())
        _ = await self.object.process(event)
        assert len(self.object._event.extra_data) == 1
        event = LogEvent(document, original=document, input_meta=InputMeta())
        _ = await self.object.process(event)
        assert len(self.object._event.extra_data) == 1
