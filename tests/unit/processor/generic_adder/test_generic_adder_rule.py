# pylint: disable=missing-docstring
# pylint: disable=protected-access
import json
import typing
from pathlib import Path

import pytest
import responses

from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.generic_adder.rule import GenericAdderRule, UriConfig
from logprep.util.defaults import ENV_NAME_LOGPREP_GETTER_CONFIG
from logprep.util.getter import GetterFactory, HttpGetter, RefreshableGetter
from tests.conftest import mock_env


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
    def test_converts_add_from_uri_configuration(self):
        rule = GenericAdderRule.create_from_dict(
            {
                "filter": "*",
                "generic_adder": {
                    "add_from_uri": {
                        "uri": "https://values.example/${tenant.id}",
                        "target_field": "enrichment",
                    }
                },
            }
        )

        config = typing.cast(GenericAdderRule.Config, rule._config)

        assert len(config.add_from_uri) == 1
        assert isinstance(config.add_from_uri[0], UriConfig)
        assert config.add_from_uri[0].target_field == "enrichment"

    def test_converts_mixed_add_from_uri_configuration(self):
        rule = GenericAdderRule.create_from_dict(
            {
                "filter": "*",
                "generic_adder": {
                    "add_from_uri": [
                        "tests/testdata/unit/generic_adder/additions_file.yml",
                        {
                            "uri": "https://values.example/${tenant.id}",
                            "target_field": "enrichment",
                        },
                    ]
                },
            }
        )

        config = typing.cast(GenericAdderRule.Config, rule._config)

        assert config.add_from_uri[0] == UriConfig(
            uri="tests/testdata/unit/generic_adder/additions_file.yml"
        )
        assert config.add_from_uri[1] == UriConfig(
            uri="https://values.example/${tenant.id}",
            target_field="enrichment",
        )

    def test_accepts_add_from_uri_without_target_field(self):
        rule = GenericAdderRule.create_from_dict(
            {
                "filter": "*",
                "generic_adder": {"add_from_uri": {"uri": "https://values.example/${tenant}"}},
            }
        )

        config = typing.cast(GenericAdderRule.Config, rule._config)

        assert config.add_from_uri == [UriConfig(uri="https://values.example/${tenant}")]

    def test_rejects_deprecated_and_new_uri_configuration_together(self):
        with pytest.raises(
            ValueError,
            match="add_from_file and new add_from_uri cannot both be configured",
        ):
            GenericAdderRule.create_from_dict(
                {
                    "filter": "*",
                    "generic_adder": {
                        "add_from_file": "legacy.yml",
                        "add_from_uri": "new.yml",
                    },
                }
            )

    def test_rejects_only_first_existing_file_for_new_uri_configuration(self):
        with pytest.raises(
            ValueError,
            match="only_first_existing_file is only supported with deprecated add_from_file",
        ):
            GenericAdderRule.create_from_dict(
                {
                    "filter": "*",
                    "generic_adder": {
                        "add_from_uri": ["first.yml", "second.yml"],
                        "only_first_existing_file": True,
                    },
                }
            )

    def test_rejects_rule_without_addition_source(self):
        with pytest.raises(
            ValueError,
            match="one of add or add_from_uri",
        ):
            GenericAdderRule.create_from_dict(
                {
                    "filter": "*",
                    "generic_adder": {},
                }
            )

    @responses.activate
    def test_resolves_dotted_event_field_and_adds_complete_response(self):
        resolved_url = "https://values.example/acme"
        response_content = {
            "user": {"name": "Alice"},
            "risk": {"score": 7},
        }
        responses.add(responses.GET, resolved_url, json=response_content)
        rule = GenericAdderRule.create_from_dict(
            {
                "filter": "*",
                "generic_adder": {
                    "add_from_uri": {
                        "uri": "https://values.example/${tenant.id}",
                        "target_field": "enrichment",
                    }
                },
            }
        )
        rule.init_generic_adder("generic-adder-test")

        additions = rule.add({"tenant": {"id": "acme"}})

        assert additions == {"enrichment": response_content}
        assert responses.calls[0].request.url == resolved_url

    @responses.activate
    def test_static_url_loads_during_setup_and_registers_only_refresh_callback(self):
        url = "https://values.example/static"
        response_content = {"risk": {"score": 7}}
        responses.add(responses.GET, url, json=response_content)
        rule = GenericAdderRule.create_from_dict(
            {
                "filter": "*",
                "generic_adder": {
                    "add_from_uri": {
                        "uri": url,
                        "target_field": "enrichment",
                    }
                },
            }
        )

        rule.init_generic_adder("generic-adder-test")

        assert rule.add({}) == {"enrichment": response_content}
        assert rule.add({}) == {"enrichment": response_content}
        assert len(responses.calls) == 1
        assert len(HttpGetter._target_to_data_caches[url].callbacks) == 1
        assert len(HttpGetter._target_to_data_caches[url].cleanup_callbacks) == 0

    @responses.activate
    def test_content_field_is_applied_to_static_http_uri(self):
        url = "https://values.example/static"
        response_content = {
            "payload": {"risk": {"score": 7}},
            "metadata": {"version": 1},
        }
        responses.add(responses.GET, url, json=response_content)
        rule = GenericAdderRule.create_from_dict(
            {
                "filter": "*",
                "generic_adder": {
                    "add_from_uri": {
                        "uri": url,
                        "target_field": "enrichment",
                    },
                    "content_field": "payload",
                },
            }
        )

        rule.init_generic_adder("generic-adder-test")

        assert rule.add({}) == {"enrichment": response_content["payload"]}

    @responses.activate
    def test_content_field_is_applied_to_dynamic_http_uri(self):
        resolved_url = "https://values.example/acme"
        response_content = {
            "payload": {"risk": {"score": 7}},
            "metadata": {"version": 1},
        }
        responses.add(responses.GET, resolved_url, json=response_content)
        rule = GenericAdderRule.create_from_dict(
            {
                "filter": "*",
                "generic_adder": {
                    "add_from_uri": {
                        "uri": "https://values.example/${tenant}",
                        "target_field": "enrichment",
                    },
                    "content_field": "payload",
                },
            }
        )
        rule.init_generic_adder("generic-adder-test")

        assert rule.add({"tenant": "acme"}) == {"enrichment": response_content["payload"]}

    @responses.activate
    def test_static_url_failed_initial_load_raises(self):
        url = "https://values.example/static"
        responses.add(responses.GET, url, status=500)
        rule = GenericAdderRule.create_from_dict(
            {
                "filter": "*",
                "generic_adder": {
                    "add_from_uri": {
                        "uri": url,
                        "target_field": "enrichment",
                    }
                },
            }
        )

        with pytest.raises(
            InvalidRuleDefinitionError,
            match=r"Could not load generic_adder URI 'https://values.example/static'",
        ):
            rule.init_generic_adder("generic-adder-test")

    def test_merges_inline_and_ordered_file_uri_sources(self, tmp_path):
        first_file = tmp_path / "first.json"
        second_file = tmp_path / "second.json"
        first_file.write_text(json.dumps({"first": True, "shared": "first"}))
        second_file.write_text(json.dumps({"second": True, "shared": "second"}))
        rule = GenericAdderRule.create_from_dict(
            {
                "filter": "*",
                "generic_adder": {
                    "add": {"inline": True, "shared": "inline"},
                    "add_from_uri": [str(first_file), str(second_file)],
                },
            }
        )

        rule.init_generic_adder("generic-adder-test")

        assert rule.add({}) == {
            "inline": True,
            "first": True,
            "second": True,
            "shared": "second",
        }

    @responses.activate
    def test_same_uri_can_add_content_to_multiple_target_fields(self):
        url = "https://values.example/shared"
        response_content = {"risk": {"score": 7}}
        responses.add(responses.GET, url, json=response_content)
        responses.add(responses.GET, url, json=response_content)
        rule = GenericAdderRule.create_from_dict(
            {
                "filter": "*",
                "generic_adder": {
                    "add_from_uri": [
                        {"uri": url, "target_field": "first"},
                        {"uri": url, "target_field": "second"},
                    ]
                },
            }
        )

        rule.init_generic_adder("generic-adder-test")

        assert rule.add({}) == {
            "first": response_content,
            "second": response_content,
        }
        assert len(HttpGetter._target_to_data_caches[url].callbacks) == 2

    @responses.activate
    def test_dynamic_uri_caches_each_resolved_uri_independently(self):
        first_url = "https://values.example/first"
        second_url = "https://values.example/second"
        responses.add(responses.GET, first_url, json={"value": 1})
        responses.add(responses.GET, second_url, json={"value": 2})
        rule = GenericAdderRule.create_from_dict(
            {
                "filter": "*",
                "generic_adder": {
                    "add_from_uri": {
                        "uri": "https://values.example/${tenant}",
                        "target_field": "enrichment",
                    }
                },
            }
        )
        rule.init_generic_adder("generic-adder-test")

        assert rule.add({"tenant": "first"}) == {"enrichment": {"value": 1}}
        assert rule.add({"tenant": "second"}) == {"enrichment": {"value": 2}}
        assert rule.add({"tenant": "first"}) == {"enrichment": {"value": 1}}
        assert len(responses.calls) == 2

    @responses.activate
    def test_dynamic_uri_refreshes_and_cleans_up_its_source_cache(self, tmp_path):
        url = "https://values.example/acme"
        responses.add(responses.GET, url, json={"value": 1})
        getter_config = tmp_path / "http_getter.json"
        getter_config.write_text(json.dumps({url: {"refresh_interval": 1, "timeout_interval": 1}}))
        rule = GenericAdderRule.create_from_dict(
            {
                "filter": "*",
                "generic_adder": {
                    "add_from_uri": {
                        "uri": "https://values.example/${tenant}",
                        "target_field": "enrichment",
                    }
                },
            }
        )

        with mock_env({ENV_NAME_LOGPREP_GETTER_CONFIG: str(getter_config)}):
            rule.init_generic_adder("generic-adder-test")
            assert rule.add({"tenant": "acme"}) == {"enrichment": {"value": 1}}
            source = rule._uri_sources[0]
            getter = GetterFactory.from_string(url)
            assert isinstance(getter, HttpGetter)
            assert getter.scheduler is not None

            responses.replace(responses.GET, url, json={"value": 2})
            getter.scheduler.run_all()

            assert rule.add({"tenant": "acme"}) == {"enrichment": {"value": 2}}
            RefreshableGetter.reset(cleanup=True)

        assert source.content_by_uri == {}

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
                "Should not be equal because URI configuration is part of rule identity",
                {
                    "filter": "add_generic_test",
                    "generic_adder": {
                        "add_from_file": "tests/testdata/unit/generic_adder/additions_file.yml"
                    },
                },
                False,
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
        rule1.init_generic_adder("generic-adder-test")
        rule2.init_generic_adder("generic-adder-test")
        assert (rule1 == rule2) == is_equal, testcase

    def test_rule_accepts_bool_type(self):
        rule_definition = {
            "filter": "add_generic_test",
            "generic_adder": {"add": {"added_bool_field": True}},
        }
        rule = GenericAdderRule.create_from_dict(rule_definition)
        assert isinstance(rule.add({}).get("added_bool_field"), bool)

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

        getter_file_content = {url: {"refresh_interval": 10}}
        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))
        with mock_env({ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}):
            scheduler = HttpGetter(protocol="http", target=url).scheduler
            rule = GenericAdderRule.create_from_dict(rule_definition)
            rule.init_generic_adder("generic-adder-test")
            assert rule.add({}) == expected_1
            HttpGetter.refresh()
            assert rule.add({}) == expected_1
            scheduler.run_all()
            assert rule.add({}) == expected_2
            assert rule.add({}) == expected_2
            scheduler.run_all()
            assert rule.add({}) == expected_3
