# pylint: disable=missing-docstring
# pylint: disable=protected-access
import uuid
from unittest import mock

import pytest

from logprep.abc.processor import ProcessorResult
from logprep.processor.selective_extractor.rule import SelectiveExtractorRule
from tests.conftest import normalize_test_cases
from tests.unit.processor.base import BaseProcessorTestCase

example_test_cases = [
    pytest.param(
        {
            "filter": "message",
            "selective_extractor": {
                "source_fields": ["other.message", "not.exists", "message"],
                "outputs": [{"opensearch": "index"}],
                "ignore_missing_fields": False,
            },
        },
        {"message": "test_message", "other": {"message": "my message value"}},
        {
            "message": "test_message",
            "other": {"message": "my message value"},
            "tags": ["_selective_extractor_missing_field_warning"],
        },
        id="test process extracts dotted fields and complains on missing fields",
    ),
    pytest.param(
        {
            "filter": "message",
            "selective_extractor": {
                "event_template": {"value": "foo", "status": "SUCCESS"},
                "outputs": [{"opensearch": "index"}],
            },
        },
        {"message": "test_message"},
        {"value": "foo", "status": "SUCCESS"},
        id="event template creates an extra event from constant values",
    ),
    pytest.param(
        {
            "filter": "message",
            "selective_extractor": {
                "event_template": {
                    "content": {
                        "message": "${message}",
                        "other_message": "${other.message}",
                    }
                },
                "outputs": [{"opensearch": "index"}],
            },
        },
        {"message": "test_message", "other": {"message": "my message value"}},
        {"content": {"message": "test_message", "other_message": "my message value"}},
        id="event template substitutes field values and dotted field values",
    ),
    pytest.param(
        {
            "filter": "list_update",
            "selective_extractor": {
                "event_template": {
                    "@timestamp": "${@timestamp}",
                    "status": "NEW",
                    "list_name": "some_list_name",
                    "command_type": "WRITE_ENTRY",
                    "command_arguments": {
                        "content": {
                            "set": "${set}",
                            "key": "${key}",
                            "value": "${value}",
                        }
                    },
                },
                "outputs": [{"opensearch": "list-updates"}],
            },
        },
        {
            "list_update": True,
            "@timestamp": "2026-09-28T10:00:00Z",
            "set": "my_subset",
            "key": "my_key",
            "value": 42,
        },
        {
            "@timestamp": "2026-09-28T10:00:00Z",
            "status": "NEW",
            "list_name": "some_list_name",
            "command_type": "WRITE_ENTRY",
            "command_arguments": {
                "content": {"set": "my_subset", "key": "my_key", "value": 42}
            },
        },
        id="event template creates a nested extra event and preserves value types",
    ),
    pytest.param(
        {
            "filter": "list_update",
            "selective_extractor": {
                "event_template": {
                    "@timestamp": "${@timestamp}",
                    "status": "NEW",
                    "list_name": "some_list_name",
                    "command_type": "WRITE_ENTRY",
                    "command_arguments": {
                        "content": {
                            "set": "${set}",
                            "key": "${key}",
                            "value": "${int_value}",
                        }
                    },
                },
                "to_string": ["int_value"],
                "outputs": [{"opensearch": "list-updates"}],
            },
        },
        {
            "list_update": True,
            "@timestamp": "2026-09-28T10:00:00Z",
            "set": "my_subset",
            "key": "my_key",
            "int_value": 42,
        },
        {
            "@timestamp": "2026-09-28T10:00:00Z",
            "status": "NEW",
            "list_name": "some_list_name",
            "command_type": "WRITE_ENTRY",
            "command_arguments": {
                "content": {"set": "my_subset", "key": "my_key", "value": "42"}
            },
        },
        id="event template creates a nested extra event and converts selected values to string",
    ),
]

