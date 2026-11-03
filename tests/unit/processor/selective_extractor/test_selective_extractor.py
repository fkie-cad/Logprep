# pylint: disable=missing-docstring
# pylint: disable=protected-access
import re
import uuid
from datetime import datetime, timezone
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
                        "message": "${source_event.message}",
                        "other_message": "${source_event.other.message}",
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
                    "@timestamp": "${source_event.@timestamp}",
                    "status": "NEW",
                    "list_name": "some_list_name",
                    "command_type": "WRITE_ENTRY",
                    "command_arguments": {
                        "content": {
                            "${source_event.set}": {
                                "${source_event.key}": {
                                    "value": "${source_event.value}",
                                }
                            }
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
            "command_arguments": {"content": {"my_subset": {"my_key": {"value": 42}}}},
        },
        id="event template creates a nested extra event and preserves value types with key substitution",
    ),
    pytest.param(
        {
            "filter": "list_update",
            "selective_extractor": {
                "event_template": {
                    "@timestamp": "${source_event.@timestamp}",
                    "status": "NEW",
                    "list_name": "some_list_name",
                    "command_type": "WRITE_ENTRY",
                    "command_arguments": {
                        "content": {
                            "${source_event.set}": {
                                "${source_event.key}": {
                                    "value": "${source_event.int_value|str}",
                                    "ttl": "${source_event.ttl}",
                                }
                            },
                            "${source_event.set2}": {
                                "${source_event.key2}": {
                                    "value": "${source_event.value|str}",
                                    "ttl": "${source_event.ttl}",
                                }
                            },
                            "ttl": "${source_event.default_ttl}",
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
            "set2": "my_subset_2",
            "key": "my_key",
            "key2": "my_key2",
            "ttl": 12,
            "value": "string_value",
            "int_value": 42,
            "default_ttl": 12345,
        },
        {
            "@timestamp": "2026-09-28T10:00:00Z",
            "status": "NEW",
            "list_name": "some_list_name",
            "command_type": "WRITE_ENTRY",
            "command_arguments": {
                "content": {
                    "my_subset": {"my_key": {"value": "42", "ttl": 12}},
                    "my_subset_2": {"my_key2": {"value": "string_value", "ttl": 12}},
                    "ttl": 12345,
                }
            },
        },
        id="event template creates a nested extra event and converts selected values to string with key substitution",
    ),
]

test_cases = normalize_test_cases(
    *example_test_cases,
    pytest.param(
        {
            "filter": "condition",
            "description": "Literal ${source_event.value}",
            "selective_extractor": {
                "id": "audit",
                "event_template": {
                    "${rule.id}": {
                        "description": "${rule.description}",
                        "filter": "${rule.filter}",
                        "value": "${source_event.value}",
                        "source_rule": "${source_event.rule.id}",
                    }
                },
                "outputs": [{"opensearch": "index"}],
            },
        },
        {"condition": True, "value": 7, "rule": {"id": "source-rule"}},
        {
            "audit": {
                "description": "Literal ${source_event.value}",
                "filter": "condition: *",
                "value": 7,
                "source_rule": "source-rule",
            }
        },
        id="event template combines rule metadata and source values without reinterpreting metadata",
    ),
    pytest.param(
        {
            "filter": "condition",
            "selective_extractor": {
                "id": 42,
                "event_template": {
                    "rule_id": "${rule.id}",
                    "description": "${rule.description}",
                },
                "outputs": [{"opensearch": "index"}],
            },
        },
        {"condition": True},
        {"rule_id": "42", "description": ""},
        id="event template exposes numeric rule id as string and default description",
    ),
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
                    "integer": "${source_event.integer}",
                    "float": "${source_event.float}",
                    "boolean": "${source_event.boolean}",
                    "string": "${source_event.string}",
                    "mapping": "${source_event.mapping}",
                    "list": "${source_event.list}",
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
                    "integer": "${source_event.integer|str}",
                    "float": "${source_event.float|str}",
                    "string": "${source_event.string|str}",
                    "boolean": "${source_event.boolean}",
                },
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
                "event_template": {
                    "original": "${source_event.value}",
                    "converted": "${source_event.value|str}",
                },
                "outputs": [{"opensearch": "index"}],
            },
        },
        {
            "condition": True,
            "value": 42,
        },
        {
            "original": 42,
            "converted": "42",
        },
        id="event template converts individual placeholders using str modifier",
    ),
    pytest.param(
        {
            "filter": "condition",
            "selective_extractor": {
                "event_template": {
                    "escaped_placeholder": r"\${source_event.value}",
                    "escaped_modifier": r"\${source_event.value|unknown}",
                    "escaped_dollar": r"\$",
                    "resolved": "${source_event.value}",
                },
                "outputs": [{"opensearch": "index"}],
            },
        },
        {"condition": True, "value": 42},
        {
            "escaped_placeholder": "${source_event.value}",
            "escaped_modifier": "${source_event.value|unknown}",
            "escaped_dollar": "$",
            "resolved": 42,
        },
        id="event template supports escaping",
    ),
    pytest.param(
        {
            "filter": "condition",
            "selective_extractor": {
                "event_template": {"value": "${source_event.value}"},
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
                "event_template": {"mapping": "${source_event.mapping|str}"},
                "outputs": [{"opensearch": "index"}],
            },
        },
        {"condition": True, "mapping": {"key": "value"}},
        {"mapping": "{'key': 'value'}"},
        id="event template converts mappings to strings",
    ),
    pytest.param(
        {
            "filter": "condition",
            "selective_extractor": {
                "event_template": {"values": "${source_event.values|str}"},
                "outputs": [{"opensearch": "index"}],
            },
        },
        {"condition": True, "values": [1, 2, 3]},
        {"values": "[1, 2, 3]"},
        id="event template converts lists to strings",
    ),
    pytest.param(
        {
            "filter": "condition",
            "selective_extractor": {
                "event_template": {"value": "${source_event.value|str}"},
                "outputs": [{"opensearch": "index"}],
            },
        },
        {"condition": True, "value": None},
        {"value": "None"},
        id="event template converts None to string",
    ),
    pytest.param(
        {
            "filter": "condition",
            "selective_extractor": {
                "event_template": {},
                "outputs": [{"opensearch": "index"}],
            },
        },
        {"condition": True},
        {},
        id="empty event template emits no extra event",
    ),
    pytest.param(
        {
            "filter": "condition",
            "selective_extractor": {
                "event_template": {
                    "first": "${source_event.value}",
                    "second": "${source_event.value}",
                },
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
                "event_template": {
                    "values": [
                        "static_value",
                        "${source_event.value}",
                        "${source_event.other.value}",
                    ]
                },
                "outputs": [{"opensearch": "index"}],
            },
        },
        {"condition": True, "value": 42, "other": {"value": True}},
        {"values": ["static_value", 42, True]},
        id="event template preserves substituted list value types",
    ),
)

