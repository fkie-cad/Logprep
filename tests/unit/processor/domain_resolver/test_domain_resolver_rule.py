# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
import pytest

from logprep.processor.domain_resolver.rule import DomainResolverRule

pytest.importorskip("logprep.processor.domain_resolver")


@pytest.fixture(name="specific_rule_definition")
def fixture_specific_rule_definition():
    return {
        "filter": "message",
        "domain_resolver": {
            "source_url_or_domain": "foo",
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
                    "source_url_or_domain": "foo",
                },
            },
            True,
        ),
        (
            "Should be equal cause of no output_field and default is equal",
            {
                "filter": "message",
                "domain_resolver": {
                    "source_url_or_domain": "foo",
                    "output_field": "resolved_ip",
                },
            },
            True,
        ),
        (
            "Should be not equal cause of other filter",
            {
                "filter": "other_message",
                "domain_resolver": {
                    "source_url_or_domain": "foo",
                    "output_field": "bar",
                },
            },
            False,
        ),
        (
            "Should be not equal cause of other source_url_or_domain",
            {
                "filter": "message",
                "domain_resolver": {
                    "source_url_or_domain": "other_foo",
                    "output_field": "bar",
                },
            },
            False,
        ),
        (
            "Should be not equal cause of other output_field",
            {
                "filter": "message",
                "domain_resolver": {
                    "source_url_or_domain": "foo",
                    "output_field": "other_bar",
                },
            },
            False,
        ),
    ],
)
def test_rules_equality(specific_rule_definition, testcase, other_rule_definition, is_equal):
    rule1 = DomainResolverRule._create_from_dict(specific_rule_definition)
    rule2 = DomainResolverRule._create_from_dict(other_rule_definition)

    assert (rule1 == rule2) == is_equal, testcase


def test_deprecation_warning():
    rule_dict = {
        "filter": "message",
        "domain_resolver": {
            "source_url_or_domain": "foo",
            "output_field": "other_bar",
        },
    }

    with pytest.deprecated_call() as warnings:
        DomainResolverRule._create_from_dict(rule_dict)
        assert len(warnings.list) == 2
        matches = [warning.message.args[0] for warning in warnings.list]
        assert "Use domain_resolver.target_field instead" in matches[1]
        assert "Use domain_resolver.source_fields instead" in matches[0]