test_cases = normalize_test_cases(
    *example_test_cases,
    pytest.param(
        {
            "filter": "message",
            "selective_extractor": {
                "source_fields": ["other.message", "message", "not.exists"],
                "outputs": [{"opensearch": "index"}],
                "ignore_missing_fields": True,
            },
        },
        {"message": "test_message", "other": {"message": "my message value"}},
        {"message": "test_message", "other": {"message": "my message value"}},
        id="test process extracts dotted fields and ignores missing fields",
    ),
    pytest.param(
        {
            "filter": "condition",
            "selective_extractor": {
                "event_template": {
                    "integer": "${integer}",
                    "float": "${float}",
                    "boolean": "${boolean}",
                    "string": "${string}",
                    "mapping": "${mapping}",
                    "list": "${list}",
                },
                "outputs": [{"opensearch": "index"}],
            },
        },
        {
            "condition": True,
            "integer": 42,
            "float": 3.5,
            "boolean": True,
            "string": "foo",
            "mapping": {"key": "value"},
            "list": [1, 2, 3],
        },
        {
            "integer": 42,
            "float": 3.5,
            "boolean": True,
            "string": "foo",
            "mapping": {"key": "value"},
            "list": [1, 2, 3],
        },
        id="event template preserves substituted field value types",
    ),
    pytest.param(
        {
            "filter": "condition",
            "selective_extractor": {
                "event_template": {
                    "integer": "${integer}",
                    "float": "${float}",
                    "string": "${string}",
                    "boolean": "${boolean}",
                },
                "to_string": ["integer", "float", "string"],
                "outputs": [{"opensearch": "index"}],
            },
        },
        {"condition": True, "integer": 42, "float": 3.5, "string": "foo", "boolean": True},
        {"integer": "42", "float": "3.5", "string": "foo", "boolean": True},
        id="event template converts explicitly selected values to strings",
    ),
    pytest.param(
        {
            "filter": "condition",
            "selective_extractor": {
                "event_template": {"value": "${value}"},
                "outputs": [{"opensearch": "index"}],
            },
        },
        {"condition": True, "value": None},
        {"value": None},
        id="event template preserves None/null values",
    ),
    pytest.param(
        {
            "filter": "condition",
            "selective_extractor": {
                "event_template": {"value": "${field"},
                "outputs": [{"opensearch": "index"}],
            },
        },
        {"condition": True, "field": "foo"},
        {"value": "${field"},
        id="malformed placeholder syntax is treated as string",
    ),
    pytest.param(
        {
            "filter": "condition",
            "selective_extractor": {
                "event_template": {"first": "${value}", "second": "${value}"},
                "outputs": [{"opensearch": "index"}],
            },
        },
        {"condition": True, "value": "foo"},
        {"first": "foo", "second": "foo"},
        id="event template can substitute the same source field multiple times",
    ),
    pytest.param(
        {
            "filter": "condition",
            "selective_extractor": {
                "event_template": {"values": ["static_value", "${value}", "${other.value}"]},
                "outputs": [{"opensearch": "index"}],
            },
        },
        {"condition": True, "value": 42, "other": {"value": True}},
        {"values": ["static_value", 42, True]},
        id="event template preserves substituted list value types",
    ),
#     pytest.param(
#         {
#             "filter": "condition",
#             "selective_extractor": {
#                 "event_template": {"value": "${value}"},
#             },
#         },
#         {"condition": True, "value": "foo"},
#         {"value": "foo"},
#         id="event template uses processor outputs as fallback",
#     ) if this is the place to test this??
)

failure_test_cases = [
    pytest.param(
        {
            "filter": "condition",
            "selective_extractor": {
                "event_template": {"value": "${not.exists}"},
                "outputs": [{"opensearch": "index"}],
            },
        },
        {"condition": True},
        {
            "condition": True,
            "tags": ["_selective_extractor_missing_field_warning"],
        },
        ".*ProcessingWarning.*",
        id="missing field in template causes processing warning and no extra event",
    ),
    pytest.param(
        {
            "filter": "condition",
            "selective_extractor": {
                "event_template": {"mapping": "${mapping}"},
                "to_string": ["mapping"],
                "outputs": [{"opensearch": "index"}],
            },
        },
        {"condition": True, "mapping": {"key": "value"}},
        {
            "condition": True,
            "mapping": {"key": "value"},
            "tags": ["_selective_extractor_failure"],
        },
        ".*ProcessingWarning.*",
        id="to_string on mapping causes processing warning",
    ),
    pytest.param(
        {
            "filter": "condition",
            "selective_extractor": {
                "event_template": {"values": "${values}"},
                "to_string": ["values"],
                "outputs": [{"opensearch": "index"}],
            },
        },
        {"condition": True, "values": [1, 2, 3]},
        {
            "condition": True,
            "values": [1, 2, 3],
            "tags": ["_selective_extractor_failure"],
        },
        ".*ProcessingWarning.*",
        id="to_string on list causes processing warning",
    ),
    pytest.param(
        {
            "filter": "condition",
            "selective_extractor": {
                "event_template": {"value": "${value}"},
                "to_string": ["value"],
                "outputs": [{"opensearch": "index"}],
            },
        },
        {"condition": True, "value": None},
        {
            "condition": True,
            "value": None,
            "tags": ["_selective_extractor_failure"],
        },
        ".*ProcessingWarning.*",
        id="to_string on None causes processing warning",
    ),
]