failure_test_cases = [
    pytest.param(
        {
            "filter": "condition",
            "selective_extractor": {
                "event_template": {"value": "${source_event.not.exists}"},
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
        result = self.object.process(event)
        if "event_template" in rule["selective_extractor"]:
            expected_data = (
                [(expected, tuple(rule["selective_extractor"]["outputs"]))] if expected else []
            )
            assert result.data == expected_data
            assert result.errors == []
        else:
            assert event == expected

    @pytest.mark.parametrize("rule, event, expected, message", failure_test_cases)
    def test_template_failures(self, rule, event, expected, message):
        self._load_rule(rule)
        result = self.object.process(event)
        assert event == expected
        assert result.data == []
        assert result.errors == []
        assert any(re.search(message, str(warning)) for warning in result.warnings)

    @pytest.mark.parametrize(
        "template, expected_events, expected_calls",
        [
            pytest.param(
                {"rule_id": "${rule.id}", "value": "${source_event.value}"},
                [{"rule_id": "audit", "value": 1}, {"rule_id": "audit", "value": 2}],
                (0, 0),
                id="unused context values are not generated",
            ),
            pytest.param(
                {"now": "${context.now}", "same_now": "${context.now}"},
                [
                    {
                        "now": "2026-11-03T12:00:00+00:00",
                        "same_now": "2026-11-03T12:00:00+00:00",
                    },
                    {
                        "now": "2026-11-03T12:00:01+00:00",
                        "same_now": "2026-11-03T12:00:01+00:00",
                    },
                ],
                (2, 0),
                id="context timestamp is cached per event and refreshed for next event",
            ),
            pytest.param(
                {"id": "${context.id}", "same_id": "${context.id}"},
                [
                    {
                        "id": "00000000-0000-4000-8000-000000000001",
                        "same_id": "00000000-0000-4000-8000-000000000001",
                    },
                    {
                        "id": "00000000-0000-4000-8000-000000000002",
                        "same_id": "00000000-0000-4000-8000-000000000002",
                    },
                ],
                (0, 2),
                id="context id is cached per event and refreshed for next event",
            ),
            pytest.param(
                {
                    "${rule.id}": {
                        "generated_id": "${context.id}",
                        "created_at": "${context.now}",
                        "value": "${source_event.value}",
                        "source_id": "${source_event.context.id}",
                    }
                },
                [
                    {
                        "audit": {
                            "generated_id": "00000000-0000-4000-8000-000000000001",
                            "created_at": "2026-11-03T12:00:00+00:00",
                            "value": 1,
                            "source_id": "source-id",
                        }
                    },
                    {
                        "audit": {
                            "generated_id": "00000000-0000-4000-8000-000000000002",
                            "created_at": "2026-11-03T12:00:01+00:00",
                            "value": 2,
                            "source_id": "source-id",
                        }
                    },
                ],
                (2, 2),
                id="rule context and source event combine without shadowing context",
            ),
        ],
    )
    def test_template_runtime_context(self, template, expected_events, expected_calls):
        processor_module = "logprep.processor.selective_extractor.processor"
        with (
            mock.patch(f"{processor_module}.datetime") as clock,
            mock.patch(f"{processor_module}.uuid4") as generate_id,
        ):
            clock.now.side_effect = [
                datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc),
                datetime(2026, 11, 3, 12, 0, 1, tzinfo=timezone.utc),
            ]
            generate_id.side_effect = [
                uuid.UUID("00000000-0000-4000-8000-000000000001"),
                uuid.UUID("00000000-0000-4000-8000-000000000002"),
            ]
            self._load_rule(
                {
                    "filter": "condition",
                    "selective_extractor": {
                        "id": "audit",
                        "event_template": template,
                        "outputs": [{"opensearch": "index"}],
                    },
                }
            )
            for value, expected in enumerate(expected_events, start=1):
                event = {"condition": True, "value": value, "context": {"id": "source-id"}}
                result = self.object.process(event)
                assert result.errors == []
                assert result.data == [(expected, ({"opensearch": "index"},))]
                assert event == {
                    "condition": True,
                    "value": value,
                    "context": {"id": "source-id"},
                }

            now_calls, id_calls = expected_calls
            assert clock.now.call_args_list == [mock.call(timezone.utc)] * now_calls
            assert generate_id.call_args_list == [mock.call()] * id_calls

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
