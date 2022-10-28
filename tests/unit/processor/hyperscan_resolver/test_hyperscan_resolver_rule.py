# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
import pytest

from logprep.processor.hyperscan_resolver.rule import HyperscanResolverRule

pytest.importorskip("hyperscan")


@pytest.fixture(name="specific_rule_definition")
def fixture_specific_rule_definition():
    return {
        "filter": "some_filter",
        "hyperscan_resolver": {
            "field_mapping": {"to_resolve": "resolved"},
            "resolve_list": {"to_resolve": "resolved"},
            "store_db_persistent": True,
        },
        "description": "insert a description text",
    }


@pytest.fixture(name="specific_rule_with_resolve_file_definition")
def fixture_specific_rule_with_resolve_file_definition():
    return {
        "filter": "some_filter",
        "hyperscan_resolver": {
            "field_mapping": {"to_resolve": "resolved"},
            "resolve_from_file": {
                "path": "tests/testdata/unit/hyperscan_resolver/resolve_mapping_no_regex.yml",
                "pattern": r"\d*?(?P<mapping>[a-z0]+)\d*",
            },
        },
        "description": "insert a description text",
    }


@pytest.mark.parametrize(
    "testcase, other_rule_definition, is_equal",
    [
        (
            "Should be equal cause the same",
            {
                "filter": "some_filter",
                "hyperscan_resolver": {
                    "field_mapping": {"to_resolve": "resolved"},
                    "resolve_list": {"to_resolve": "resolved"},
                    "store_db_persistent": True,
                },
            },
            True,
        ),
        (
            "Should be not equal cause of other store_db_persistent",
            {
                "filter": "some_filter",
                "hyperscan_resolver": {
                    "field_mapping": {"to_resolve": "resolved"},
                    "resolve_list": {"to_resolve": "resolved"},
                    "store_db_persistent": False,
                },
            },
            False,
        ),
        (
            "Should be not equal cause of no store_db_persistent and default is different",
            {
                "filter": "some_filter",
                "hyperscan_resolver": {
                    "field_mapping": {"to_resolve": "resolved"},
                    "resolve_list": {"to_resolve": "resolved"},
                },
            },
            False,
        ),
        (
            "Should be not equal cause of other filter",
            {
                "filter": "other_filter",
                "hyperscan_resolver": {
                    "field_mapping": {"to_resolve": "resolved"},
                    "resolve_list": {"to_resolve": "resolved"},
                    "store_db_persistent": True,
                },
            },
            False,
        ),
        (
            "Should be not equal cause of other resolve",
            {
                "filter": "some_filter",
                "hyperscan_resolver": {
                    "field_mapping": {"to_resolve": "resolved"},
                    "resolve_list": {"other_to_resolve": "other_resolved"},
                    "store_db_persistent": True,
                },
            },
            False,
        ),
        (
            "Should be not equal cause of more resolves",
            {
                "filter": "some_filter",
                "hyperscan_resolver": {
                    "field_mapping": {"to_resolve": "resolved"},
                    "resolve_list": {
                        "to_resolve": "resolved",
                        "other_to_resolve": "other_resolved",
                    },
                    "store_db_persistent": True,
                },
            },
            False,
        ),
        (
            "Should be equal cause file value results in same resolve values",
            {
                "filter": "some_filter",
                "hyperscan_resolver": {
                    "field_mapping": {"to_resolve": "resolved"},
                    "resolve_from_file": "tests/testdata/unit/hyperscan_resolver/"
                    "resolve_mapping_same.yml",
                    "store_db_persistent": True,
                },
            },
            True,
        ),
        (
            "Should be not equal cause file value results in different resolve values",
            {
                "filter": "some_filter",
                "hyperscan_resolver": {
                    "field_mapping": {"to_resolve": "resolved"},
                    "resolve_from_file": "tests/testdata/unit/hyperscan_resolver/"
                    "resolve_mapping_different.yml",
                    "store_db_persistent": True,
                },
            },
            False,
        ),
    ],
)
def test_rules_equality(
    specific_rule_definition,
    testcase,
    other_rule_definition,
    is_equal,
):
    rule1 = HyperscanResolverRule._create_from_dict(
        specific_rule_definition,
    )

    rule2 = HyperscanResolverRule._create_from_dict(
        other_rule_definition,
    )

    assert (rule1 == rule2) == is_equal, testcase


def test_rules_with_differently_defined_but_equivalent_regex_pattern_definition_types_are_equal(
    specific_rule_with_resolve_file_definition,
):
    rule_no_regex = HyperscanResolverRule._create_from_dict(
        specific_rule_with_resolve_file_definition,
    )

    specific_rule_with_resolve_file_definition["hyperscan_resolver"][
        "resolve_from_file"
    ] = "tests/testdata/unit/hyperscan_resolver/resolve_mapping_regex.yml"
    rule_regex = HyperscanResolverRule._create_from_dict(
        specific_rule_with_resolve_file_definition,
    )

    assert rule_no_regex == rule_regex


def test_replace_pattern_with_parenthesis_after_closing_parenthesis_not_included_in_replacement():
    replaced_pattern = HyperscanResolverRule.Config._replace_pattern(
        "123abc456",
        r"\d*(?P<mapping>[a-z]+)c)\d*",
    )

    assert replaced_pattern == "\\d*123abc456c)\\d*"


def test_replace_pattern_with_escaped_parenthesis_is_included_in_replacement():
    replaced_pattern = HyperscanResolverRule.Config._replace_pattern(
        r"123ab\)c123", r"\d*(?P<mapping>[a-z]+\)c)\d*"
    )

    assert replaced_pattern == "\\d*123ab\\\\\\)c123\\d*"