class TestSelectiveExtractor(BaseProcessorTestCase):
    CONFIG = {
        "type": "selective_extractor",
        "rules": ["tests/testdata/unit/selective_extractor/rules"],
    }

    @pytest.mark.parametrize(["rule", "event", "expected", "context"], test_cases)
    def test_testcases(self, rule, event, expected, context, provision_context):
        provision_context(context)
        self._load_rule(rule)
        self.object.process(event)
        assert event == expected

    def test_selective_extractor_does_not_change_orig_doc(self):
        document = {"user": "test_user", "other": "field"}
        exp_document = {"user": "test_user", "other": "field"}

        self.object.process(document)

        assert document == exp_document

    def test_process_returns_list_of_tuples(self):
        document = {"message": "test_message", "other": "field"}
        tuple_list = self.object.process(document)
        assert isinstance(tuple_list, ProcessorResult)
        assert len(tuple_list.data) > 0

    def test_process_returns_tuple_list_with_extraction_fields_from_rule(self):
        field_name = f"{uuid.uuid4()}"
        rule = SelectiveExtractorRule.create_from_dict(
            {
                "filter": field_name,
                "selective_extractor": {
                    "source_fields": [field_name],
                    "outputs": [{"kafka": "topic"}],
                },
            }
        )
        self.object._rule_tree.add_rule(rule)
        document = {field_name: "the value"}
        tuple_list = self.object.process(document)
        for filtered_event, _ in tuple_list.data:
            if field_name in filtered_event:
                break
        else:
            assert False

    def test_process_returns_selective_extractor_target_topic(self):
        field_name = f"{uuid.uuid4()}"
        rule = {
            "filter": field_name,
            "selective_extractor": {
                "source_fields": [field_name],
                "outputs": [{"opensearch": "my topic"}],
            },
        }
        self._load_rule(rule)
        document = {field_name: "test_message", "other": "field"}
        result = self.object.process(document)
        output = result.data[0][1][0]
        assert "my topic" in output.values()

    def test_process_returns_selective_extractor_target_output(self):
        field_name = f"{uuid.uuid4()}"
        rule = {
            "filter": field_name,
            "selective_extractor": {
                "source_fields": [field_name],
                "outputs": [{"opensearch": "index"}],
            },
        }
        self._load_rule(rule)
        document = {field_name: "test_message", "other": "field"}
        result = self.object.process(document)
        output = result.data[0][1][0]
        assert "opensearch" in output.keys()

    def test_process_returns_extracted_fields(self):
        document = {"message": "test_message", "other": "field"}
        rule = {
            "filter": "message",
            "selective_extractor": {
                "source_fields": ["message"],
                "outputs": [{"opensearch": "index"}],
            },
        }
        self._load_rule(rule)
        result = self.object.process(document)
        for filtered_event, *_ in result.data:
            if filtered_event == {"message": "test_message"}:
                break
        else:
            assert False

    def test_process_returns_none_when_no_extraction_field_matches(self):
        document = {"nomessage": "test_message", "other": "field"}
        result = self.object.process(document)
        assert isinstance(result, ProcessorResult)
        assert result.data == []
        assert result.errors == []
        assert result.processor_name == "Test Instance Name"

    def test_gets_matching_rules_from_rules_tree(self):
        matching_rules = self.object._rule_tree.get_matching_rules({"message": "the message"})
        assert isinstance(matching_rules, list)
        assert len(matching_rules) > 0

    def test_apply_rules_is_called(self):
        with mock.patch(
            f"{self.object.__module__}.{self.object.__class__.__name__}._apply_rules"
        ) as mock_apply_rules:
            self.object.process({"message": "the message"})
            mock_apply_rules.assert_called()

    def test_process_extracts_dotted_fields(self):
        rule = {
            "filter": "message",
            "selective_extractor": {
                "source_fields": ["other.message", "message"],
                "outputs": [{"opensearch": "index"}],
            },
        }
        self._load_rule(rule)
        document = {"message": "test_message", "other": {"message": "my message value"}}
        result = self.object.process(document)

        for extracted_event, *_ in result.data:
            if extracted_event.get("other", {}).get("message") is not None:
                break
        else:
            assert False, f"other.message not in {result}"

    def test_process_clears_internal_filtered_events_list_before_every_event(self):
        document = {"message": "test_message", "other": {"message": "my message value"}}
        _ = self.object.process(document)
        assert len(self.object.result.data) == 1
        _ = self.object.process(document)
        assert len(self.object.result.data) == 1
