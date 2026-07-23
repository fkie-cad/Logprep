# pylint: disable=missing-docstring
# pylint: disable=protected-access
import typing
from unittest import mock

import pytest

from logprep.factory_error import InvalidConfigurationError
from logprep.processor.list_comparison.rule import ListComparisonRule, _StaticCompareSet


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

    def test_compare_sets_not_empty_for_valid_rule_def_after_init_list_comparison(
        self, rule_definition
    ):
        rule = ListComparisonRule.create_from_dict(rule_definition)

        rule = typing.cast(ListComparisonRule, rule)

        rule.init_list_comparison("test_owner", "tests/testdata/unit/list_comparison/rules")

        compare_sets = dict(rule.iter_compare_sets({}))

        assert compare_sets == {"user_list.txt": {"Franz"}}
        assert list(rule.compare_set_names) == ["user_list.txt"]

    def test_init_list_comparison_raises_if_no_base_path_is_configured(self):
        rule_definition = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": ["../lists/user_list.txt"],
            },
            "description": "",
        }
        rule = ListComparisonRule.create_from_dict(rule_definition)

        with pytest.raises(
            InvalidConfigurationError,
            match="list_search_base_path must be set either in the processor config or in the rule",
        ):
            rule.init_list_comparison("test_owner")

    @pytest.mark.parametrize(
        ("url", "will_fail"),
        [
            pytest.param("something", True),
            pytest.param("https://something", False),
        ],
    )
    def test_expects_refreshable_getter(self, url, will_fail):
        rule_definition = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": ["../lists/user_list.txt"],
            },
        }
        rule = typing.cast(ListComparisonRule, ListComparisonRule.create_from_dict(rule_definition))
        compare_set = _StaticCompareSet(name="user_list.txt", content=set())

        with mock.patch(
            "logprep.processor.list_comparison.rule.ListComparisonRule._update_compare_sets_via_http",
            return_value=mock.MagicMock(),
        ):
            if will_fail:
                with pytest.raises(TypeError, match=f"The target {url} must be a url"):
                    rule._load_and_refresh_uri(compare_set, url)
            else:
                rule._load_and_refresh_uri(compare_set, url)

    def test_rule_remains_failed_until_all_static_compare_sets_recover(self):
        rule_definition = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": ["../lists/user_list.txt"],
            },
        }
        rule = typing.cast(ListComparisonRule, ListComparisonRule.create_from_dict(rule_definition))

        compare_set_a = _StaticCompareSet(name="LIST_A", content=set())
        compare_set_b = _StaticCompareSet(name="LIST_B", content=set())
        rule._static_sets = [compare_set_a, compare_set_b]

        error_a = RuntimeError("LIST_A failed")
        error_b = RuntimeError("LIST_B failed")

        rule._mark_failed(compare_set_a, error_a)
        rule._mark_failed(compare_set_b, error_b)

        assert isinstance(rule.data_error, ExceptionGroup)
        assert rule.data_error.exceptions == (error_a, error_b)

        rule._clear_failed(compare_set_a)
        assert rule.data_error is error_b

        rule._clear_failed(compare_set_b)
        assert rule.data_error is None

    @pytest.mark.parametrize(
        "list_comparison_config, error_message",
        [
            pytest.param(
                {
                    "source_fields": ["user"],
                    "target_field": "user_results",
                    "list_file_paths": ["../lists/user_list.txt"],
                    "list_paths": {"KNOWN_USERS": "../lists/user_list.txt"},
                },
                r"must not both be specified",
                id="list_file_paths and list_paths are mutually exclusive",
            ),
            pytest.param(
                {
                    "source_fields": ["user"],
                    "target_field": "user_results",
                },
                r"needs to be specified",
                id="one of list_file_paths or list_paths is required",
            ),
            pytest.param(
                {
                    "source_fields": ["user"],
                    "target_field": "user_results",
                    "list_file_paths": ["some/nice/path/list.txt", "some/cool/path/list.txt"],
                },
                r"list names need to be unique",
                id="basenames for list_file_paths need to be unique",
            ),
            pytest.param(
                {
                    "source_fields": ["user"],
                    "target_field": "user_results",
                    "list_file_paths": ["blocklist?type=users"],
                    "list_search_base_path": "https://localhost/api/v2/",
                },
                r"LOGPREP_LIST needs to be configured in list_search_base_path",
                id="LOGPREP_LIST needs to be configured in list_search_base_path",
            ),
        ],
    )
    def test_rule_config_is_validated(self, list_comparison_config, error_message):
        rule_dict = {"filter": "user", "list_comparison": list_comparison_config}
        with pytest.raises(ValueError, match=error_message):
            rule = typing.cast(ListComparisonRule, ListComparisonRule.create_from_dict(rule_dict))
            rule.init_list_comparison("irrelevant_tag", "/base/path")
