# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
import pytest

from logprep.processor.domain_resolver.rule import DomainResolverRule

pytest.importorskip("logprep.processor.domain_resolver")


@pytest.fixture(name="rule_definition")
def fixture_rule_definition():
    return {
        "filter": "message",
        "domain_resolver": {
            "source_fields": ["foo"],
        },
        "description": "insert a description text",
    }


@pytest.mark.parametrize(
    "testcase, other_rule_definition, is_equal",
    [
        (
            "Should be equal cause the same",
            {
                "filter": "message",
                "domain_resolver": {
                    "source_fields": ["foo"],
                },
            },
            True,
        ),
        (
            "Should be equal cause of no output_field and default is equal",
            {
                "filter": "message",
                "domain_resolver": {
                    "source_fields": ["foo"],
                    "target_field": "resolved_ip",
                },
            },
            True,
        ),
        (
            "Should be not equal cause of other filter",
            {
                "filter": "other_message",
                "domain_resolver": {
                    "source_fields": ["foo"],
                    "target_field": "bar",
                },
            },
            False,
        ),
        (
            "Should be not equal cause of other source_fields",
            {
                "filter": "message",
                "domain_resolver": {
                    "source_fields": ["other_foo"],
                    "target_field": "bar",
                },
            },
            False,
        ),
        (
            "Should be not equal cause of other target_field",
            {
                "filter": "message",
                "domain_resolver": {
                    "source_fields": ["foo"],
                    "target_field": "other_bar",
                },
            },
            False,
        ),
    ],
)
def test_rules_equality(rule_definition, testcase, other_rule_definition, is_equal):
    rule1 = DomainResolverRule._create_from_dict(rule_definition)
    rule2 = DomainResolverRule._create_from_dict(other_rule_definition)

    assert (rule1 == rule2) == is_equal, testcase
