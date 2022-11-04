# pylint: disable=protected-access
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=wrong-import-position
from copy import deepcopy
import pytest

from logprep.filter.expression.filter_expression import StringFilterExpression
from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.labeler.labeling_schema import LabelingSchema
from logprep.processor.labeler.rule import LabelerRule
from tests.testdata.FilledTempFile import JsonTempFile
from tests.testdata.ruledata import simple_rule_dict


class MockLabelingSchema(LabelingSchema):
    def __init__(self, result):  # pylint: disable=super-init-not-called
        self._result = result
        self.are_valid_labels_was_called = False

    def validate_labels(self, labels):
        self.are_valid_labels_was_called = True

        return self._result

    def get_parent_labels(self, category, label):
        return [f"parent:{label}"]


class TestRule:
    def test_create_from_file_fails_if_document_does_not_contain_filter_and_label(self):
        with pytest.raises(InvalidRuleDefinitionError):
            with JsonTempFile({}) as rule_path:
                LabelerRule.create_rules_from_file(rule_path)

        for missing_field in ["filter", "label"]:
            invalid_rule_dict = deepcopy(simple_rule_dict)
            del invalid_rule_dict[missing_field]

            with pytest.raises(InvalidRuleDefinitionError):
                with JsonTempFile([invalid_rule_dict]) as rule_path:
                    LabelerRule.create_rules_from_file(rule_path)

    def test_create_from_dict_creates_expected_rule(self):
        rule_definition = {"filter": 'applyrule: "yes"', "label": {"reporter": ["windows"]}}
        rule = LabelerRule._create_from_dict(rule_definition)
        assert rule._filter == StringFilterExpression(["applyrule"], "yes")
        assert rule._config.label == simple_rule_dict["label"]

    def test_create_from_dict_fails_if_document_does_not_contain_filter_and_label(self):
        with pytest.raises(InvalidRuleDefinitionError):
            LabelerRule._create_from_dict({})

        for missing_field in ["filter", "label"]:
            invalid_rule_dict = deepcopy(simple_rule_dict)
            del invalid_rule_dict[missing_field]

            with pytest.raises(InvalidRuleDefinitionError):
                LabelerRule._create_from_dict(invalid_rule_dict)

    def test_conforms_to_schema_is_false_when_labels_do_not_conform_to_schema(self):
        rule_definition = {"filter": 'applyrule: "yes"', "label": {"reporter": ["windows"]}}
        rule = LabelerRule._create_from_dict(rule_definition)
        dummy_schema = MockLabelingSchema(False)

        assert not rule.conforms_to_schema(dummy_schema)

    def test_conforms_to_schema_is_true_when_labels_do_conform_to_schema(self):
        rule_definition = {"filter": 'applyrule: "yes"', "label": {"reporter": ["windows"]}}
        rule = LabelerRule._create_from_dict(rule_definition)
        dummy_schema = MockLabelingSchema(True)

        assert rule.conforms_to_schema(dummy_schema)

    def test_rules_may_contain_description(self):
        rule_definition = {
            "filter": 'applyrule: "yes"',
            "label": {"reporter": ["windows"]},
            "description": "this is the description",
        }
        _ = LabelerRule._create_from_dict(rule_definition)

    def test_matches_returns_true_for_matching_document(self):
        rule_definition = {"filter": 'applyrule: "yes"', "label": {"reporter": ["windows"]}}
        rule = LabelerRule._create_from_dict(rule_definition)
        document = {"applyrule": "yes"}

        assert rule.matches(document)

    def test_matches_returns_false_for_non_matching_document(self):
        rule_definition = {"filter": 'applyrule: "yes"', "label": {"reporter": ["windows"]}}
        rule = LabelerRule._create_from_dict(rule_definition)
        non_matching_documents = [{}, {"applyrule": "wrong value"}, {"wrong key": "value"}]
        for document in non_matching_documents:
            assert not rule.matches(document)

    def test_rules_are_different_if_their_filters_differ(self):
        rule1 = LabelerRule._create_from_dict(simple_rule_dict)
        rule2_dict = deepcopy(simple_rule_dict)
        rule2_dict["filter"] = 'applyrule: "no"'
        rule2 = LabelerRule._create_from_dict(rule2_dict)

        assert rule1 != rule2

    def test_rules_are_different_if_their_assigned_labels_differ(self):
        rule1_dict = {"filter": 'applyrule: "yes"', "label": {"reporter": ["windows"]}}
        rule1 = LabelerRule._create_from_dict(rule1_dict)
        rule2_dict = {"filter": 'applyrule: "yes"', "label": {"reporter": ["mac"]}}
        rule2 = LabelerRule._create_from_dict(rule2_dict)

        assert rule1 != rule2

    def test_rules_are_equal_if_their_filters_and_labes_are_the_same(self):
        rule_definition = {"filter": 'applyrule: "yes"', "label": {"reporter": ["windows"]}}
        rule1 = LabelerRule._create_from_dict(rule_definition)
        rule2 = LabelerRule._create_from_dict(rule_definition)

        assert rule1 == rule2

    def test_rules_are_equal_if_their_filters_and_labes_are_the_same_but_their_descriptions_differ(
        self,
    ):
        rule_dict1 = deepcopy(simple_rule_dict)
        rule_dict1["description"] = "This is the first description"
        rule1 = LabelerRule._create_from_dict(rule_dict1)

        rule_dict2 = deepcopy(simple_rule_dict)
        rule_dict2["description"] = "This is the second description"
        rule2 = LabelerRule._create_from_dict(rule_dict2)

        assert rule1 == rule2

    def test_regex_matches_returns_true_for_matching_document(self):
        rule_definition = {
            "filter": 'applyrule: ".*yes.*"',
            "regex_fields": ["applyrule"],
            "label": {"reporter": ["windows"]},
        }
        rule = LabelerRule._create_from_dict(rule_definition)
        assert rule.matches({"applyrule": "yes"})
        assert rule.matches({"applyrule": "yes!"})
        assert rule.matches({"applyrule": "no? yes!"})

    def test_regex_matches_returns_false_for_non_matching_document(self):
        rule_definition = {
            "filter": 'applyrule: ".*yes.*"',
            "regex_fields": ["applyrule"],
            "label": {"reporter": ["windows"]},
        }
        rule = LabelerRule._create_from_dict(rule_definition)
        non_matching_documents = [
            {},
            {"applyrule": "no"},
            {"applyrule": "ye s"},
            {"applyrule": "YES"},
            {"wrong key": "yes"},
        ]

        for document in non_matching_documents:
            assert not rule.matches(document)

    def test_complex_regex_matches_returns_true_for_matching_document(self):
        rule_definition = {
            "filter": r'applyrule: "(?:(?=.*[a-z])(?:(?=.*[A-Z])(?=.*[\d\W])|(?=.*\W)(?=.*\d))|(?=.*\W)(?=.*[A-Z])(?=.*\d)).{8,}"',  # pylint: disable=line-too-long
            "regex_fields": ["applyrule"],
            "label": {"reporter": ["windows"]},
        }
        rule = LabelerRule._create_from_dict(rule_definition)
        assert rule.matches({"applyrule": "UPlo8888"})
        assert rule.matches({"applyrule": "UPlo99999"})
        assert rule.matches({"applyrule": "UPlo$$$$"})
        assert rule.matches({"applyrule": "UP$$$$88"})

    def test_complex_regex_does_not_match_returns_true_for_matching_document(self):
        rule_definition = {
            "filter": r'applyrule: "(?:(?=.*[a-z])(?:(?=.*[A-Z])(?=.*[\d\W])|(?=.*\W)(?=.*\d))|(?=.*\W)(?=.*[A-Z])(?=.*\d)).{8,}"',  # pylint: disable=line-too-long
            "regex_fields": ["applyrule"],
            "label": {"reporter": ["windows"]},
        }
        rule = LabelerRule._create_from_dict(rule_definition)
        assert not rule.matches({"applyrule": ""})
        assert not rule.matches({"applyrule": "UPlo777"})
        assert not rule.matches({"applyrule": "UP888888"})
        assert not rule.matches({"applyrule": "lo888888"})
        assert not rule.matches({"applyrule": "UPloXXXX"})
        assert not rule.matches({"applyrule": "88888888"})
        assert not rule.matches({"applyrule": "UPlo$$7"})

    def test_null_returns_true_for_matching_document(self):
        rule_definition = {"filter": "applyrule: null", "label": {"reporter": ["windows"]}}
        rule = LabelerRule._create_from_dict(rule_definition)
        document = {"applyrule": None}

        assert rule.matches(document)

    def test_deprecation_warning(self):
        rule_dict = {
            "filter": "other_message",
            "label": {"reporter": ["windows"]},
            "description": "",
        }
        with pytest.deprecated_call() as warnings:
            LabelerRule._create_from_dict(rule_dict)
            assert len(warnings.list) == 1
            matches = [warning.message.args[0] for warning in warnings.list]
            assert "Use labeler.label instead" in matches[0]
