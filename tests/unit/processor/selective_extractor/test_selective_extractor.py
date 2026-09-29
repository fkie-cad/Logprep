# pylint: disable=missing-docstring
# pylint: disable=protected-access
import json
import shutil
import uuid
from collections.abc import Generator
from pathlib import Path
from typing import Any, Callable, TypeAlias
from unittest import mock

import attrs
import pytest
import responses
from attrs import field

from logprep.abc.processor import Processor, ProcessorResult
from logprep.processor.selective_extractor.rule import SelectiveExtractorRule
from logprep.util.helper import JsonObject
from tests.unit.processor.base import BaseProcessorTestCase


@attrs.define
class MockedUrl:
    url: str
    body: str
    content_type: str | None = field(default="application/json")


@attrs.define
class MockedPath:
    dest_path: str
    source_path: str | None = field(default=None)
    body: str | None = field(default=None)  # Json


@pytest.fixture
def provision_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pytestconfig: pytest.Config
) -> Generator[Callable[[list[MockedUrl | MockedPath]], None]]:
    """Experimental override for this test file only.

    The context is expected to have the following structure:
    .. code-block:: json

    [
        MockedUrl(url="http://example.tld/any/path", body="{"any": "json serializable content"}", spec=),
        MockedUrl(url="https://...", body={}), # same as http://
        MockedUrl(url="http://example.tld/any/path", body={}, content_type="application/json", # default content_type }),
        MockedPath(refpath="file://any/path/to/dict/or/file"),
        ...
    ],



        "file://some/path/contents.txt": {
            "body": {
                "any": "json serializable content"
            }
        }
        "some/path/contents.txt": { } # same as file://
    }

    The helper covers the most relevant aspects of mocking and provisioning:
    - ``http://`` / ``https://`` are registered as mocked ``GET`` responses. The
      response is served as ``application/json`` unless the spec sets a
      ``content_type`` (e.g. ``text/plain``), in which case the body is still
      JSON-serialized but sent under that content type. Requests are automatically mocked
      using `responses`.
    - ``file://`` or a bare path is written into an isolated working directory the
      test is switched into, so a rule's relative file path resolves to it without
      any rewriting. The working directory is only changed when a file path is provided.
    """
    project_root = pytestconfig.rootpath
    with responses.RequestsMock(assert_all_requests_are_fired=False) as mocked_responses:

        def _provision(context: MockContext) -> None:
            for x in context:
                if isinstance(x, MockedUrl):
                    mocked_responses.add(
                        responses.GET, x.url, body=json.dumps(x.body), content_type=x.content_type
                    )
                elif isinstance(x, MockedPath):
                    dst_path = tmp_path / x.dest_path.removeprefix("file://")
                    dst_path.parent.mkdir(parents=True, exist_ok=True)
                    if x.source_path is not None:
                        src_path = Path(x.source_path)
                        if not src_path.is_absolute():
                            src_path = project_root / src_path
                        shutil.copy(src_path, dst_path)
                    else:
                        dst_path.write_text(json.dumps(x.body), encoding="utf-8")
            monkeypatch.chdir(tmp_path)

        yield _provision


MockContext: TypeAlias = list[MockedPath | MockedUrl]


@attrs.define
class Case:
    id: str
    rule: dict[str, Any]
    event: JsonObject
    expected: JsonObject
    expected_extras: list[JsonObject] | None = field(default=None)
    context: MockContext | None = field(default=None)

    def __len__(self):
        return 1

    def _get_params(self):
        return [self.rule, self.event, self.expected, self.expected_extras, self.context]

    # params = property(_get_params)


test_cases = [
    Case(
        rule={
            "filter": "message",
            "selective_extractor": {
                "source_fields": ["message"],
                "outputs": [{"opensearch": "index"}],
            },
        },
        event={"message": "test_message", "other": "field"},
        expected={"message": "test_message", "other": "field"},
        expected_extras=[{"message": "test_message"}],
        context=[
            MockedUrl(url="http://example.com", body='{"whatever":"json"}'),
            # MockedPath(refpath="blabla"),
        ],
        id="test_process_returns_extracted_fields",
    ),
]

parametrized_test_cases = [pytest.param(c, id=c.id) for c in test_cases]


class TestSelectiveExtractor(BaseProcessorTestCase):
    CONFIG = {
        "type": "selective_extractor",
        "rules": ["tests/testdata/unit/selective_extractor/rules"],
    }

    @pytest.mark.parametrize(["case"], parametrized_test_cases)
    def test_cases(self, case: Case, provision_context):
        provision_context(case.context)
        self._load_rule(case.rule)
        assert isinstance(self.object, Processor)
        result = self.object.process(case.event)
        assert case.expected == result.event
        assert case.expected_extras == result.data

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

    def test_process_extracts_dotted_fields_complains_on_missing_fields(self):
        rule = {
            "filter": "message",
            "selective_extractor": {
                "source_fields": ["other.message", "not.exists", "message"],
                "outputs": [{"opensearch": "index"}],
                "ignore_missing_fields": False,
            },
        }
        self._load_rule(rule)
        document = {"message": "test_message", "other": {"message": "my message value"}}
        expected = {
            "message": "test_message",
            "other": {"message": "my message value"},
            "tags": ["_selective_extractor_missing_field_warning"],
        }
        self.object.process(document)
        assert document == expected

    def test_process_extracts_dotted_fields_and_ignores_missing_fields(self):
        rule = {
            "filter": "message",
            "selective_extractor": {
                "source_fields": ["other.message", "message", "not.exists"],
                "outputs": [{"opensearch": "index"}],
                "ignore_missing_fields": True,
            },
        }
        self._load_rule(rule)
        document = {"message": "test_message", "other": {"message": "my message value"}}
        expected = {
            "message": "test_message",
            "other": {"message": "my message value"},
        }
        self.object.process(document)
        assert document == expected
