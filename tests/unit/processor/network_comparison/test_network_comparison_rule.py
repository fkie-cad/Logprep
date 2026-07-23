# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=no-self-use
from ipaddress import IPv4Network

import pytest

from logprep.processor.network_comparison.rule import NetworkComparisonRule


@pytest.fixture(name="rule_definition")
def fixture_rule_definition():
    return {
        "filter": "ip",
        "network_comparison": {
            "source_fields": ["ip"],
            "target_field": "ip_results",
            "list_file_paths": ["../lists/network_list.txt"],
        },
        "description": "",
    }


class TestNetworkComparisonRule:
    @pytest.mark.parametrize(
        "testcase, other_rule_definition, is_equal",
        [
            (
                "Should be equal cause the same",
                {
                    "filter": "ip",
                    "network_comparison": {
                        "source_fields": ["ip"],
                        "target_field": "ip_results",
                        "list_file_paths": ["../lists/network_list.txt"],
                    },
                },
                True,
            ),
            (
                "Should be not equal cause of other filter",
                {
                    "filter": "ip2",
                    "network_comparison": {
                        "source_fields": ["ip"],
                        "target_field": "ip_results",
                        "list_file_paths": ["../lists/network_list.txt"],
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of other source_fields",
                {
                    "filter": "ip",
                    "network_comparison": {
                        "source_fields": ["ip2"],
                        "target_field": "ip_results",
                        "list_file_paths": ["../lists/network_list.txt"],
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of other target_field",
                {
                    "filter": "ip",
                    "network_comparison": {
                        "source_fields": ["ip"],
                        "target_field": "ip2_results",
                        "list_file_paths": ["../lists/network_list.txt"],
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of other list_file_paths",
                {
                    "filter": "ip",
                    "network_comparison": {
                        "source_fields": ["ip"],
                        "target_field": "ip2_results",
                        "list_file_paths": ["../lists/other_network_list.txt"],
                    },
                },
                False,
            ),
        ],
    )
    def test_rules_equality(self, rule_definition, testcase, other_rule_definition, is_equal):
        rule1 = NetworkComparisonRule.create_from_dict(rule_definition)
        rule2 = NetworkComparisonRule.create_from_dict(other_rule_definition)
        assert (rule1 == rule2) == is_equal, testcase

    def test_compare_sets_not_empty_for_valid_rule_def_after_init_list_comparison(
        self, rule_definition
    ):
        rule = NetworkComparisonRule.create_from_dict(rule_definition)

        rule.init_list_comparison("test_owner", "tests/testdata/unit/network_comparison/rules")

        compare_sets = dict(rule.iter_compare_sets({}))

        assert compare_sets == {
            "network_list.txt": {IPv4Network("127.0.0.0/24"), IPv4Network("127.0.0.1/32")}
        }
        assert list(rule.compare_set_names) == ["network_list.txt"]

    @pytest.mark.parametrize(
        "testcase, lists, expected",
        [
            (
                "Compare combined network and IP",
                ["../lists/network_list.txt"],
                {"network_list.txt": {IPv4Network("127.0.0.0/24"), IPv4Network("127.0.0.1/32")}},
            ),
            (
                "Compare network only",
                ["../lists/network_only_list.txt"],
                {
                    "network_only_list.txt": {
                        IPv4Network("127.0.0.0/8"),
                        IPv4Network("127.0.0.0/16"),
                        IPv4Network("127.0.0.0/24"),
                    }
                },
            ),
            (
                "Compare IP only",
                ["../lists/ip_only_list.txt"],
                {
                    "ip_only_list.txt": {
                        IPv4Network("127.0.0.1/32"),
                        IPv4Network("127.0.0.2/32"),
                        IPv4Network("127.0.0.3/32"),
                    }
                },
            ),
            (
                "Compare separate network and IP file",
                ["../lists/network_only_list.txt", "../lists/ip_only_list.txt"],
                {
                    "network_only_list.txt": {
                        IPv4Network("127.0.0.0/8"),
                        IPv4Network("127.0.0.0/16"),
                        IPv4Network("127.0.0.0/24"),
                    },
                    "ip_only_list.txt": {
                        IPv4Network("127.0.0.1/32"),
                        IPv4Network("127.0.0.2/32"),
                        IPv4Network("127.0.0.3/32"),
                    },
                },
            ),
            ("Compare empty file", ["../lists/empty_list.txt"], {"empty_list.txt": set()}),
        ],
    )
    def test_compare_set_with_network_and_string_loads_correctly(self, testcase, lists, expected):
        rule_definition = {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "network_results",
                "list_file_paths": lists,
            },
            "description": "",
        }
        rule = NetworkComparisonRule.create_from_dict(rule_definition)

        rule.init_list_comparison("test_owner", "tests/testdata/unit/network_comparison/rules")

        compare_sets = dict(rule.iter_compare_sets({}))

        assert compare_sets == expected, testcase
        for networks in compare_sets.values():
            assert all(isinstance(network, IPv4Network) for network in networks)

    def test_rule_load_fails_if_network_invalid(self):
        rule_definition = {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "network_results",
                "list_file_paths": ["../lists/invalid_list.txt"],
            },
            "description": "",
        }
        rule = NetworkComparisonRule.create_from_dict(rule_definition)

        with pytest.raises(
            ValueError, match="'invalid_network' does not appear to be an IPv4 or IPv6 network"
        ):
            rule.init_list_comparison("test_owner", "tests/testdata/unit/network_comparison/rules")
