# pylint: disable=missing-docstring,too-many-lines,protected-access,duplicate-code
import json
from copy import deepcopy
from pathlib import Path
from unittest import mock

import pytest
from aiohttp import web

from logprep.ng.abc.event import InputMeta, LogEvent
from logprep.ng.processor.list_comparison.processor import ListComparison
from logprep.ng.processor.list_comparison.rule import ListComparisonRule
from logprep.ng.util.getter import (
    DataSharedPerTarget,
    HttpGetter,
    RefreshableGetter,
    RefreshableGetterError,
    refresh_getters,
)
from logprep.processor.base.exceptions import ProcessingWarning
from logprep.util.defaults import ENV_NAME_LOGPREP_GETTER_CONFIG
from tests.conftest import mock_env
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.list_comparison.test_list_comparison import (
    HTTP_DYNAMIC_BASE_PATH,
    LOCAL_BASE_PATH,
    NOT_SET,
)
from tests.unit.processor.list_comparison.test_list_comparison import (
    failure_test_cases as non_ng_failure_test_cases,
)
from tests.unit.processor.list_comparison.test_list_comparison import (
    test_cases as non_ng_test_cases,
)


def _warning_str(warning) -> str:
    return f"{type(warning).__name__}: {warning}"


test_cases = deepcopy(non_ng_test_cases)
failure_test_cases = deepcopy(non_ng_failure_test_cases)


async def _compare_sets(
    rule: ListComparisonRule,
    event: dict | None = None,
) -> dict[str, set[str]]:
    """Materialize a rule's compare sets via its public ``iter_compare_sets`` API.

    Local and static lists are available with an empty event; dynamic lists
    require the event fields that resolve their target URI.
    """
    return {name: content async for name, content in rule.iter_compare_sets(event or {})}


