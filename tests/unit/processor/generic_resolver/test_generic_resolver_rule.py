# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
import pytest

from logprep.processor.generic_resolver.rule import GenericResolverRule


@pytest.fixture(name="specific_rule_definition")
def fixture_specific_rule_definition():
    return {
        "filter": "message",
        "generic_resolver": {
            "field_mapping": {"to_resolve": "resolved"},
            "resolve_list": {"pattern": "result"},
            "resolve_from_file": {
                "path": "tests/testdata/unit/generic_resolver/resolve_mapping.yml",
                "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
            },
            "append_to_list": False,
        },
        "description": "insert a description text",
    }


class TestGenericResolverRule:
    @pytest.mark.parametrize(
        "testcase, other_rule_definition, is_equal",
        [
            (
                "Should be equal cause the same",
                {
                    "filter": "message",
                    "generic_resolver": {
                        "field_mapping": {"to_resolve": "resolved"},
                        "resolve_list": {"pattern": "result"},
                        "resolve_from_file": {
                            "path": "tests/testdata/unit/generic_resolver/resolve_mapping.yml",
                            "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                        },
                        "append_to_list": False,
                    },
                },
                True,
            ),
            (
                "Should be equal cause without append_to_list, since default is the same",
                {
                    "filter": "message",
                    "generic_resolver": {
                        "field_mapping": {"to_resolve": "resolved"},
                        "resolve_list": {"pattern": "result"},
                        "resolve_from_file": {
                            "path": "tests/testdata/unit/generic_resolver/resolve_mapping.yml",
                            "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                        },
                    },
                },
                True,
            ),
            (
                "Should be not equal cause of other filter",
                {
                    "filter": "other_message",
                    "generic_resolver": {
                        "field_mapping": {"to_resolve": "resolved"},
                        "resolve_list": {"pattern": "result"},
                        "resolve_from_file": {
                            "path": "tests/testdata/unit/generic_resolver/resolve_mapping.yml",
                            "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                        },
                        "append_to_list": False,
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of other field_mapping",
                {
                    "filter": "message",
                    "generic_resolver": {
                        "field_mapping": {"to_resolve": "other_resolved"},
                        "resolve_list": {"pattern": "result"},
                        "resolve_from_file": {
                            "path": "tests/testdata/unit/generic_resolver/resolve_mapping.yml",
                            "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                        },
                        "append_to_list": False,
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of other resolve_list",
                {
                    "filter": "message",
                    "generic_resolver": {
                        "field_mapping": {"to_resolve": "resolved"},
                        "resolve_list": {"pattern": "other_result"},
                        "resolve_from_file": {
                            "path": "tests/testdata/unit/generic_resolver/resolve_mapping.yml",
                            "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                        },
                        "append_to_list": False,
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of no resolve_list",
                {
                    "filter": "message",
                    "generic_resolver": {
                        "field_mapping": {"to_resolve": "resolved"},
                        "resolve_from_file": {
                            "path": "tests/testdata/unit/generic_resolver/resolve_mapping.yml",
                            "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                        },
                        "append_to_list": False,
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of other resolve_from_file",
                {
                    "filter": "message",
                    "generic_resolver": {
                        "field_mapping": {"to_resolve": "resolved"},
                        "resolve_list": {"pattern": "result"},
                        "resolve_from_file": {
                            "path": "tests/testdata/unit/generic_resolver/resolve_mapping.yml",
                            "pattern": r"other_\d*(?P<mapping>[a-z]+)\d*",
                        },
                        "append_to_list": False,
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of no resolve_from_file",
                {
                    "filter": "message",
                    "generic_resolver": {
                        "field_mapping": {"to_resolve": "resolved"},
                        "resolve_list": {"pattern": "result"},
                        "append_to_list": False,
                    },
                },
                False,
            ),
        ],
    )
    def test_rules_equality(
        self, specific_rule_definition, testcase, other_rule_definition, is_equal
    ):
        rule1 = GenericResolverRule._create_from_dict(specific_rule_definition)
        rule2 = GenericResolverRule._create_from_dict(other_rule_definition)
        assert (rule1 == rule2) == is_equal, testcase
