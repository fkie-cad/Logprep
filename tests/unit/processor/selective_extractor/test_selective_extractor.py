# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long

import uuid
from unittest import mock

import pytest

from logprep.abc.processor import Processor, ProcessorResult
from logprep.processor.selective_extractor.rule import SelectiveExtractorRule
from tests.conftest import ProcessorTestCase
from tests.unit.processor.base import BaseProcessorTestCase

example_test_cases = [
    ProcessorTestCase(
        id="Test process returns extracted fields",
        rule={
            "filter": "message",
            "selective_extractor": {
                "source_fields": ["message", "message2"],
                "outputs": [{"opensearch": "index"}],
            },
        },
        event={"message": "test_message", "message2": "test_message2", "other": "field"},
        expected={"message": "test_message", "message2": "test_message2", "other": "field"},
        expected_extras=[
            (
                {"message": "test_message", "message2": "test_message2"},
                [
                    ("opensearch", "index"),
                ],
            ),
        ],
    ),
    # context=[
    #    MockedUrl(url="http://example.com", body='{"whatever":"json"}'),
    #    MockedFile(source_path="/tests/testdata/blabla"),
    # ],
]
test_cases = [
    *example_test_cases,
    ProcessorTestCase(
        id="test process extracts dotted fields and ignores missing fields",
        rule={
            "filter": "message",
            "selective_extractor": {
                "source_fields": ["other.message", "message", "not.exists"],
                "outputs": [{"opensearch": "index"}],
                "ignore_missing_fields": True,
            },
        },
        event={"message": "test_message", "other": {"message": "my message value"}},
        expected={"message": "test_message", "other": {"message": "my message value"}},
        expected_extras=[
            (
                {"message": "test_message", "other": {"message": "my message value"}},
                [
                    ("opensearch", "index"),
                ],
            ),
        ],
    ),
    ProcessorTestCase(
        id="test process extracts dotted fields and complains on missing fields",
        rule={
            "filter": "message",
            "selective_extractor": {
                "source_fields": ["other.message", "not.exists", "message"],
                "outputs": [{"opensearch": "index"}],
                "ignore_missing_fields": False,
            },
        },
        event={"message": "test_message", "other": {"message": "my message value"}},
        expected={
            "message": "test_message",
            "other": {"message": "my message value"},
            "tags": ["_selective_extractor_missing_field_warning"],
        },
    ),
]

parametrized_test_cases = [c.case_to_param() for c in test_cases]


class TestSelectiveExtractor(BaseProcessorTestCase):
    CONFIG = {
        "type": "selective_extractor",
        "rules": ["tests/testdata/unit/selective_extractor/rules"],
    }

    @pytest.mark.parametrize("case", parametrized_test_cases)
    def test_testcases(self, case: ProcessorTestCase, provision_context_new):
        if case.context is not None:
            provision_context_new(case.context)
        self._load_rule(case.rule)
        assert isinstance(self.object, Processor)
        result = self.object.process(case.event)
        assert result.event == case.expected
        expected_extras = getattr(case, "expected_extras", None)
        if not expected_extras:
            assert not result.data
            return
        assert len(result.data) == len(expected_extras)

        for (expected_extra_data, expected_outputs), (actual_data, actual_outputs) in zip(
            expected_extras, result.data
        ):
            assert actual_data == expected_extra_data
            if not expected_outputs:
                continue
            for (expected_output_name, expected_target), actual_output in zip(
                expected_outputs, actual_outputs
            ):
                if isinstance(actual_output, dict):
                    assert actual_output.get(expected_output_name) == expected_target
                else:
                    assert actual_output == expected_target

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

    # def test_process_returns_extracted_fields(self):
    #     document = {"message": "test_message", "other": "field"}
    #     rule = {
    #         "filter": "message",
    #         "selective_extractor": {
    #             "source_fields": ["message"],
    #             "outputs": [{"opensearch": "index"}],
    #         },
    #     }
    #     self._load_rule(rule)
    #     result = self.object.process(document)
    #     assert result.event is document
    #     for filtered_event, *_ in result.data:
    #         if filtered_event == {"message": "test_message"}:
    #             break
    #     else:
    #         assert False

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