class TestListComparison(BaseProcessorTestCase[ListComparison]):
    CONFIG = {
        "type": "list_comparison",
        "rules": ["tests/testdata/unit/list_comparison/rules"],
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
        "list_search_base_path": "tests/testdata/unit/list_comparison/rules",
    }

    async def async_setup(self):
        await super().async_setup()
        await self.object.setup()

    async def _create_lister(self, rules: list[dict], **extra_config):
        RefreshableGetter.reset()
        patch = {"rules": rules, "list_search_base_path": None, **extra_config}
        processor = self._create_test_instance(patch)
        await processor.setup()
        return processor

    @pytest.mark.parametrize("rule, event, expected", test_cases)
    async def test_testcases(self, rule, event, expected, aiohttp_server):
        rule = deepcopy(rule)

        list_search_base_path = rule["list_comparison"].get("list_search_base_path")

        if list_search_base_path and list_search_base_path.startswith(("http://", "https://")):

            async def handler(_: web.Request) -> web.Response:
                return web.Response(
                    text="# a comment\nFranz\nAlpha\nBeta\n",
                    content_type="text/plain",
                )

            app = web.Application()
            app.router.add_get("/{path:.*}", handler)
            server = await aiohttp_server(app)

            base_url = str(server.make_url("/")).rstrip("/")
            rule["list_comparison"]["list_search_base_path"] = f"{base_url}/${{LOGPREP_LIST}}"

        processor = await self._create_lister([rule])
        log_event = LogEvent(event, original=b"", input_meta=InputMeta())

        await processor.process(log_event)

        assert log_event.data == expected

    async def test_multiple_rules_write_independent_target_fields(self):
        document = {"user": "Mark", "system": "Franz"}

        await self.object.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert document["user_results"] == {"not_in_list": ["user_list.txt"]}
        assert document["user_and_system_results"] == {
            "in_list": ["user_list.txt", "system_list.txt"]
        }

    async def test_multiple_rules_all_not_in_list(self):
        document = {"user": "Mark", "system": "Gamma"}

        await self.object.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert document["user_results"] == {"not_in_list": ["user_list.txt"]}
        assert document["user_and_system_results"] == {
            "not_in_list": ["user_list.txt", "system_list.txt"]
        }

    async def test_rule_level_base_path_takes_precedence_over_processor_base_path(self):
        document = {"user": "Franz"}
        processor = await self._create_lister(
            [
                {
                    "filter": "user",
                    "list_comparison": {
                        "source_fields": ["user"],
                        "target_field": "user_results",
                        "list_search_base_path": LOCAL_BASE_PATH,
                        "list_file_paths": ["../lists/user_list.txt"],
                    },
                }
            ],
            list_search_base_path="some/nonexistent/base/path",
        )
        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))
        assert document == {"user": "Franz", "user_results": {"in_list": ["user_list.txt"]}}

    async def test_loads_static_http_list_with_template_base_path(self, aiohttp_server):
        async def handler(request: web.Request) -> web.Response:
            assert request.match_info["list_name"] == "bad_users.list"
            assert request.query["ref"] == "bla"

            return web.Response(
                text="Franz\nHeinz\nHans\n",
                content_type="text/plain",
            )

        app = web.Application()
        app.router.add_get("/tests/testdata/{list_name}", handler)
        server = await aiohttp_server(app)

        base_url = str(server.make_url("/")).rstrip("/")

        processor = await self._create_lister(
            [
                {
                    "filter": "user",
                    "list_comparison": {
                        "source_fields": ["user"],
                        "target_field": "user_results",
                        "list_file_paths": ["bad_users.list"],
                        "list_search_base_path": (
                            f"{base_url}/tests/testdata/${{LOGPREP_LIST}}?ref=bla"
                        ),
                    },
                }
            ]
        )

        assert await _compare_sets(processor.rules[0]) == {
            "bad_users.list": {"Franz", "Heinz", "Hans"}
        }

    @pytest.mark.parametrize(
        ("json_content", "content_field"),
        [
            pytest.param(["Franz", "Heinz", "Hans"], ""),
            pytest.param(["Franz", "Heinz", "Hans"], None),
            pytest.param(
                ["Franz", "Heinz", "Hans"],
                NOT_SET,
                id="no_content_field_entry_in_config",
            ),
            pytest.param({"content": ["Franz", "Heinz", "Hans"]}, "content"),
            pytest.param({"_": ["Franz", "Heinz", "Hans"]}, "_"),
        ],
    )
    async def test_loads_json_list_from_http(
        self,
        json_content,
        content_field,
        aiohttp_server,
    ):
        async def handler(request: web.Request) -> web.Response:
            assert request.match_info["list_name"] == "bad_users.list"
            return web.json_response(json_content)

        app = web.Application()
        app.router.add_get(
            "/v2/valuestore/test_4/{list_name}",
            handler,
        )
        server = await aiohttp_server(app)

        base_url = str(server.make_url("/")).rstrip("/")
        url = f"{base_url}/v2/valuestore/test_4/${{LOGPREP_LIST}}"

        list_comparison = {
            "source_fields": ["user"],
            "target_field": "user_results",
            "list_file_paths": ["bad_users.list"],
            "list_search_base_path": url,
        }

        if content_field is not NOT_SET:
            list_comparison["content_field"] = content_field

        processor = await self._create_lister(
            [
                {
                    "filter": "user",
                    "list_comparison": list_comparison,
                }
            ]
        )

        assert await _compare_sets(processor.rules[0]) == {
            "bad_users.list": {"Franz", "Heinz", "Hans"}
        }

    @pytest.mark.parametrize(
        ("yaml_content", "content_field"),
        [
            pytest.param("- Franz\n- Heinz\n- Hans\n", NOT_SET, id="plain-yaml-list"),
            pytest.param(
                "content:\n  - Franz\n  - Heinz\n  - Hans\n",
                "content",
                id="content-field",
            ),
        ],
    )
    async def test_loads_yaml_list_from_http(
        self,
        yaml_content,
        content_field,
        aiohttp_server,
    ):
        async def handler(request: web.Request) -> web.Response:
            assert request.match_info["list_name"] == "hosts.yml"

            return web.Response(
                text=yaml_content,
                content_type="application/yaml",
            )

        app = web.Application()
        app.router.add_get(
            "/v2/valuestore/{list_name}",
            handler,
        )
        server = await aiohttp_server(app)

        base_url = str(server.make_url("/")).rstrip("/")
        url = f"{base_url}/v2/valuestore/${{LOGPREP_LIST}}"

        list_comparison = {
            "source_fields": ["user"],
            "target_field": "user_results",
            "list_file_paths": ["hosts.yml"],
            "list_search_base_path": url,
        }

        if content_field is not NOT_SET:
            list_comparison["content_field"] = content_field

        processor = await self._create_lister(
            [
                {
                    "filter": "user",
                    "list_comparison": list_comparison,
                }
            ]
        )

        assert await _compare_sets(processor.rules[0]) == {"hosts.yml": {"Franz", "Heinz", "Hans"}}

    @pytest.mark.parametrize(
        ("json_content", "content_field"),
        [
            pytest.param(["Franz", "Heinz", "Hans"], ""),
            pytest.param(["Franz", "Heinz", "Hans"], None),
            pytest.param(
                ["Franz", "Heinz", "Hans"], NOT_SET, id="no_content_field_entry_in_config"
            ),
            pytest.param({"content": ["Franz", "Heinz", "Hans"]}, "content"),
            pytest.param({"_": ["Franz", "Heinz", "Hans"]}, "_"),
        ],
    )
    async def test_loads_json_list_from_file(self, json_content, content_field, tmp_path):
        file_name = "file.json"
        (tmp_path / file_name).write_text(json.dumps(json_content))
        list_comparison = {
            "source_fields": ["user"],
            "target_field": "user_results",
            "list_file_paths": [file_name],
            "list_search_base_path": str(tmp_path),
        }
        if content_field is not NOT_SET:
            list_comparison["content_field"] = content_field

        processor = await self._create_lister(
            [{"filter": "user", "list_comparison": list_comparison}]
        )
        assert await _compare_sets(processor.rules[0]) == {"file.json": {"Franz", "Heinz", "Hans"}}

    @pytest.mark.parametrize(
        ("json_content", "content_field"),
        [
            pytest.param({None: ["Franz", "Heinz", "Hans"]}, ""),
            pytest.param({None: ["Franz", "Heinz", "Hans"]}, None),
            pytest.param({"": ["Franz", "Heinz", "Hans"]}, ""),
            pytest.param({"": ["Franz", "Heinz", "Hans"]}, None),
        ],
    )
    async def test_fail_on_json_list_load_from_file(self, json_content, content_field, tmp_path):
        file_name = "file.json"
        (tmp_path / file_name).write_text(json.dumps(json_content))

        RefreshableGetter.reset()
        processor = self._create_test_instance(
            {
                "list_search_base_path": None,
                "rules": [
                    {
                        "filter": "user",
                        "list_comparison": {
                            "source_fields": ["user"],
                            "target_field": "user_results",
                            "list_file_paths": [file_name],
                            "content_field": content_field,
                            "list_search_base_path": str(tmp_path),
                        },
                    }
                ],
            }
        )
        with pytest.raises(ValueError, match="Content is not a list"):
            await processor.setup()

    async def test_static_http_list_is_updated_by_refresh_callback(
        self,
        tmp_path,
        aiohttp_server,
    ):
        responses = [
            "Franz\nHeinz\nHans\n",
            "Franz\nHeinz\n",
        ]
        request_count = 0

        async def handler(request: web.Request) -> web.Response:
            nonlocal request_count

            assert request.match_info["list_name"] == "bad_users.list"
            assert request.query["ref"] == "bla"

            content = responses[min(request_count, len(responses) - 1)]
            request_count += 1

            return web.Response(
                text=content,
                content_type="text/plain",
            )

        app = web.Application()
        app.router.add_get("/tests/testdata/{list_name}", handler)
        server = await aiohttp_server(app)

        base_url = str(server.make_url("/")).rstrip("/")
        url = f"{base_url}/tests/testdata/bad_users.list?ref=bla"

        http_getter_conf = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps({url: {"refresh_interval": 10}}))

        with mock_env({ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}):
            processor = await self._create_lister(
                [
                    {
                        "filter": "user",
                        "list_comparison": {
                            "source_fields": ["user"],
                            "target_field": "user_results",
                            "list_file_paths": ["bad_users.list"],
                            "list_search_base_path": (
                                f"{base_url}/tests/testdata/" "${LOGPREP_LIST}?ref=bla"
                            ),
                        },
                    }
                ]
            )

            rule = processor.rules[0]

            assert await _compare_sets(rule) == {"bad_users.list": {"Franz", "Heinz", "Hans"}}

            getter = HttpGetter(target=url, protocol="http")
            await getter._refresh()

            assert await _compare_sets(rule) == {"bad_users.list": {"Franz", "Heinz"}}

    async def test_resolves_dynamic_http_template_from_event_lazily(self, aiohttp_server):
        document = {"tenant": "acme", "user": "Foo"}
        request_count = 0

        async def handler(request: web.Request) -> web.Response:
            nonlocal request_count
            request_count += 1

            assert request.match_info["tenant"] == "acme"
            assert request.match_info["list_name"] == "bad_users.list"

            return web.Response(
                text="Foo\nBar\n",
                content_type="text/plain",
            )

        app = web.Application()
        app.router.add_get("/{tenant}/{list_name}", handler)
        server = await aiohttp_server(app)

        base_url = str(server.make_url("/")).rstrip("/")
        dynamic_base_path = f"{base_url}/${{tenant}}/${{LOGPREP_LIST}}"

        processor = await self._create_lister(
            [
                {
                    "filter": "user",
                    "list_comparison": {
                        "source_fields": ["user"],
                        "target_field": "user_results",
                        "list_file_paths": ["bad_users.list"],
                        "list_search_base_path": dynamic_base_path,
                    },
                }
            ]
        )
        rule = processor.rules[0]

        assert request_count == 0

        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert request_count == 1
        assert document["user_results"] == {"in_list": ["bad_users.list"]}

    @pytest.mark.parametrize(
        "list_path, environment",
        [
            pytest.param("${tenant.id}/bad_users.list", {}, id="event-field"),
            pytest.param(
                "${LIST_TENANT}/${tenant.id}/bad_users.list",
                {"LIST_TENANT": "customers"},
                id="environment-and-event-field",
            ),
        ],
    )
    async def test_resolves_dynamic_template_in_list_file_path(
        self,
        list_path,
        environment,
        aiohttp_server,
    ):
        document = {"tenant": {"id": "acme"}, "user": "Foo"}
        request_count = 0

        async def handler(request: web.Request) -> web.Response:
            nonlocal request_count
            request_count += 1

            expected_path = (
                "/customers/acme/bad_users.list" if environment else "/acme/bad_users.list"
            )
            assert request.path == expected_path

            return web.Response(
                text="Foo\nBar\n",
                content_type="text/plain",
            )

        app = web.Application()
        app.router.add_get("/{path:.*}", handler)
        server = await aiohttp_server(app)

        base_url = str(server.make_url("/")).rstrip("/")
        list_search_base_path = f"{base_url}/${{LOGPREP_LIST}}"

        with mock_env(environment):
            processor = await self._create_lister(
                [
                    {
                        "filter": "user",
                        "list_comparison": {
                            "source_fields": ["user"],
                            "target_field": "user_results",
                            "list_file_paths": [list_path],
                            "list_search_base_path": list_search_base_path,
                        },
                    }
                ]
            )
            rule = processor.rules[0]

            assert request_count == 0

            await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

            assert request_count == 1

            assert await _compare_sets(
                rule,
                {"tenant": {"id": "acme"}},
            ) == {
                list_path: {"Foo", "Bar"},
            }

    async def test_resolves_environment_template_in_list_file_path_during_setup(
        self,
        aiohttp_server,
    ):
        request_count = 0

        async def handler(request: web.Request) -> web.Response:
            nonlocal request_count
            request_count += 1

            assert request.path == "/acme/bad_users.list"

            return web.Response(
                text="Foo\nBar\n",
                content_type="text/plain",
            )

        app = web.Application()
        app.router.add_get("/{path:.*}", handler)
        server = await aiohttp_server(app)

        base_url = str(server.make_url("/")).rstrip("/")
        list_search_base_path = f"{base_url}/${{LOGPREP_LIST}}"

        with mock_env({"LIST_TENANT": "acme"}):
            processor = await self._create_lister(
                [
                    {
                        "filter": "user",
                        "list_comparison": {
                            "source_fields": ["user"],
                            "target_field": "user_results",
                            "list_file_paths": ["${LIST_TENANT}/bad_users.list"],
                            "list_search_base_path": list_search_base_path,
                        },
                    }
                ]
            )

        assert request_count == 1

        assert await _compare_sets(processor.rules[0]) == {
            "${LIST_TENANT}/bad_users.list": {"Foo", "Bar"}
        }

    async def test_loads_static_and_dynamic_list_file_paths_lazily(
        self,
        aiohttp_server,
    ):
        document = {"tenant": {"id": "acme"}, "user": "Foo"}
        requested_paths = []

        async def handler(request: web.Request) -> web.Response:
            requested_paths.append(request.path)

            if request.path == "/common.list":
                return web.Response(
                    text="Foo\n",
                    content_type="text/plain",
                )

            if request.path == "/acme/bad_users.list":
                return web.Response(
                    text="Foo\nBar\n",
                    content_type="text/plain",
                )

            return web.Response(status=404)

        app = web.Application()
        app.router.add_get("/{path:.*}", handler)
        server = await aiohttp_server(app)

        base_url = str(server.make_url("/")).rstrip("/")
        list_search_base_path = f"{base_url}/${{LOGPREP_LIST}}"

        processor = await self._create_lister(
            [
                {
                    "filter": "user",
                    "list_comparison": {
                        "source_fields": ["user"],
                        "target_field": "user_results",
                        "list_file_paths": [
                            "common.list",
                            "${tenant.id}/bad_users.list",
                        ],
                        "list_search_base_path": list_search_base_path,
                    },
                }
            ]
        )
        rule = processor.rules[0]

        assert requested_paths == ["/common.list"]

        assert await _compare_sets(
            rule,
            {"tenant": {"id": "acme"}},
        ) == {
            "common.list": {"Foo"},
            "${tenant.id}/bad_users.list": {"Foo", "Bar"},
        }

        assert requested_paths == [
            "/common.list",
            "/acme/bad_users.list",
        ]

        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert document["user_results"] == {
            "in_list": [
                "common.list",
                "${tenant.id}/bad_users.list",
            ]
        }

    @pytest.mark.parametrize(
        "document, url_template",
        [
            pytest.param(
                {"tenant": {"id": "acme"}, "user": "Foo"},
                "${tenant.id}/${LOGPREP_LIST}",
                id="nested-field",
            ),
            pytest.param(
                {"tenants": ["acme"], "user": "Foo"},
                "${tenants.0}/${LOGPREP_LIST}",
                id="list-index",
            ),
            pytest.param(
                {"tenants": ["beta", "acme"], "user": "Foo"},
                "${tenants.-1}/${LOGPREP_LIST}",
                id="negative-list-index",
            ),
            pytest.param(
                {"tenant.id": "acme", "user": "Foo"},
                r"${tenant\.id}/${LOGPREP_LIST}",
                id="escaped-dot",
            ),
            pytest.param(
                {r"tenant\.id": "acme", "user": "Foo"},
                r"${tenant\\\.id}/${LOGPREP_LIST}",
                id="escaped-backslash-and-dot",
            ),
        ],
    )
    async def test_resolves_dynamic_http_template_with_field_syntax(
        self,
        document,
        url_template,
        aiohttp_server,
    ):
        list_name = "bad_users.list"
        request_count = 0

        async def handler(request: web.Request) -> web.Response:
            nonlocal request_count
            request_count += 1

            assert request.path == "/acme/bad_users.list"

            return web.Response(
                text="Foo\nBar\n",
                content_type="text/plain",
            )

        app = web.Application()
        app.router.add_get("/{path:.*}", handler)
        server = await aiohttp_server(app)

        base_url = str(server.make_url("/")).rstrip("/")
        list_search_base_path = f"{base_url}/{url_template}"

        processor = await self._create_lister(
            [
                {
                    "filter": "user",
                    "list_comparison": {
                        "source_fields": ["user"],
                        "target_field": "user_results",
                        "list_file_paths": [list_name],
                        "list_search_base_path": list_search_base_path,
                    },
                }
            ]
        )

        assert request_count == 0

        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert request_count == 1
        assert document["user_results"] == {"in_list": [list_name]}

    async def test_dynamic_http_template_rejects_non_scalar_slice_value(self):
        document = {"tenants": ["acme", "beta"], "user": "Foo"}
        expected = {**document, "tags": ["_list_comparison_failure"]}

        processor = await self._create_lister(
            [
                {
                    "filter": "user",
                    "list_comparison": {
                        "source_fields": ["user"],
                        "target_field": "user_results",
                        "list_file_paths": ["bad_users.list"],
                        "list_search_base_path": "http://localhost/${tenants.0:2}/${LOGPREP_LIST}",
                    },
                }
            ]
        )

        with mock.patch.object(
            HttpGetter,
            "_do_request",
            new_callable=mock.AsyncMock,
        ) as do_request:
            result = await processor.process(
                LogEvent(document, original=b"", input_meta=InputMeta())
            )

        assert document == expected
        assert len(result.warnings) == 1
        assert (
            "value for list comparison field 'tenants.0:2' is not a scalar value"
            in _warning_str(result.warnings[0])
        )
        do_request.assert_not_awaited()

    async def test_dynamic_http_template_rejects_non_scalar_event_value(self):
        document = {"tenant": ["acme"], "user": "Foo"}
        expected = {"tenant": ["acme"], "user": "Foo", "tags": ["_list_comparison_failure"]}

        processor = await self._create_lister(
            [
                {
                    "filter": "user",
                    "list_comparison": {
                        "source_fields": ["user"],
                        "target_field": "user_results",
                        "list_file_paths": ["bad_users.list"],
                        "list_search_base_path": HTTP_DYNAMIC_BASE_PATH,
                    },
                }
            ]
        )

        with mock.patch.object(
            HttpGetter,
            "_do_request",
            new_callable=mock.AsyncMock,
        ) as do_request:
            result = await processor.process(
                LogEvent(document, original=b"", input_meta=InputMeta())
            )

        assert document == expected
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], ProcessingWarning)
        assert "value for list comparison field 'tenant' is not a scalar value" in _warning_str(
            result.warnings[0]
        )
        do_request.assert_not_awaited()

    async def test_dynamic_http_template_adds_failure_tag_if_event_field_is_missing(self):
        document = {"user": "Foo"}
        expected = {"user": "Foo", "tags": ["_list_comparison_failure"]}

        processor = await self._create_lister(
            [
                {
                    "filter": "user",
                    "list_comparison": {
                        "source_fields": ["user"],
                        "target_field": "user_results",
                        "list_file_paths": ["bad_users.list"],
                        "list_search_base_path": HTTP_DYNAMIC_BASE_PATH,
                    },
                }
            ]
        )

        with mock.patch.object(
            HttpGetter,
            "_do_request",
            new_callable=mock.AsyncMock,
        ) as do_request:
            result = await processor.process(
                LogEvent(document, original=b"", input_meta=InputMeta())
            )

        assert document == expected
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], ProcessingWarning)
        assert "missing event field 'tenant' for dynamic list comparison path" in _warning_str(
            result.warnings[0]
        )
        do_request.assert_not_awaited()

    async def test_reuses_dynamic_http_compare_set_and_signals_activity(
        self,
        aiohttp_server,
    ):
        first_document = {"tenant": "acme", "user": "Foo"}
        second_document = {"tenant": "acme", "user": "Bar"}
        request_count = 0

        async def handler(request: web.Request) -> web.Response:
            nonlocal request_count
            request_count += 1

            assert request.path == "/acme/bad_users.list"

            return web.Response(
                text="Foo\nBar\n",
                content_type="text/plain",
            )

        app = web.Application()
        app.router.add_get("/{path:.*}", handler)
        server = await aiohttp_server(app)

        base_url = str(server.make_url("/")).rstrip("/")
        url = f"{base_url}/acme/bad_users.list"
        list_search_base_path = f"{base_url}/${{tenant}}/${{LOGPREP_LIST}}"

        processor = await self._create_lister(
            [
                {
                    "filter": "user",
                    "list_comparison": {
                        "source_fields": ["user"],
                        "target_field": "user_results",
                        "list_file_paths": ["bad_users.list"],
                        "list_search_base_path": list_search_base_path,
                    },
                }
            ]
        )

        timestamps = iter([100.0, 125.0])

        def keep_alive(shared: DataSharedPerTarget) -> None:
            shared.last_called = next(timestamps)

        with mock.patch.object(
            DataSharedPerTarget,
            "keep_alive",
            autospec=True,
            side_effect=keep_alive,
        ):
            await processor.process(LogEvent(first_document, original=b"", input_meta=InputMeta()))

            shared = HttpGetter._target_to_data_caches[url]
            assert shared.last_called == 100.0

            await processor.process(LogEvent(second_document, original=b"", input_meta=InputMeta()))

            assert shared.last_called == 125.0

        assert request_count == 1
        assert first_document["user_results"] == {"in_list": ["bad_users.list"]}
        assert second_document["user_results"] == {"in_list": ["bad_users.list"]}

    async def test_dynamic_not_in_list_uses_current_event_compare_set(
        self,
        aiohttp_server,
    ):
        first_document = {"tenant": "acme", "user": "Foo"}
        second_document = {"tenant": "beta", "user": "Missing"}
        list_name = "bad_users.list"

        async def handler(request: web.Request) -> web.Response:
            tenant = request.match_info["tenant"]

            if tenant == "acme":
                return web.Response(
                    text="Foo\n",
                    content_type="text/plain",
                )

            if tenant == "beta":
                return web.Response(
                    text="Bar\n",
                    content_type="text/plain",
                )

            return web.Response(status=404)

        app = web.Application()
        app.router.add_get("/{tenant}/{list_name}", handler)
        server = await aiohttp_server(app)

        base_url = str(server.make_url("/")).rstrip("/")
        dynamic_base_path = f"{base_url}/${{tenant}}/${{LOGPREP_LIST}}"

        processor = await self._create_lister(
            [
                {
                    "filter": "user",
                    "list_comparison": {
                        "source_fields": ["user"],
                        "target_field": "user_results",
                        "list_file_paths": [list_name],
                        "list_search_base_path": dynamic_base_path,
                    },
                }
            ]
        )
        rule = processor.rules[0]

        await processor.process(LogEvent(first_document, original=b"", input_meta=InputMeta()))
        await processor.process(LogEvent(second_document, original=b"", input_meta=InputMeta()))

        assert first_document["user_results"] == {"in_list": [list_name]}
        assert second_document["user_results"] == {"not_in_list": [list_name]}

        assert await _compare_sets(
            rule,
            {"tenant": "acme"},
        ) == {
            list_name: {"Foo"},
        }

        assert await _compare_sets(
            rule,
            {"tenant": "beta"},
        ) == {
            list_name: {"Bar"},
        }

    async def test_dynamic_empty_http_list_is_used_for_not_in_list(
        self,
        aiohttp_server,
    ):
        document = {"tenant": "acme", "user": "Foo"}
        list_name = "bad_users.list"

        async def handler(request: web.Request) -> web.Response:
            assert request.path == "/acme/bad_users.list"

            return web.Response(
                text="",
                content_type="text/plain",
            )

        app = web.Application()
        app.router.add_get("/{tenant}/{list_name}", handler)
        server = await aiohttp_server(app)

        base_url = str(server.make_url("/")).rstrip("/")
        dynamic_base_path = f"{base_url}/${{tenant}}/${{LOGPREP_LIST}}"

        processor = await self._create_lister(
            [
                {
                    "filter": "user",
                    "list_comparison": {
                        "source_fields": ["user"],
                        "target_field": "user_results",
                        "list_file_paths": [list_name],
                        "list_search_base_path": dynamic_base_path,
                    },
                }
            ]
        )
        rule = processor.rules[0]

        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert document == {
            "tenant": "acme",
            "user": "Foo",
            "user_results": {"not_in_list": [list_name]},
        }

        assert await _compare_sets(
            rule,
            {"tenant": "acme"},
        ) == {
            list_name: set(),
        }

    async def test_dynamic_http_failure_does_not_mark_rule_failed(
        self,
        aiohttp_server,
    ):
        failed_document = {"tenant": "acme", "user": "Foo"}
        successful_document = {"tenant": "beta", "user": "Foo"}
        list_name = "bad_users.list"

        async def handler(request: web.Request) -> web.Response:
            tenant = request.match_info["tenant"]

            if tenant == "acme":
                return web.Response(status=500)

            if tenant == "beta":
                return web.Response(
                    text="Foo\n",
                    content_type="text/plain",
                )

            return web.Response(status=404)

        app = web.Application()
        app.router.add_get("/{tenant}/{list_name}", handler)
        server = await aiohttp_server(app)

        base_url = str(server.make_url("/")).rstrip("/")
        failed_url = f"{base_url}/acme/{list_name}"
        successful_url = f"{base_url}/beta/{list_name}"
        dynamic_base_path = f"{base_url}/${{tenant}}/${{LOGPREP_LIST}}"

        processor = await self._create_lister(
            [
                {
                    "filter": "user",
                    "list_comparison": {
                        "source_fields": ["user"],
                        "target_field": "user_results",
                        "list_file_paths": [list_name],
                        "list_search_base_path": dynamic_base_path,
                    },
                }
            ]
        )
        rule = processor.rules[0]

        result = await processor.process(
            LogEvent(failed_document, original=b"", input_meta=InputMeta())
        )

        assert failed_document == {
            "tenant": "acme",
            "user": "Foo",
            "tags": ["_list_comparison_failure"],
        }
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], ProcessingWarning)
        assert rule.data_error is None
        assert len(HttpGetter._target_to_data_caches[failed_url].callbacks) == 0
        assert len(HttpGetter._target_to_data_caches[failed_url].cleanup_callbacks) == 0

        result = await processor.process(
            LogEvent(successful_document, original=b"", input_meta=InputMeta())
        )

        assert result.warnings == []
        assert successful_document == {
            "tenant": "beta",
            "user": "Foo",
            "user_results": {"in_list": [list_name]},
        }
        assert rule.data_error is None
        assert len(HttpGetter._target_to_data_caches[successful_url].callbacks) == 1
        assert len(HttpGetter._target_to_data_caches[successful_url].cleanup_callbacks) == 1

    async def test_removes_timed_out_dynamic_compare_set(
        self,
        aiohttp_server,
    ):
        document = {"tenant": "acme", "user": "Foo"}
        request_count = 0

        async def handler(request: web.Request) -> web.Response:
            nonlocal request_count
            request_count += 1

            assert request.path == "/acme/bad_users.list"

            return web.Response(
                text="Foo\n",
                content_type="text/plain",
            )

        app = web.Application()
        app.router.add_get("/{path:.*}", handler)
        server = await aiohttp_server(app)

        base_url = str(server.make_url("/")).rstrip("/")
        url = f"{base_url}/acme/bad_users.list"
        dynamic_base_path = f"{base_url}/${{tenant}}/${{LOGPREP_LIST}}"

        processor = await self._create_lister(
            [
                {
                    "filter": "user",
                    "list_comparison": {
                        "source_fields": ["user"],
                        "target_field": "user_results",
                        "list_file_paths": ["bad_users.list"],
                        "list_search_base_path": dynamic_base_path,
                    },
                }
            ]
        )

        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert url in HttpGetter._target_to_data_caches
        assert request_count == 1

        shared = HttpGetter._target_to_data_caches[url]

        assert shared.last_called is not None
        assert shared.timeout_interval is not None

        shared.last_called -= shared.timeout_interval + 1

        await refresh_getters()

        assert url not in HttpGetter._target_to_data_caches

    @pytest.mark.parametrize(
        "http_list_content, expected_content",
        [
            pytest.param("", set(), id="empty-body"),
            pytest.param("\n", {""}, id="single-empty-line"),
        ],
    )
    async def test_static_http_empty_body_or_empty_line_updates_compare_set(
        self,
        http_list_content,
        expected_content,
        aiohttp_server,
    ):
        document = {"user": "Foo"}
        list_name = "bad_users.list"
        request_count = 0

        async def handler(request: web.Request) -> web.Response:
            nonlocal request_count
            request_count += 1

            assert request.match_info["list_name"] == list_name
            assert request.query["ref"] == "bla"

            return web.Response(
                text=http_list_content,
                content_type="text/plain",
            )

        app = web.Application()
        app.router.add_get("/tests/testdata/{list_name}", handler)
        server = await aiohttp_server(app)

        base_url = str(server.make_url("/")).rstrip("/")

        processor = await self._create_lister(
            [
                {
                    "filter": "user",
                    "list_comparison": {
                        "source_fields": ["user"],
                        "target_field": "user_results",
                        "list_file_paths": [list_name],
                        "list_search_base_path": (
                            f"{base_url}/tests/testdata/${{LOGPREP_LIST}}?ref=bla"
                        ),
                    },
                }
            ]
        )
        rule = processor.rules[0]

        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert document == {"user": "Foo", "user_results": {"not_in_list": [list_name]}}
        assert request_count == 1
        assert await _compare_sets(rule) == {list_name: expected_content}

    async def test_process_adds_failure_tag_if_http_list_returns_500(
        self,
        caplog,
        aiohttp_server,
    ):
        document = {"user": "Foo"}
        list_name = "bad_users.list"
        request_count = 0

        async def handler(request: web.Request) -> web.Response:
            nonlocal request_count
            request_count += 1

            assert request.match_info["list_name"] == list_name
            assert request.query["ref"] == "bla"

            return web.Response(status=500)

        app = web.Application()
        app.router.add_get("/tests/testdata/{list_name}", handler)
        server = await aiohttp_server(app)

        base_url = str(server.make_url("/")).rstrip("/")

        RefreshableGetter.reset()
        processor = self._create_test_instance(
            {
                "list_search_base_path": None,
                "rules": [
                    {
                        "filter": "user",
                        "list_comparison": {
                            "source_fields": ["user"],
                            "target_field": "user_results",
                            "list_file_paths": [list_name],
                            "list_search_base_path": (
                                f"{base_url}/tests/testdata/${{LOGPREP_LIST}}?ref=bla"
                            ),
                        },
                    }
                ],
            }
        )

        await processor.setup()

        rule = processor.rules[0]

        assert isinstance(rule.data_error, RefreshableGetterError)
        assert request_count == 4
        assert "500" in caplog.text
        assert "ListComparisonRule failed" in caplog.text

        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert document == {"user": "Foo", "tags": ["_list_comparison_failure"]}
        assert request_count == 4

    async def test_recovers_after_failed_http_getter_setup(self, aiohttp_server):
        list_name = "bad_users.list"
        response_status = 500
        request_statuses = []

        async def handler(request: web.Request) -> web.Response:
            assert request.match_info["list_name"] == list_name
            assert request.query["ref"] == "bla"

            request_statuses.append(response_status)

            if response_status == 500:
                return web.Response(status=500)

            return web.Response(
                text="Foo\n",
                content_type="text/plain",
            )

        app = web.Application()
        app.router.add_get("/tests/testdata/{list_name}", handler)
        server = await aiohttp_server(app)

        base_url = str(server.make_url("/")).rstrip("/")
        rules = [
            {
                "filter": "user",
                "list_comparison": {
                    "source_fields": ["user"],
                    "target_field": "user_results",
                    "list_file_paths": [list_name],
                    "list_search_base_path": (
                        f"{base_url}/tests/testdata/${{LOGPREP_LIST}}?ref=bla"
                    ),
                },
            }
        ]

        processor = await self._create_lister(rules)
        rule = processor.rules[0]

        document = {"user": "Foo"}
        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert isinstance(rule.data_error, RefreshableGetterError)
        assert document == {"user": "Foo", "tags": ["_list_comparison_failure"]}
        assert request_statuses == [500, 500, 500, 500]

        response_status = 200

        processor = await self._create_lister(rules)
        rule = processor.rules[0]

        document = {"user": "Foo"}
        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert rule.data_error is None
        assert document == {"user": "Foo", "user_results": {"in_list": [list_name]}}
        assert await _compare_sets(rule) == {list_name: {"Foo"}}
        assert request_statuses == [500, 500, 500, 500, 200]

    async def test_recovers_after_failed_http_getter_while_processing(
        self,
        tmp_path,
        aiohttp_server,
    ):
        list_name = "bad_users.list"
        response_status = 500
        request_statuses = []

        async def handler(request: web.Request) -> web.Response:
            assert request.match_info["list_name"] == list_name
            assert request.query["ref"] == "bla"

            request_statuses.append(response_status)

            if response_status == 500:
                return web.Response(status=500)

            return web.Response(
                text="Foo\n",
                content_type="text/plain",
            )

        app = web.Application()
        app.router.add_get("/tests/testdata/{list_name}", handler)
        server = await aiohttp_server(app)

        base_url = str(server.make_url("/")).rstrip("/")
        url = f"{base_url}/tests/testdata/{list_name}?ref=bla"

        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps({url: {"refresh_interval": 1}}))

        with mock_env({ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}):
            processor = await self._create_lister(
                [
                    {
                        "filter": "user",
                        "list_comparison": {
                            "source_fields": ["user"],
                            "target_field": "user_results",
                            "list_file_paths": [list_name],
                            "list_search_base_path": (
                                f"{base_url}/tests/testdata/${{LOGPREP_LIST}}?ref=bla"
                            ),
                        },
                    }
                ]
            )
            rule = processor.rules[0]

            document = {"user": "Foo"}
            await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

            assert isinstance(rule.data_error, RefreshableGetterError)
            assert document == {"user": "Foo", "tags": ["_list_comparison_failure"]}
            assert request_statuses == [500, 500, 500, 500]

            response_status = 200

            getter = HttpGetter(target=url, protocol="http")
            await getter._refresh()

            assert rule.data_error is None
            assert await _compare_sets(rule) == {list_name: {"Foo"}}
            assert request_statuses == [500, 500, 500, 500, 200]
