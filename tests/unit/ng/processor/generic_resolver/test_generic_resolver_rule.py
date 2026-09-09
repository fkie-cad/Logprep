# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
import json
from pathlib import Path

import pytest
from aiohttp import web

from logprep.factory_error import InvalidConfigurationError
from logprep.ng.processor.generic_resolver.rule import (
    GenericResolverRule,
)
from logprep.ng.util.getter import HttpGetter, RefreshableGetter
from logprep.util.defaults import ENV_NAME_LOGPREP_GETTER_CONFIG
from tests.conftest import FIELD_VALUE_TEST_CASES, mock_env


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
        ["other_rule_definition", "is_equal"],
        [
            pytest.param(
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
                id="should_be_equal_same",
            ),
            pytest.param(
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
                id="should_be_equal_default_same",
            ),
            pytest.param(
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
                id="should_not_be_equal_other_filter",
            ),
            pytest.param(
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
                id="should_not_be_equal_other_field_mapping",
            ),
            pytest.param(
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
                id="should_not_be_equal_other_resolve_list",
            ),
            pytest.param(
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
                id="should_not_be_equal_no_resolve_list",
            ),
            pytest.param(
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
                id="should_not_be_equal_other_resolve_from_file",
            ),
            pytest.param(
                {
                    "filter": "message",
                    "generic_resolver": {
                        "field_mapping": {"to_resolve": "resolved"},
                        "resolve_list": {"pattern": "result"},
                        "merge_with_target": False,
                    },
                },
                False,
                id="should_not_be_equal_no_resolve_from_file",
            ),
            pytest.param(
                {
                    "filter": "message",
                    "generic_resolver": {
                        "field_mapping": {"to_resolve": "resolved"},
                        "resolve_list": [{"pattern": "result"}, {"pattern2": "result2"}],
                        "merge_with_target": False,
                    },
                },
                False,
                id="should_not_be_equal_no_resolve_from_file_with_resolve_list_sequence",
            ),
            pytest.param(
                {
                    "filter": "message",
                    "generic_resolver": {
                        "field_mapping": {"to_resolve": "resolved"},
                        "resolve_list": [{"pattern": "result"}],
                        "resolve_from_file": {
                            "path": "tests/testdata/unit/generic_resolver/resolve_mapping.yml",
                            "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                        },
                        "merge_with_target": False,
                    },
                },
                True,
                id="should_be_equal_same_with_resolve_list_sequence",
            ),
        ],
    )
    def test_rules_equality(self, rule_definition, other_rule_definition, is_equal):
        rule1 = GenericResolverRule.create_from_dict(rule_definition)
        rule2 = GenericResolverRule.create_from_dict(other_rule_definition)
        assert (rule1 == rule2) == is_equal

    @pytest.mark.parametrize(
        ["rule", "error", "message"],
        [
            pytest.param(
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
                id="missing_mapping_group",
            ),
            pytest.param(
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
                id="no_additional_file_found",
            ),
            pytest.param(
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
                None,
                "",
                id="load_from_file_with_list_of_key_value",
            ),
        ],
    )
    async def test_create_from_dict_validates_config(self, rule, error, message):
        rule_instance = GenericResolverRule.create_from_dict(rule)

        if error:
            with pytest.raises(error, match=message):
                await rule_instance.setup("test")
        else:
            await rule_instance.setup("test")
            assert hasattr(rule_instance, "_config")
            for key, value in rule.get("generic_resolver").items():
                assert hasattr(rule_instance._config, key)
                assert value == getattr(rule_instance._config, key)

    async def test_rule_callback_updates_additions_and_preserves_original_add(
        self,
        tmp_path,
        aiohttp_server,
    ):
        from_http_1 = {"foo": "bar"}
        from_http_2 = {"foo": "bar", "some": "thing"}
        from_http_3 = {}
        responses = iter((from_http_1, from_http_2, from_http_3))

        async def handler(_: web.Request) -> web.Response:
            return web.json_response(next(responses))

        app = web.Application()
        app.router.add_get("/resolve", handler)
        server = await aiohttp_server(app)
        url = str(server.make_url("/resolve"))

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

        RefreshableGetter.reset()

        getter_file_content = {url: {"refresh_interval": 10}}
        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))

        try:
            with mock_env({ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}):
                rule = GenericResolverRule.create_from_dict(rule_definition)
                await rule.setup("test")

                scheduler = HttpGetter(protocol="http", target=url).scheduler
                assert scheduler is not None

                assert rule.additions == from_http_1

                await HttpGetter.refresh()
                assert rule.additions == from_http_1

                await scheduler.run_all()
                assert rule.additions == from_http_2

                await scheduler.run_all()
                assert rule.additions == from_http_3
        finally:
            RefreshableGetter.reset()

    @pytest.mark.parametrize(
        ["content_field_config", "expected"],
        [
            pytest.param({}, None, id="omitted_defaults_to_none"),
            pytest.param({"content_field": ""}, None, id="empty_string_converted_to_none"),
            pytest.param({"content_field": None}, None, id="null_stays_none"),
            pytest.param({"content_field": "content"}, "content", id="string_kept_verbatim"),
        ],
    )
    def test_content_field_default_and_converter(self, content_field_config, expected):
        rule = GenericResolverRule.create_from_dict(
            {
                "filter": "message",
                "generic_resolver": {
                    "field_mapping": {"to_resolve": "resolved"},
                    "resolve_list": {"pattern": "result"},
                    **content_field_config,
                },
            }
        )
        assert rule.config.content_field == expected

    def test_content_field_affects_rule_equality(self):
        def _make(content_field):
            generic_resolver = {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_list": {"pattern": "result"},
            }
            if content_field is not None:
                generic_resolver["content_field"] = content_field
            return GenericResolverRule.create_from_dict(
                {"filter": "message", "generic_resolver": generic_resolver}
            )

        assert _make("content") == _make("content")
        assert _make("content") != _make("other")
        assert _make("content") != _make(None)
        assert _make("") == _make(None)  # both are converted to None

    @pytest.mark.parametrize(
        "bad_value",
        [c for c in FIELD_VALUE_TEST_CASES if not isinstance(c.values[0], (str, type(None)))],
    )
    def test_content_field_rejects_non_string(self, bad_value):
        with pytest.raises(TypeError, match="'content_field' must be"):
            GenericResolverRule.create_from_dict(
                {
                    "filter": "message",
                    "generic_resolver": {
                        "field_mapping": {"to_resolve": "resolved"},
                        "resolve_list": {"pattern": "result"},
                        "content_field": bad_value,
                    },
                }
            )

    async def test_content_field_loads_nested_additions_from_http(self, aiohttp_server):
        expected = {"ab": "ab_server_type", "de": "de_server_type"}

        async def handler(_: web.Request) -> web.Response:
            return web.json_response({"content": expected})

        app = web.Application()
        app.router.add_get("/resolve", handler)
        server = await aiohttp_server(app)
        url = str(server.make_url("/resolve"))

        rule = GenericResolverRule.create_from_dict(
            {
                "filter": "to_resolve",
                "generic_resolver": {
                    "field_mapping": {"to_resolve": "resolved"},
                    "resolve_from_file": {
                        "path": url,
                        "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                    },
                    "content_field": "content",
                },
            }
        )

        await rule.setup("test")

        assert rule.additions == expected

    @pytest.mark.parametrize(
        ["body", "content_field", "match"],
        [
            pytest.param(
                ["ab", "de"],
                "content",
                "Expected mapping type when content_field is set",
                id="content_root_is_a_list",
            ),
            pytest.param(
                {"content": {"ab": "ab_server_type"}},
                "missing",
                "Error loading additions",
                id="content_field_key_absent",
            ),
        ],
    )
    async def test_content_field_load_failures_from_http(
        self,
        body,
        content_field,
        match,
        aiohttp_server,
    ):
        async def handler(_: web.Request) -> web.Response:
            return web.json_response(body)

        app = web.Application()
        app.router.add_get("/resolve", handler)
        server = await aiohttp_server(app)
        url = str(server.make_url("/resolve"))

        rule = GenericResolverRule.create_from_dict(
            {
                "filter": "to_resolve",
                "generic_resolver": {
                    "field_mapping": {"to_resolve": "resolved"},
                    "resolve_from_file": {
                        "path": url,
                        "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                    },
                    "content_field": content_field,
                },
            }
        )

        with pytest.raises(InvalidConfigurationError, match=match):
            await rule.setup("test")

    def test_additions_are_not_shared_between_configs(self):
        first = GenericResolverRule.Config(
            field_mapping={"source": "target"},
            resolve_list={},
        )
        second = GenericResolverRule.Config(
            field_mapping={"source": "target"},
            resolve_list={},
        )

        assert first.additions is not second.additions

    async def test_failed_refresh_preserves_last_valid_additions(
        self,
        tmp_path,
        aiohttp_server,
    ):
        responses = iter(
            (
                {"content": {"foo": "first"}},
                {"invalid": {"foo": "second"}},
                {"content": {"foo": "third"}},
            )
        )

        async def handler(_: web.Request) -> web.Response:
            return web.json_response(next(responses))

        app = web.Application()
        app.router.add_get("/resolve", handler)
        server = await aiohttp_server(app)
        url = str(server.make_url("/resolve"))

        getter_file_content = {
            url: {
                "refresh_interval": 10,
            }
        }
        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))

        rule_definition = {
            "filter": "something",
            "generic_resolver": {
                "field_mapping": {"to_resolve": "resolved"},
                "resolve_from_file": {
                    "path": url,
                    "pattern": r"something_\d*(?P<mapping>[a-z]+)\d*",
                },
                "content_field": "content",
            },
        }

        RefreshableGetter.reset()

        try:
            with mock_env({ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}):
                rule = GenericResolverRule.create_from_dict(rule_definition)
                await rule.setup("test")

                scheduler = HttpGetter(protocol="http", target=url).scheduler
                assert scheduler is not None

                assert rule.additions == {"foo": "first"}

                await scheduler.run_all()

                assert rule.additions == {"foo": "first"}

                await scheduler.run_all()

                assert rule.additions == {"foo": "third"}
        finally:
            RefreshableGetter.reset()
