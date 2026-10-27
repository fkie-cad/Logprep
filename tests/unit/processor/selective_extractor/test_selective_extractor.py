# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long

import json
import shutil
import uuid
from collections.abc import Callable, Generator
from copy import deepcopy
from pathlib import Path
from typing import Any, TypeAlias
from unittest import mock

import attrs
import pytest
import responses
from _pytest.mark.structures import (
    ParameterSet,  # pyright: ignore[reportPrivateImportUsage]
)
from attrs import field

from logprep.abc.processor import Processor, ProcessorResult
from logprep.processor.selective_extractor.rule import SelectiveExtractorRule
from logprep.util.helper import JsonObject
from tests.unit.processor.base import BaseProcessorTestCase


@attrs.define(kw_only=True, slots=True)
class MockedUrl:
    url: str
    body: str
    content_type: str | None = field(default="application/json")


@attrs.define(kw_only=True, slots=True)
class MockedFile:
    path: str = field(default="")
    source_path: str | None = field(default=None)
    body: str | None = field(default=None)

    def __post_init__(self):
        has_source = self.source_path is not None
        has_body = self.body is not None
        if has_source == has_body:
            if self.source_path is None and self.body is None:
                raise TypeError("Value needed for at least one: source_path, body")
            else:
                raise ValueError("Setting both source and body is not allowed.")


MockContext: TypeAlias = list[MockedFile | MockedUrl]


@attrs.define(kw_only=True, slots=True, frozen=True)
class ProcessorTestCase:
    id: str
    rule: dict[str, Any]
    event: JsonObject
    expected: JsonObject
    expected_extras: list[tuple[JsonObject, list[tuple[str, str]]]] | None = field(default=None)
    context: MockContext | None = field(default=None)

    def case_to_param(self) -> ParameterSet:
        """Export a ProcessorTestCase as a Pytest-ParameterSet.
        Uses a deepcopy to avoid problems with in-place changes on event.
        """
        return pytest.param(deepcopy(self), id=self.id)


@attrs.define(kw_only=True, slots=True, frozen=True)
class ProcessorFailureTestCase(ProcessorTestCase):
    error_message: str


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
    #    MockedFile(refpath="blabla"),
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
        expected_extras=None,  # can be left out
    ),
]


@pytest.fixture
def provision_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pytestconfig: pytest.Config,
) -> Generator[Callable[[list[MockedUrl | MockedFile]], None]]:
    """Experimental override for this test file only.

    The helper covers the most relevant aspects of mocking and provisioning.
    MockContext is either MockedUrl or MockedFile.
    - MockedUrl-Objects are registered as mocked ``GET`` responses. The
      response is served as ``application/json`` unless the spec sets a
      ``content_type`` (e.g. ``text/plain``), in which case the body is still
      JSON-serialized but sent under that content type. Requests are automatically mocked
      using `responses`.
    - MockedFile-Objects can be defined in one of two ways.
        1) Via a json "body" directly from code
        2) Via a path (string) to a file which gets copied
      An isolated working directory is created, which the test is switched into, so a rule's relative file path resolves to it without
      any rewriting. The working directory is only changed when a tmp_path is provided.
    """
    project_root = pytestconfig.rootpath
    with responses.RequestsMock(assert_all_requests_are_fired=False) as mocked_responses:

        def _provision(context: MockContext) -> None:
            if not context:  # includes falsy values such as []
                return
            for mock_item in context:
                match mock_item:
                    case MockedUrl():
                        mocked_responses.add(
                            responses.GET,
                            mock_item.url,
                            body=json.dumps(mock_item.body),
                            content_type=mock_item.content_type,
                        )
                    case MockedFile():
                        destination_path = tmp_path / mock_item.path.removeprefix("file://")
                        destination_path.parent.mkdir(parents=True, exist_ok=True)
                        if mock_item.source_path is None:
                            destination_path.write_text(
                                json.dumps(mock_item.body), encoding="utf-8"
                            )
                        else:
                            source_path = Path(mock_item.source_path)
                            if not source_path.is_absolute():
                                source_path = project_root / source_path
                            shutil.copy(source_path, destination_path)
            monkeypatch.chdir(tmp_path)

        yield _provision


parametrized_test_cases = [c.case_to_param() for c in test_cases]


class TestSelectiveExtractor(BaseProcessorTestCase):
    CONFIG = {
        "type": "selective_extractor",
        "rules": ["tests/testdata/unit/selective_extractor/rules"],
    }

    @pytest.mark.parametrize("case", parametrized_test_cases)
    def test_testcases(self, case: ProcessorTestCase, provision_context):
        provision_context(case.context)
        self._load_rule(case.rule)
        assert isinstance(self.object, Processor)
        result = self.object.process(case.event)
        assert case.expected == result.event
        # This last section is AI-Generated. I don't like it but I want to progress.
        if case.expected_extras is None:
            return
        assert result.data == case.expected_extras
        for (expected_extra_data, expected_outputs), (actual_data, actual_outputs) in zip(
            case.expected_extras, result.data
        ):
            assert actual_data == expected_extra_data
            if expected_outputs is not None:
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
