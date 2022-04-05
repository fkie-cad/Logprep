# pylint: disable=protected-access
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
from copy import deepcopy

from pytest import raises, fail

from logprep.filter.expression.filter_expression import StringFilterExpression
from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.labeler.labeling_schema import LabelingSchema
from logprep.processor.labeler.rule import LabelingRule
from tests.testdata.FilledTempFile import JsonTempFile
from tests.testdata.ruledata import (
    simple_rule,
    simple_regex_rule,
    complex_regex_rule,
    simple_rule_dict,
    null_rule,
)


class MockLabelingSchema(LabelingSchema):
    def __init__(self, result):
        self._result = result
        self.are_valid_labels_was_called = False

    def validate_labels(self, labels):
        self.are_valid_labels_was_called = True

        return self._result

    def get_parent_labels(self, category, label):
        return ["parent:%s" % label]


class TestRule:
    def setup_class(self):
        with JsonTempFile(simple_rule) as rule_path:
            self.rule = list(LabelingRule.create_rules_from_file(rule_path))[0]

        with JsonTempFile(simple_regex_rule) as rule_path:
            self.regex_rule = list(LabelingRule.create_rules_from_file(rule_path))[0]

        with JsonTempFile(complex_regex_rule) as rule_path:
            self.complex_regex_rule = list(LabelingRule.create_rules_from_file(rule_path))[0]

        with JsonTempFile(null_rule) as rule_path:
            self.null_rule = list(LabelingRule.create_rules_from_file(rule_path))[0]

    def test_create_from_file_fails_if_document_contains_unexpected_field(self):
        for unexpected_field in ["filters", "labels", "unexpected", "whatever"]:
            invalid_rule_dict = deepcopy(simple_rule_dict)
            invalid_rule_dict[unexpected_field] = "value"

            with raises(InvalidRuleDefinitionError):
                with JsonTempFile([invalid_rule_dict]) as rule_path:
                    LabelingRule.create_rules_from_file(rule_path)

    def test_create_from_file_fails_if_document_does_not_contain_filter_and_label(self):
        with raises(InvalidRuleDefinitionError):
            with JsonTempFile({}) as rule_path:
                LabelingRule.create_rules_from_file(rule_path)

        for missing_field in ["filter", "label"]:
            invalid_rule_dict = deepcopy(simple_rule_dict)
            del invalid_rule_dict[missing_field]

            with raises(InvalidRuleDefinitionError):
                with JsonTempFile([invalid_rule_dict]) as rule_path:
                    LabelingRule.create_rules_from_file(rule_path)

    def test_create_from_file_creates_expected_rule(self):
        assert self.rule._filter == StringFilterExpression(["applyrule"], "yes")
        assert self.rule._label == simple_rule_dict["label"]

    def test_create_from_dict_fails_if_document_contains_unexpected_field(self):
        for unexpected_field in ["filters", "labels", "unexpected", "whatever"]:
            invalid_rule_dict = deepcopy(simple_rule_dict)
            invalid_rule_dict[unexpected_field] = "value"

            with raises(InvalidRuleDefinitionError):
                LabelingRule._create_from_dict(invalid_rule_dict)

    def test_create_from_dict_fails_if_document_does_not_contain_filter_and_label(self):
        with raises(InvalidRuleDefinitionError):
            LabelingRule._create_from_dict({})

        for missing_field in ["filter", "label"]:
            invalid_rule_dict = deepcopy(simple_rule_dict)
            del invalid_rule_dict[missing_field]

            with raises(InvalidRuleDefinitionError):
                LabelingRule._create_from_dict(invalid_rule_dict)

    def test_create_from_dict_creates_expected_rule(self):
        rule = LabelingRule._create_from_dict(simple_rule_dict)

        assert rule._filter == StringFilterExpression(["applyrule"], "yes")
        assert rule._label == simple_rule_dict["label"]

    def test_conforms_to_schema_is_false_when_labels_do_not_conform_to_schema(self):
        dummy_schema = MockLabelingSchema(False)

        assert not self.rule.conforms_to_schema(dummy_schema)

    def test_conforms_to_schema_is_true_when_labels_do_conform_to_schema(self):
        dummy_schema = MockLabelingSchema(True)

        assert self.rule.conforms_to_schema(dummy_schema)

    def test_rules_may_contain_description(self):
        rule_with_description = deepcopy(simple_rule[0])
        rule_with_description["description"] = "this is the description"

        try:
            with JsonTempFile([rule_with_description]) as rule_path:
                self.rule = LabelingRule.create_rules_from_file(rule_path)[0]
        except InvalidRuleDefinitionError:
            fail("Rules with description field should be accepted as valid rules.")

    def test_matches_returns_true_for_matching_document(self):
        document = {"applyrule": "yes"}

        assert self.rule.matches(document)

    def test_matches_returns_false_for_non_matching_document(self):
        non_matching_documents = [{}, {"applyrule": "wrong value"}, {"wrong key": "value"}]
        for document in non_matching_documents:
            assert not self.rule.matches(document)

    def test_rules_are_different_if_their_filters_differ(self):
        rule1 = LabelingRule._create_from_dict(simple_rule_dict)
        rule2_dict = deepcopy(simple_rule_dict)
        rule2_dict["filter"] = 'applyrule: "no"'
        rule2 = LabelingRule._create_from_dict(rule2_dict)

        assert rule1 != rule2

    def test_rules_are_different_if_their_assigned_labels_differ(self):
        rule1 = LabelingRule._create_from_dict(simple_rule_dict)
        rule2_dict = deepcopy(simple_rule_dict)
        rule2_dict["label"]["reporter"] = ["mac"]
        rule2 = LabelingRule._create_from_dict(rule2_dict)

        assert rule1 != rule2

    def test_rules_are_equal_if_their_filters_and_labes_are_the_same(self):
        rule1 = LabelingRule._create_from_dict(simple_rule_dict)
        rule2 = LabelingRule._create_from_dict(deepcopy(simple_rule_dict))

        assert rule1 == rule2

    def test_rules_are_equal_if_their_filters_and_labes_are_the_same_but_their_descriptions_differ(
        self,
    ):
        rule_dict1 = deepcopy(simple_rule_dict)
        rule_dict1["description"] = "This is the first description"
        rule1 = LabelingRule._create_from_dict(rule_dict1)

        rule_dict2 = deepcopy(simple_rule_dict)
        rule_dict2["description"] = "This is the second description"
        rule2 = LabelingRule._create_from_dict(rule_dict2)

        assert rule1 == rule2

    def test_regex_matches_returns_true_for_matching_document(self):
        assert self.regex_rule.matches({"applyrule": "yes"})
        assert self.regex_rule.matches({"applyrule": "yes!"})
        assert self.regex_rule.matches({"applyrule": "no? yes!"})

    def test_regex_matches_returns_false_for_non_matching_document(self):
        non_matching_documents = [
            {},
            {"applyrule": "no"},
            {"applyrule": "ye s"},
            {"applyrule": "YES"},
            {"wrong key": "yes"},
        ]

        for document in non_matching_documents:
            assert not self.regex_rule.matches(document)

    def test_complex_regex_matches_returns_true_for_matching_document(self):
        assert self.complex_regex_rule.matches({"applyrule": "UPlo8888"})
        assert self.complex_regex_rule.matches({"applyrule": "UPlo99999"})
        assert self.complex_regex_rule.matches({"applyrule": "UPlo$$$$"})
        assert self.complex_regex_rule.matches({"applyrule": "UP$$$$88"})

    def test_complex_regex_does_not_match_returns_true_for_matching_document(self):
        assert not self.complex_regex_rule.matches({"applyrule": ""})
        assert not self.complex_regex_rule.matches({"applyrule": "UPlo777"})
        assert not self.complex_regex_rule.matches({"applyrule": "UP888888"})
        assert not self.complex_regex_rule.matches({"applyrule": "lo888888"})
        assert not self.complex_regex_rule.matches({"applyrule": "UPloXXXX"})
        assert not self.complex_regex_rule.matches({"applyrule": "88888888"})
        assert not self.complex_regex_rule.matches({"applyrule": "UPlo$$7"})

    def test_null_returns_true_for_matching_document(self):
        document = {"applyrule": None}

        assert self.null_rule.matches(document)
