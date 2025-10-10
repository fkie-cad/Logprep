# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=no-self-use
from ipaddress import IPv4Network

import pytest

from logprep.processor.list_comparison.rule import ListComparisonRule


@pytest.fixture(name="rule_definition")
def fixture_rule_definition():
    return {
        "filter": "user",
        "list_comparison": {
            "source_fields": ["user"],
            "target_field": "user_results",
            "list_file_paths": ["../lists/user_list.txt"],
        },
        "description": "",
    }


class TestListComparisonRule:
    @pytest.mark.parametrize(
        "testcase, other_rule_definition, is_equal",
        [
            (
                "Should be equal cause the same",
                {
                    "filter": "user",
                    "list_comparison": {
                        "source_fields": ["user"],
                        "target_field": "user_results",
                        "list_file_paths": ["../lists/user_list.txt"],
                    },
                },
                True,
            ),
            (
                "Should be not equal cause of other filter",
                {
                    "filter": "other_user",
                    "list_comparison": {
                        "source_fields": ["user"],
                        "target_field": "user_results",
                        "list_file_paths": ["../lists/user_list.txt"],
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of other source_fields",
                {
                    "filter": "user",
                    "list_comparison": {
                        "source_fields": ["other_user"],
                        "target_field": "user_results",
                        "list_file_paths": ["../lists/user_list.txt"],
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of other target_field",
                {
                    "filter": "user",
                    "list_comparison": {
                        "source_fields": ["user"],
                        "target_field": "other_user_results",
                        "list_file_paths": ["../lists/user_list.txt"],
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of other list_file_paths",
                {
                    "filter": "user",
                    "list_comparison": {
                        "source_fields": ["user"],
                        "target_field": "other_user_results",
                        "list_file_paths": ["../lists/other_user_list.txt"],
                    },
                },
                False,
            ),
        ],
    )
    def test_rules_equality(self, rule_definition, testcase, other_rule_definition, is_equal):
        rule1 = ListComparisonRule.create_from_dict(rule_definition)
        rule2 = ListComparisonRule.create_from_dict(other_rule_definition)
        assert (rule1 == rule2) == is_equal, testcase

    def test_compare_set_not_empty_for_valid_rule_def_after_init_list_comparison(
        self, rule_definition
    ):
        rule = ListComparisonRule.create_from_dict(rule_definition)

        rule.init_list_comparison("tests/testdata/unit/list_comparison/rules")

        assert rule.compare_sets is not None
        assert isinstance(rule.compare_sets, dict)
        assert len(rule.compare_sets.keys()) > 0
        assert len(rule.network_compare_sets.keys()) == 0

    @pytest.mark.parametrize(
        "testcase, lists, ips_greater_zero, networks_greater_zero",
        [
            ("Compare combined network and IP", ["../lists/network_list.txt"], True, True),
            ("Compare network only", ["../lists/network_only_list.txt"], False, True),
            ("Compare IP only", ["../lists/ip_only_list.txt"], True, False),
            (
                "Compare separate network and IP file",
                ["../lists/network_only_list.txt", "../lists/ip_only_list.txt"],
                True,
                True,
            ),
            ("Compare empty file", ["../lists/empty_list.txt"], False, False),
        ],
    )
    def test_compare_set_with_network_and_string_loads_correctly(
        self, testcase, lists, ips_greater_zero, networks_greater_zero
    ):
        rule_definition = {
            "filter": "ip",
            "list_comparison": {
                "source_fields": ["ip"],
                "target_field": "network_results",
                "list_file_paths": lists,
            },
            "description": "",
        }
        rule = ListComparisonRule.create_from_dict(rule_definition)

        rule.init_list_comparison("tests/testdata/unit/list_comparison/rules")

        assert rule.compare_sets is not None
        assert rule.network_compare_sets is not None
        assert isinstance(rule.compare_sets, dict)
        assert isinstance(rule.network_compare_sets, dict)
        assert (len(rule.compare_sets.keys()) > 0) == ips_greater_zero
        assert (len(rule.network_compare_sets.keys()) > 0) == networks_greater_zero
        for string_values in rule.compare_sets.values():
            assert all(not isinstance(value, IPv4Network) for value in string_values)
        for networks in rule.network_compare_sets.values():
            assert all(isinstance(network, IPv4Network) for network in networks)
