# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
import json
from pathlib import Path
from unittest.mock import patch

import pytest
import responses

from logprep.factory_error import InvalidConfigurationError
from logprep.processor.generic_resolver.rule import GenericResolverRule
from logprep.util.defaults import ENV_NAME_LOGPREP_GETTER_CONFIG
from logprep.util.getter import HttpGetter


@pytest.fixture(name="rule_definition")
def fixture_rule_definition():
    return {
        "filter": "message",
        "generic_resolver": {
            "field_mapping": {"to_resolve": "resolved"},
            "resolve_list": {"pattern": "result"},
            "resolve_from_file": {
                "path": "tests/testdata/unit/generic_resolver/resolve_mapping.yml",
                "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
            },
            "merge_with_target": False,
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
                        "merge_with_target": False,
                    },
                },
                True,
            ),
            (
                "Should be equal cause without merge_with_target, since default is the same",
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
                        "merge_with_target": False,
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
                        "merge_with_target": False,
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
                        "merge_with_target": False,
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
                        "merge_with_target": False,
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
                        "merge_with_target": False,
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
                        "merge_with_target": False,
                    },
                },
                False,
            ),
        ],
    )
    def test_rules_equality(self, rule_definition, testcase, other_rule_definition, is_equal):
        rule1 = GenericResolverRule.create_from_dict(rule_definition)
        rule2 = GenericResolverRule.create_from_dict(other_rule_definition)
        assert (rule1 == rule2) == is_equal, testcase

    @pytest.mark.parametrize(
        ["rule", "error", "message"],
        [
            (
                {
                    "filter": "to_resolve",
                    "generic_resolver": {
                        "field_mapping": {"to_resolve": "resolved"},
                        "resolve_from_file": {
                            "path": "tests/testdata/unit/generic_resolver/resolve_mapping.yml",
                            "pattern": r"\d*(?P<foobar>[a-z]+)\d*",
                        },
                        "resolve_list": {"FOO": "BAR"},
                    },
                },
                InvalidConfigurationError,
                "Mapping group is missing in mapping",
            ),
            (
                {
                    "filter": "to.resolve",
                    "generic_resolver": {
                        "field_mapping": {"to.resolve": "resolved"},
                        "resolve_from_file": {
                            "path": "foo",
                            "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                        },
                    },
                },
                InvalidConfigurationError,
                "Additions file 'foo' not found",
            ),
            (
                {
                    "filter": "to.resolve",
                    "generic_resolver": {
                        "field_mapping": {"to.resolve": "resolved"},
                        "resolve_from_file": {
                            "path": "tests/testdata/unit/generic_resolver/resolve_mapping_list.yml",
                            "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                        },
                    },
                },
                InvalidConfigurationError,
                r"Error loading additions from '.+resolve_mapping_list\.yml': "
                r"Value is not a dictionary",
            ),
        ],
    )
    def test_create_from_dict_validates_config(self, rule, error, message):
        if error:
            with pytest.raises(error, match=message):
                GenericResolverRule.create_from_dict(rule)
        else:
            rule_instance = GenericResolverRule.create_from_dict(rule)
            assert hasattr(rule_instance, "_config")
            for key, value in rule.get("generic_resolver").items():
                assert hasattr(rule_instance._config, key)
                assert value == getattr(rule_instance._config, key)

    @responses.activate
    def test_rule_callback_updates_additions_and_preserves_original_add(self, tmp_path):
        target = "localhost:123"
        url = f"http://{target}"

        rule_definition = {
            "filter": "something",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": url,
                    "pattern": r"something_\d*(?P<mapping>[a-z]+)\d*",
                },
            },
        }

        from_http_1 = {"foo": "bar"}
        from_http_2 = {"foo": "bar", "some": "thing"}
        from_http_3 = {}

        responses.add(responses.GET, url, json=from_http_1)
        responses.add(responses.GET, url, json=from_http_2)
        responses.add(responses.GET, url, json=from_http_3)

        HttpGetter._shared.clear()

        getter_file_content = {target: {"refresh_interval": 10}}
        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))
        mock_env = {ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}
        with patch.dict("os.environ", mock_env):
            scheduler = HttpGetter(protocol="http", target=target).scheduler
            rule = GenericResolverRule.create_from_dict(rule_definition)
            assert rule.additions == from_http_1
            HttpGetter.refresh()
            assert rule.additions == from_http_1
            scheduler.run_all()
            assert rule.additions == from_http_2
            assert rule.additions == from_http_2
            scheduler.run_all()
            assert rule.additions == from_http_3
