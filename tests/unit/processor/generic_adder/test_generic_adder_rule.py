# pylint: disable=missing-docstring
# pylint: disable=protected-access
import json
from pathlib import Path
from unittest.mock import patch

import pytest
import responses

from logprep.processor.generic_adder.rule import GenericAdderRule
from logprep.util.defaults import ENV_NAME_LOGPREP_GETTER_CONFIG
from logprep.util.getter import HttpGetter


@pytest.fixture(name="rule_definition")
def fixture_rule_definition():
    return {
        "filter": "add_generic_test",
        "generic_adder": {
            "add": {
                "some_added_field": "some value",
                "another_added_field": "another_value",
                "dotted.added.field": "yet_another_value",
            }
        },
        "description": "",
    }


class TestGenericAdderRule:
    @pytest.mark.parametrize(
        "testcase, other_rule_definition, is_equal",
        [
            (
                "Should be equal cause the same",
                {
                    "filter": "add_generic_test",
                    "generic_adder": {
                        "add": {
                            "some_added_field": "some value",
                            "another_added_field": "another_value",
                            "dotted.added.field": "yet_another_value",
                        }
                    },
                },
                True,
            ),
            (
                "Should be not equal cause of other filter",
                {
                    "filter": "other_filter",
                    "generic_adder": {
                        "add": {
                            "some_added_field": "some value",
                            "another_added_field": "another_value",
                            "dotted.added.field": "yet_another_value",
                        }
                    },
                },
                False,
            ),
            (
                "Should be not equal cause of one key is missing",
                {
                    "filter": "add_generic_test",
                    "generic_adder": {
                        "add": {
                            "some_added_field": "some value",
                            "dotted.added.field": "yet_another_value",
                        }
                    },
                },
                False,
            ),
            (
                "Should be equal cause file value results in same add values",
                {
                    "filter": "add_generic_test",
                    "generic_adder": {
                        "add_from_file": "tests/testdata/unit/generic_adder/additions_file.yml"
                    },
                },
                True,
            ),
        ],
    )
    def test_rules_equality(
        self,
        rule_definition,
        testcase,
        other_rule_definition,
        is_equal,
    ):
        rule1 = GenericAdderRule.create_from_dict(rule_definition)
        rule2 = GenericAdderRule.create_from_dict(other_rule_definition)
        assert (rule1 == rule2) == is_equal, testcase

    def test_rule_accepts_bool_type(self):
        rule_definition = {
            "filter": "add_generic_test",
            "generic_adder": {"add": {"added_bool_field": True}},
        }
        rule = GenericAdderRule.create_from_dict(rule_definition)
        assert isinstance(rule.add.get("added_bool_field"), bool)

    @responses.activate
    def test_rule_callback_updates_additions_and_preserves_original_add(self, tmp_path):
        target = "localhost:123"
        url = f"http://{target}"

        rule_definition = {
            "filter": "add_generic_test",
            "generic_adder": {"add": {"added_bool_field": True}, "add_from_file": f"{url}"},
        }

        from_http_1 = {
            "getter_int": 123,
            "getter_float": 123.0,
            "getter_bool": True,
            "getter_string": "test-1",
        }

        from_http_2 = {
            "getter_int": 456,
            "getter_float": 456.0,
            "getter_bool": False,
            "getter_string": "test-2",
            "getter_something_new": "something",
        }

        from_http_3 = {}

        expected_1 = {"added_bool_field": True, **from_http_1}
        expected_2 = {"added_bool_field": True, **from_http_2}
        expected_3 = {"added_bool_field": True}

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
            rule = GenericAdderRule.create_from_dict(rule_definition)
            assert rule.add == expected_1
            HttpGetter.refresh()
            assert rule.add == expected_1
            scheduler.run_all()
            assert rule.add == expected_2
            assert rule.add == expected_2
            scheduler.run_all()
            assert rule.add == expected_3
