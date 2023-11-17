# pylint: disable=missing-docstring
# pylint: disable=protected-access
import uuid
from unittest import mock

from logprep.processor.selective_extractor.rule import SelectiveExtractorRule
from tests.unit.processor.base import BaseProcessorTestCase


class TestSelectiveExtractor(BaseProcessorTestCase):
    CONFIG = {
        "type": "selective_extractor",
        "specific_rules": ["tests/testdata/unit/selective_extractor/rules/specific"],
        "generic_rules": ["tests/testdata/unit/selective_extractor/rules/generic"],
    }

    def test_selective_extractor_does_not_change_orig_doc(self):
        document = {"user": "test_user", "other": "field"}
        exp_document = {"user": "test_user", "other": "field"}

        self.object.process(document)

        assert document == exp_document

    def test_process_returns_list_of_tuples(self):
        document = {"message": "test_message", "other": "field"}
        tuple_list = self.object.process(document)
        assert isinstance(tuple_list, list)
        assert len(tuple_list) > 0
        assert isinstance(tuple_list[0], tuple)

    def test_process_returns_tuple_list_with_extraction_fields_from_rule(self):
        field_name = f"{uuid.uuid4()}"
        rule = SelectiveExtractorRule._create_from_dict(
            {
                "filter": field_name,
                "selective_extractor": {
                    "source_fields": [field_name],
                    "outputs": [{"kafka": "topic"}],
                },
            }
        )
        self.object._specific_tree.add_rule(rule)
        document = {field_name: "the value"}
        tuple_list = self.object.process(document)
        for filtered_event, _ in tuple_list:
            if field_name in filtered_event[0]:
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
        self._load_specific_rule(rule)
        document = {field_name: "test_message", "other": "field"}
        result = self.object.process(document)
        output = result[0][1][0]
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
        self._load_specific_rule(rule)
        document = {field_name: "test_message", "other": "field"}
        result = self.object.process(document)
        output = result[0][1][0]
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
        self._load_specific_rule(rule)
        result = self.object.process(document)
        for filtered_event, *_ in result:
            if filtered_event[0] == {"message": "test_message"}:
                break
        else:
            assert False

    def test_process_returns_none_when_no_extraction_field_matches(self):
        document = {"nomessage": "test_message", "other": "field"}
        result = self.object.process(document)
        assert result is None

    def test_gets_matching_rules_from_rules_trees(self):
        rule_trees = [self.object._generic_tree, self.object._specific_tree]
        assert len(rule_trees) > 0
        for tree in rule_trees:
            matching_rules = tree.get_matching_rules({"message": "the message"})
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
        self._load_specific_rule(rule)
        document = {"message": "test_message", "other": {"message": "my message value"}}
        result = self.object.process(document)

        for extracted_event, *_ in result:
            if extracted_event[0].get("other", {}).get("message") is not None:
                break
        else:
            assert False, f"other.message not in {result}"

    def test_process_clears_internal_filtered_events_list_before_every_event(self):
        assert len(self.object._extra_data) == 0
        document = {"message": "test_message", "other": {"message": "my message value"}}
        _ = self.object.process(document)
        assert len(self.object._extra_data) == 1
        _ = self.object.process(document)
        assert len(self.object._extra_data) == 1

    def test_process_extracts_dotted_fields_complains_on_missing_fields(self):
        rule = {
            "filter": "message",
            "selective_extractor": {
                "source_fields": ["other.message", "not.exists", "message"],
                "outputs": [{"opensearch": "index"}],
                "ignore_missing_fields": False,
            },
        }
        self._load_specific_rule(rule)
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
        self._load_specific_rule(rule)
        document = {"message": "test_message", "other": {"message": "my message value"}}
        expected = {
            "message": "test_message",
            "other": {"message": "my message value"},
        }
        self.object.process(document)
        assert document == expected
