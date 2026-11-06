# pylint: disable=missing-docstring,too-many-lines,protected-access,duplicate-code
import json
import re
from copy import deepcopy
from pathlib import Path
from unittest import mock

import pytest
import responses

from logprep.factory_error import InvalidResourcesError
from logprep.ng.abc.event import InputMeta, LogEvent
from logprep.ng.processor.list_comparison.processor import ListComparison
from logprep.ng.processor.list_comparison.rule import ListComparisonRule
from logprep.ng.util.getter import (
    HttpGetter,
    RefreshableGetter,
    refresh_getters,
)
from logprep.processor.base.exceptions import ProcessingWarning
from logprep.util.defaults import ENV_NAME_LOGPREP_GETTER_CONFIG
from tests.conftest import Endpoint, Response, mock_env
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


async def _compare_sets(rule: ListComparisonRule, event: dict | None = None) -> dict[str, set]:
    """Materialize a rule's compare sets via its public ``iter_compare_sets`` API."""
    return {name: content async for name, content in rule.iter_compare_sets(event or {})}


def _warning_str(warning) -> str:
    return f"{type(warning).__name__}: {warning}"


test_cases = deepcopy(non_ng_test_cases)
failure_test_cases = deepcopy(non_ng_failure_test_cases)


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
    async def test_testcases(self, rule, event, expected, provision_context):
        rule = deepcopy(rule)

        list_search_base_path = rule["list_comparison"].get("list_search_base_path")

        if list_search_base_path and list_search_base_path.startswith(("http://", "https://")):
            base_url = "https://example.dd"
            provision_context(
                Endpoint(
                    url=re.compile(rf"{base_url}/.*"),
                    body="# a comment\nFranz\nAlpha\nBeta\n",
                )
            )
            rule["list_comparison"]["list_search_base_path"] = f"{base_url}/${{LOGPREP_LIST}}"

        processor = await self._create_lister([rule])
        await processor.setup()
        log_event = LogEvent(event, original=b"", input_meta=InputMeta())

        await processor.process(log_event)
        assert log_event.data == expected

    @pytest.mark.parametrize("rule, event, expected, error_message", failure_test_cases)
    async def test_testcases_failure_handling(
        self, rule, event, expected, error_message, provision_context
    ):
        provision_context(
            Endpoint(
                url=r"http.*",
                status=500,
            ),
        )
        processor = await self._create_lister([rule])
        log_event = LogEvent(event, original=b"", input_meta=InputMeta())
        result = await processor.process(log_event)
        assert len(result.warnings) == 1
        assert re.search(error_message, _warning_str(result.warnings[0]))
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

    async def test_loads_static_http_list_with_template_base_path(self, provision_context):
        provision_context(
            Endpoint(
                url="http://example.dd/tests/testdata/bad_users.list",
                body="Franz\nHeinz\nHans\n",
                content_type="text/plain",
            )
        )

        processor = await self._create_lister(
            [
                {
                    "filter": "user",
                    "list_comparison": {
                        "source_fields": ["user"],
                        "target_field": "user_results",
                        "list_file_paths": ["bad_users.list"],
                        "list_search_base_path": (
                            "http://example.dd/tests/testdata/${LOGPREP_LIST}"
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
                ["Franz", "Heinz", "Hans"], NOT_SET, id="no_content_field_entry_in_config"
            ),
            pytest.param({"content": ["Franz", "Heinz", "Hans"]}, "content"),
            pytest.param({"_": ["Franz", "Heinz", "Hans"]}, "_"),
        ],
    )
    async def test_loads_json_list_from_http(
        self,
        json_content,
        content_field,
        provision_context,
    ):
        base_url = "http://example.dd"
        path = "v2/valuestore/test_4"
        list_name = "bad_users.list"
        provision_context(
            Endpoint(
                url=f"{base_url}/{path}/{list_name}",
                json=json_content,
            ),
        )

        url_template = f"{base_url}/{path}/${{LOGPREP_LIST}}"

        list_comparison = {
            "source_fields": ["user"],
            "target_field": "user_results",
            "list_file_paths": ["bad_users.list"],
            "list_search_base_path": url_template,
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
        assert await _compare_sets(processor.rules[0]) == {list_name: {"Franz", "Heinz", "Hans"}}

    @pytest.mark.parametrize(
        ("yaml_content", "content_field"),
        [
            pytest.param("- Franz\n- Heinz\n- Hans\n", NOT_SET, id="plain-yaml-list"),
            pytest.param(
                "content:\n  - Franz\n  - Heinz\n  - Hans\n", "content", id="content-field"
            ),
        ],
    )
    async def test_loads_yaml_list_from_http(
        self,
        yaml_content,
        content_field,
        provision_context,
    ):
        base_url = "https://example.dd"
        path = "v2/valuestore"
        list_name = "hosts.yml"
        provision_context(
            Endpoint(
                url=f"{base_url}/{path}/{list_name}",
                body=yaml_content,
                content_type="application/yaml",
            ),
        )
        url = f"{base_url}/{path}/${{LOGPREP_LIST}}"

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
        with pytest.raises(InvalidResourcesError, match="Content is not a list"):
            await processor.setup()

    async def test_static_http_list_is_updated_by_refresh_callback(
        self,
        tmp_path,
        provision_context,
    ):
        base_url = "http://example.dd"
        list_name = "bad_users.list"
        path = "tests/testdata"
        url = f"{base_url}/{path}/{list_name}"

        provision_context(
            Endpoint(
                url=url,
                responses=[
                    Response(body="Franz\nHeinz\nHans\n"),
                    Response(body="Franz\nHeinz\n"),
                ],
            )
        )

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
                            "list_search_base_path": (f"{base_url}/{path}/${{LOGPREP_LIST}}"),
                        },
                    }
                ]
            )
            rule = processor.rules[0]
            assert await _compare_sets(rule) == {"bad_users.list": {"Franz", "Heinz", "Hans"}}

            getter = HttpGetter(target=url, protocol="http")
            await getter._refresh()

    @responses.activate
    async def test_resolves_dynamic_http_template_from_event_lazily(self, provision_context):
        document = {"tenant": "acme", "user": "Foo"}
        base_url = "http://yolo.dd"

        endpoint = Endpoint(url=f"{base_url}/acme/bad_users.list", body="Foo\nBar\n")
        provision_context(endpoint)

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

        assert endpoint.call_count == 0

        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert endpoint.call_count == 1
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
        provision_context,
    ):
        document = {"tenant": {"id": "acme"}, "user": "Foo"}
        base_url = "http://example.dd"
        list_name = "bad_users.list"
        path = "customers/acme" if environment else "acme"
        endpoint = Endpoint(
            url=f"{base_url}/{path}/{list_name}",
            body="Foo\nBar\n",
        )
        provision_context(endpoint)
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

            assert endpoint.call_count == 0

            await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

            assert endpoint.call_count == 1

            assert await _compare_sets(
                rule,
                {"tenant": {"id": "acme"}},
            ) == {
                list_path: {"Foo", "Bar"},
            }

    async def test_resolves_environment_template_in_list_file_path_during_setup(
        self,
        provision_context,
    ):
        base_url = "http://blabla.dd"
        endpoint = Endpoint(url=f"{base_url}/acme/bad_users.list", body="Foo\nBar\n")
        provision_context(endpoint)
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

        assert endpoint.call_count == 1

        assert await _compare_sets(processor.rules[0]) == {
            "${LIST_TENANT}/bad_users.list": {"Foo", "Bar"}
        }

    async def test_loads_static_and_dynamic_list_file_paths_lazily(
        self,
        provision_context,
    ):
        document = {"tenant": {"id": "acme"}, "user": "Foo"}
        base_url = "http://example.dd"

        common_endpoint = Endpoint(url=f"{base_url}/common.list", body="Foo\n")
        acme_endpoint = Endpoint(url=f"{base_url}/acme/bad_users.list", body="Foo\nBar\n")

        provision_context(common_endpoint, acme_endpoint)

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

        assert common_endpoint.call_count == 1
        assert acme_endpoint.call_count == 0

        assert await _compare_sets(
            rule,
            {"tenant": {"id": "acme"}},
        ) == {
            "common.list": {"Foo"},
            "${tenant.id}/bad_users.list": {"Foo", "Bar"},
        }

        assert common_endpoint.call_count == 1
        assert acme_endpoint.call_count == 1

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
        provision_context,
    ):
        base_url = "http://exmaple.dd"
        list_name = "bad_users.list"
        endpoint = Endpoint(
            url=f"{base_url}/acme/bad_users.list",
            body="Foo\nBar\n",
        )
        provision_context(endpoint)

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

        assert endpoint.call_count == 0

        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert endpoint.call_count == 1
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
        assert "value for dynamic URI field 'tenants.0:2' is not a scalar value" in _warning_str(
            result.warnings[0]
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
        assert "value for dynamic URI field 'tenant' is not a scalar value" in _warning_str(
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
        assert "missing event field 'tenant' for dynamic URI" in _warning_str(result.warnings[0])
        do_request.assert_not_awaited()

    async def test_reuses_dynamic_http_compare_set_and_signals_activity(
        self,
        provision_context,
    ):
        base_url = "http://zombo.dd"
        first_document = {"tenant": "acme", "user": "Foo"}
        second_document = {"tenant": "acme", "user": "Bar"}
        url = f"{base_url}/acme/bad_users.list"

        endpoint = Endpoint(
            url=url,
            body="Foo\nBar\n",
        )
        provision_context(endpoint)

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
        with mock.patch("logprep.util.getter.time.monotonic", return_value=100.0):
            await processor.process(LogEvent(first_document, original=b"", input_meta=InputMeta()))
            assert HttpGetter._target_to_data_caches[url].last_called == 100.0
            assert endpoint.call_count == 1

        with mock.patch("logprep.util.getter.time.monotonic", return_value=125.0):
            await processor.process(LogEvent(second_document, original=b"", input_meta=InputMeta()))
            assert HttpGetter._target_to_data_caches[url].last_called == 125.0
            assert endpoint.call_count == 1

        assert first_document["user_results"] == {"in_list": ["bad_users.list"]}
        assert second_document["user_results"] == {"in_list": ["bad_users.list"]}

    async def test_dynamic_not_in_list_uses_current_event_compare_set(
        self,
        provision_context,
    ):
        base_url = "https://example.dd"
        first_document = {"tenant": "acme", "user": "Foo"}
        second_document = {"tenant": "beta", "user": "Missing"}
        list_name = "bad_users.list"
        provision_context(
            Endpoint(url=f"{base_url}/acme/{list_name}", body="Foo\n"),
            Endpoint(url=f"{base_url}/beta/{list_name}", body="Bar\n"),
        )
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

    async def test_dynamic_empty_http_list_is_used_for_not_in_list(
        self,
        provision_context,
    ):
        base_url = "http://example.dd"
        document = {"tenant": "acme", "user": "Foo"}
        list_name = "bad_users.list"

        provision_context(
            Endpoint(url=f"{base_url}/acme/bad_users.list", body=""),
        )

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
        provision_context,
    ):
        failed_document = {"tenant": "acme", "user": "Foo"}
        successful_document = {"tenant": "beta", "user": "Foo"}
        list_name = "bad_users.list"
        failed_url = "http://localhost/acme/bad_users.list"
        successful_url = "http://localhost/beta/bad_users.list"
        provision_context(
            Endpoint(url=failed_url, status=500),
            Endpoint(url=successful_url, body="Foo\n"),
        )

        processor = await self._create_lister(
            [
                {
                    "filter": "user",
                    "list_comparison": {
                        "source_fields": ["user"],
                        "target_field": "user_results",
                        "list_file_paths": [list_name],
                        "list_search_base_path": HTTP_DYNAMIC_BASE_PATH,
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
        assert len(HttpGetter._target_to_data_caches[failed_url].callbacks) == 1
        assert len(HttpGetter._target_to_data_caches[failed_url].cleanup_callbacks) == 1

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
        provision_context,
    ):
        document = {"tenant": "acme", "user": "Foo"}
        base_url = "http://example.dd"
        url = f"{base_url}/acme/bad_users.list"
        dynamic_base_path = f"{base_url}/${{tenant}}/${{LOGPREP_LIST}}"

        endpoint = Endpoint(url=url, body="Foo\n")
        provision_context(endpoint)
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
        assert endpoint.call_count == 1

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
        provision_context,
    ):
        base_url = "https://example.dd"
        document = {"user": "Foo"}
        path = "tests/testdata"
        list_name = "bad_users.list"
        endpoint = Endpoint(
            url=f"{base_url}/{path}/{list_name}",
            body=http_list_content,
        )
        provision_context(endpoint)

        processor = await self._create_lister(
            [
                {
                    "filter": "user",
                    "list_comparison": {
                        "source_fields": ["user"],
                        "target_field": "user_results",
                        "list_file_paths": [list_name],
                        "list_search_base_path": f"{base_url}/{path}/${{LOGPREP_LIST}}",
                    },
                }
            ]
        )
        rule = processor.rules[0]

        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert document == {"user": "Foo", "user_results": {"not_in_list": [list_name]}}
        assert endpoint.call_count == 1
        assert await _compare_sets(rule) == {list_name: expected_content}

    async def test_process_adds_failure_tag_if_http_list_returns_500(
        self,
        caplog,
        provision_context,
    ):
        base_url = "https://example.dd"
        path = "tests/testdata"
        document = {"user": "Foo"}
        list_name = "bad_users.list"
        endpoint = Endpoint(
            url=f"{base_url}/{path}/{list_name}?ref=bla",
            status=500,
        )
        provision_context(endpoint)

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
                                f"{base_url}/{path}/${{LOGPREP_LIST}}?ref=bla"
                            ),
                        },
                    }
                ],
            }
        )

        await processor.setup()

        rule = processor.rules[0]

        assert isinstance(rule.data_error, InvalidResourcesError)
        assert endpoint.call_count == 4
        assert "500" in caplog.text
        assert "ListComparisonRule failed" in caplog.text

        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert document == {"user": "Foo", "tags": ["_list_comparison_failure"]}
        assert endpoint.call_count == 4

    async def test_recovers_after_failed_http_getter_setup(self, provision_context):
        base_url = "https://example.dd"
        path = "tests/testdata"
        list_name = "bad_users.list"

        endpoint = Endpoint(
            url=f"{base_url}/{path}/{list_name}?ref=bla",
            responses=[
                Response(status=500),
                Response(status=500),
                Response(status=500),
                Response(status=500),
                Response(
                    body="Foo\n",
                ),
            ],
        )
        provision_context(endpoint)
        rules = [
            {
                "filter": "user",
                "list_comparison": {
                    "source_fields": ["user"],
                    "target_field": "user_results",
                    "list_file_paths": [list_name],
                    "list_search_base_path": (f"{base_url}/{path}/${{LOGPREP_LIST}}?ref=bla"),
                },
            }
        ]

        processor = await self._create_lister(rules)
        rule = processor.rules[0]

        document = {"user": "Foo"}
        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert isinstance(rule.data_error, InvalidResourcesError)
        assert document == {"user": "Foo", "tags": ["_list_comparison_failure"]}
        assert endpoint.call_count == 4

        processor = await self._create_lister(rules)
        rule = processor.rules[0]

        document = {"user": "Foo"}
        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert rule.data_error is None
        assert document == {"user": "Foo", "user_results": {"in_list": [list_name]}}
        assert await _compare_sets(rule) == {list_name: {"Foo"}}
        assert endpoint.call_count == 5

    async def test_recovers_after_failed_http_getter_while_processing(
        self,
        tmp_path,
        provision_context,
    ):
        base_url = "https://example.dd"
        path = "tests/testdata"
        list_name = "bad_users.list"

        endpoint = Endpoint(
            url=f"{base_url}/{path}/{list_name}?ref=bla",
            responses=[
                Response(status=500),
                Response(status=500),
                Response(status=500),
                Response(status=500),
                Response(
                    body="Foo\n",
                    content_type="text/plain",
                ),
            ],
        )

        provision_context(endpoint)

        url = f"{base_url}/{path}/{list_name}?ref=bla"

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
                                f"{base_url}/{path}/${{LOGPREP_LIST}}?ref=bla"
                            ),
                        },
                    }
                ]
            )
            rule = processor.rules[0]

            document = {"user": "Foo"}
            await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

            assert isinstance(rule.data_error, InvalidResourcesError)
            assert document == {"user": "Foo", "tags": ["_list_comparison_failure"]}
            assert endpoint.call_count == 4

            getter = HttpGetter(target=url, protocol="http")
            await getter._refresh()

            assert endpoint.call_count == 5
            assert await _compare_sets(rule) == {list_name: {"Foo"}}

            assert rule.data_error is None

    async def test_has_async_io(self):
        assert await self.object.has_asyncio() is True
