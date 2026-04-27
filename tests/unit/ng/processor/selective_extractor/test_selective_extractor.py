# pylint: disable=missing-docstring
# pylint: disable=protected-access
import uuid
from unittest import mock

from logprep.ng.abc.event import OutputSpec
from logprep.ng.event.filtered_event import FilteredEvent
from logprep.ng.event.log_event import LogEvent
from logprep.ng.processor.selective_extractor.processor import SelectiveExtractor
from tests.unit.ng.processor.base import BaseProcessorTestCase


class TestSelectiveExtractor(BaseProcessorTestCase[SelectiveExtractor]):
    CONFIG = {
        "type": "ng_selective_extractor",
        "rules": ["tests/testdata/unit/selective_extractor/rules"],
    }

    async def test_selective_extractor_does_not_change_orig_doc(self):
        document = {"user": "test_user", "other": "field"}
        exp_document = {"user": "test_user", "other": "field"}
        event = LogEvent(document, original=document)
        await self.object.process(event)

        assert document == exp_document

    async def test_process_adds_filtered_event_to_extra_data(self):
        document = {"message": "test_message", "other": "field"}
        event = LogEvent(document, original=document)
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
        event = LogEvent(document, original=document)
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
        event = LogEvent(document, original=document)
        event = await self.object.process(event)
        filtered_event = event.extra_data[0]
        assert filtered_event.outputs == [
            OutputSpec(output_name="opensearch", output_target="my topic"),
        ]

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
        event = LogEvent(document, original=document)
        event = await self.object.process(event)
        filtered_event = event.extra_data[0]
        assert isinstance(filtered_event, FilteredEvent)
        assert filtered_event.data == expected

    async def test_process_returns_none_when_no_extraction_field_matches(self):
        document = {"nomessage": "test_message", "other": "field"}
        event = LogEvent(document, original=document)
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
            event = LogEvent({"message": "the message"}, original=b"")
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
        event = LogEvent(document, original=document)
        result = await self.object.process(event)
        filtered_event = result.extra_data[0]
        assert filtered_event.data.get("other", {}).get("message") is not None

    async def test_process_clears_internal_filtered_events_list_before_every_event(self):
        document = {"message": "test_message", "other": {"message": "my message value"}}
        event = LogEvent(document, original=document)
        _ = await self.object.process(event)
        assert len(self.object._event.extra_data) == 1
        event = LogEvent(document, original=document)
        _ = await self.object.process(event)
        assert len(self.object._event.extra_data) == 1

    async def test_process_extracts_dotted_fields_complains_on_missing_fields(self):
        rule = {
            "filter": "message",
            "selective_extractor": {
                "source_fields": ["other.message", "not.exists", "message"],
                "outputs": [{"opensearch": "index"}],
                "ignore_missing_fields": False,
            },
        }
        await self._load_rule(rule)
        document = {"message": "test_message", "other": {"message": "my message value"}}
        expected = {
            "message": "test_message",
            "other": {"message": "my message value"},
            "tags": ["_selective_extractor_missing_field_warning"],
        }
        event = LogEvent(document, original=document)
        await self.object.process(event)
        assert event.data == expected

    async def test_process_extracts_dotted_fields_and_ignores_missing_fields(self):
        rule = {
            "filter": "message",
            "selective_extractor": {
                "source_fields": ["other.message", "message", "not.exists"],
                "outputs": [{"opensearch": "index"}],
                "ignore_missing_fields": True,
            },
        }
        await self._load_rule(rule)
        document = {"message": "test_message", "other": {"message": "my message value"}}
        expected = {
            "message": "test_message",
            "other": {"message": "my message value"},
        }
        event = LogEvent(document, original=document)
        await self.object.process(event)
        assert event.data == expected
