# pylint: disable=missing-docstring,too-many-lines,protected-access,duplicate-code
import json
import re
import time
from copy import deepcopy
from pathlib import Path
from unittest import mock

import pytest
import responses

from logprep.ng.abc.event import InputMeta, LogEvent
from logprep.ng.processor.list_comparison.processor import ListComparison
from logprep.processor.base.exceptions import ProcessingWarning
from logprep.util.defaults import ENV_NAME_LOGPREP_GETTER_CONFIG
from logprep.util.getter import (
    HttpGetter,
    RefreshableGetter,
    RefreshableGetterError,
    refresh_getters,
)
from tests.conftest import mock_env
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.list_comparison.test_list_comparison import (
    HTTP_BASE_PATH,
    HTTP_DYNAMIC_BASE_PATH,
    LOCAL_BASE_PATH,
    NOT_SET,
    _compare_sets,
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
    async def test_testcases(self, rule, event, expected):
        with responses.RequestsMock(assert_all_requests_are_fired=False) as mocked:
            mocked.add_callback(
                responses.GET,
                re.compile(r"http.*"),
                callback=lambda _: (200, {}, "# a comment\nFranz\nAlpha\nBeta\n"),
            )
            processor = await self._create_lister([rule])
            log_event = LogEvent(event, original=b"", input_meta=InputMeta())
            await processor.process(log_event)
        assert log_event.data == expected

    @pytest.mark.parametrize("rule, event, expected, error_message", failure_test_cases)
    async def test_testcases_failure_handling(self, rule, event, expected, error_message):
        with responses.RequestsMock(assert_all_requests_are_fired=False) as mocked:
            mocked.add_callback(
                responses.GET, re.compile(r"http.*"), callback=lambda _: (500, {}, "")
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

    @responses.activate
    async def test_loads_static_http_list_with_template_base_path(self):
        url = "http://localhost/tests/testdata/bad_users.list?ref=bla"
        responses.add(responses.GET, url, "Franz\nHeinz\nHans\n")
        processor = await self._create_lister(
            [
                {
                    "filter": "user",
                    "list_comparison": {
                        "source_fields": ["user"],
                        "target_field": "user_results",
                        "list_file_paths": ["bad_users.list"],
                        "list_search_base_path": (
                            "http://localhost/tests/testdata/${LOGPREP_LIST}?ref=bla"
                        ),
                    },
                }
            ]
        )
        assert _compare_sets(processor.rules[0]) == {"bad_users.list": {"Franz", "Heinz", "Hans"}}

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
    @responses.activate
    async def test_loads_json_list_from_http(self, json_content, content_field):
        url = "http://localhost:8080/v2/valuestore/test_4/${LOGPREP_LIST}"
        responses.add(
            responses.GET,
            url.replace("${LOGPREP_LIST}", "bad_users.list"),
            json.dumps(json_content),
            content_type="application/json",
        )
        list_comparison = {
            "source_fields": ["user"],
            "target_field": "user_results",
            "list_file_paths": ["bad_users.list"],
            "list_search_base_path": url,
        }
        if content_field is not NOT_SET:
            list_comparison["content_field"] = content_field

        processor = await self._create_lister(
            [{"filter": "user", "list_comparison": list_comparison}]
        )
        assert _compare_sets(processor.rules[0]) == {"bad_users.list": {"Franz", "Heinz", "Hans"}}

    @pytest.mark.parametrize(
        ("yaml_content", "content_field"),
        [
            pytest.param("- Franz\n- Heinz\n- Hans\n", NOT_SET, id="plain-yaml-list"),
            pytest.param(
                "content:\n  - Franz\n  - Heinz\n  - Hans\n", "content", id="content-field"
            ),
        ],
    )
    @responses.activate
    async def test_loads_yaml_list_from_http(self, yaml_content, content_field):
        url = "http://localhost:8080/v2/valuestore/${LOGPREP_LIST}"
        responses.add(
            responses.GET,
            url.replace("${LOGPREP_LIST}", "hosts.yml"),
            yaml_content,
            content_type="application/yaml",
        )
        list_comparison = {
            "source_fields": ["user"],
            "target_field": "user_results",
            "list_file_paths": ["hosts.yml"],
            "list_search_base_path": url,
        }
        if content_field is not NOT_SET:
            list_comparison["content_field"] = content_field

        processor = await self._create_lister(
            [{"filter": "user", "list_comparison": list_comparison}]
        )
        assert _compare_sets(processor.rules[0]) == {"hosts.yml": {"Franz", "Heinz", "Hans"}}

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
        assert _compare_sets(processor.rules[0]) == {"file.json": {"Franz", "Heinz", "Hans"}}

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

    @responses.activate
    async def test_static_http_list_is_updated_by_refresh_callback(self, tmp_path):
        url = "http://localhost/tests/testdata/bad_users.list?ref=bla"
        responses.add(responses.GET, url, "Franz\nHeinz\nHans\n")
        responses.add(responses.GET, url, "Franz\nHeinz\n")

        http_getter_conf: Path = tmp_path / "http_getter.json"
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
                                "http://localhost/tests/testdata/${LOGPREP_LIST}?ref=bla"
                            ),
                        },
                    }
                ]
            )
            rule = processor.rules[0]
            assert _compare_sets(rule) == {"bad_users.list": {"Franz", "Heinz", "Hans"}}

            HttpGetter(target=url, protocol="http").scheduler.run_all()
            assert _compare_sets(rule) == {"bad_users.list": {"Franz", "Heinz"}}

    @responses.activate
    async def test_resolves_dynamic_http_template_from_event_lazily(self):
        document = {"tenant": "acme", "user": "Foo"}
        url = "http://localhost/acme/bad_users.list"
        responses.add(responses.GET, url=url, body="Foo\nBar\n", status=200)

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
        rule = processor.rules[0]

        assert len(responses.calls) == 0

        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert document["user_results"] == {"in_list": ["bad_users.list"]}
        assert _compare_sets(rule, {"tenant": "acme"}) == {"bad_users.list": {"Foo", "Bar"}}
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == url

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
    @responses.activate
    async def test_resolves_dynamic_template_in_list_file_path(self, list_path, environment):
        document = {"tenant": {"id": "acme"}, "user": "Foo"}
        path_prefix = "customers/" if environment else ""
        url = f"http://localhost/{path_prefix}acme/bad_users.list"
        responses.add(responses.GET, url=url, body="Foo\nBar\n", status=200)

        with mock_env(environment):
            processor = await self._create_lister(
                [
                    {
                        "filter": "user",
                        "list_comparison": {
                            "source_fields": ["user"],
                            "target_field": "user_results",
                            "list_file_paths": [list_path],
                            "list_search_base_path": HTTP_BASE_PATH,
                        },
                    }
                ]
            )
            rule = processor.rules[0]

            assert len(responses.calls) == 0

            await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

            assert _compare_sets(rule, {"tenant": {"id": "acme"}}) == {list_path: {"Foo", "Bar"}}

        assert document["user_results"] == {"in_list": [list_path]}
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == url

    @responses.activate
    async def test_resolves_environment_template_in_list_file_path_during_setup(self):
        url = "http://localhost/acme/bad_users.list"
        responses.add(responses.GET, url=url, body="Foo\nBar\n", status=200)

        with mock_env({"LIST_TENANT": "acme"}):
            processor = await self._create_lister(
                [
                    {
                        "filter": "user",
                        "list_comparison": {
                            "source_fields": ["user"],
                            "target_field": "user_results",
                            "list_file_paths": ["${LIST_TENANT}/bad_users.list"],
                            "list_search_base_path": HTTP_BASE_PATH,
                        },
                    }
                ]
            )

        assert _compare_sets(processor.rules[0]) == {
            "${LIST_TENANT}/bad_users.list": {"Foo", "Bar"}
        }
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == url

    @responses.activate
    async def test_loads_static_and_dynamic_list_file_paths_lazily(self):
        document = {"tenant": {"id": "acme"}, "user": "Foo"}
        static_url = "http://localhost/common.list"
        dynamic_url = "http://localhost/acme/bad_users.list"
        responses.add(responses.GET, url=static_url, body="Foo\n", status=200)
        responses.add(responses.GET, url=dynamic_url, body="Foo\nBar\n", status=200)

        processor = await self._create_lister(
            [
                {
                    "filter": "user",
                    "list_comparison": {
                        "source_fields": ["user"],
                        "target_field": "user_results",
                        "list_file_paths": ["common.list", "${tenant.id}/bad_users.list"],
                        "list_search_base_path": HTTP_BASE_PATH,
                    },
                }
            ]
        )
        rule = processor.rules[0]

        assert _compare_sets(rule, {"tenant": {"id": "acme"}}) == {
            "common.list": {"Foo"},
            "${tenant.id}/bad_users.list": {"Foo", "Bar"},
        }

        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert document["user_results"] == {
            "in_list": ["common.list", "${tenant.id}/bad_users.list"]
        }
        assert len(responses.calls) == 2

    @pytest.mark.parametrize(
        "document, url_template",
        [
            pytest.param(
                {"tenant": {"id": "acme"}, "user": "Foo"},
                "http://localhost/${tenant.id}/${LOGPREP_LIST}",
                id="nested-field",
            ),
            pytest.param(
                {"tenants": ["acme"], "user": "Foo"},
                "http://localhost/${tenants.0}/${LOGPREP_LIST}",
                id="list-index",
            ),
            pytest.param(
                {"tenants": ["beta", "acme"], "user": "Foo"},
                "http://localhost/${tenants.-1}/${LOGPREP_LIST}",
                id="negative-list-index",
            ),
            pytest.param(
                {"tenant.id": "acme", "user": "Foo"},
                r"http://localhost/${tenant\.id}/${LOGPREP_LIST}",
                id="escaped-dot",
            ),
            pytest.param(
                {r"tenant\.id": "acme", "user": "Foo"},
                r"http://localhost/${tenant\\\.id}/${LOGPREP_LIST}",
                id="escaped-backslash-and-dot",
            ),
        ],
    )
    @responses.activate
    async def test_resolves_dynamic_http_template_with_field_syntax(self, document, url_template):
        list_name = "bad_users.list"
        url = "http://localhost/acme/bad_users.list"
        responses.add(responses.GET, url=url, body="Foo\nBar\n", status=200)

        processor = await self._create_lister(
            [
                {
                    "filter": "user",
                    "list_comparison": {
                        "source_fields": ["user"],
                        "target_field": "user_results",
                        "list_file_paths": [list_name],
                        "list_search_base_path": url_template,
                    },
                }
            ]
        )

        assert len(responses.calls) == 0

        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert document["user_results"] == {"in_list": [list_name]}
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == url

    @responses.activate
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

        result = await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert document == expected
        assert len(result.warnings) == 1
        assert (
            "value for list comparison field 'tenants.0:2' is not a scalar value"
            in _warning_str(result.warnings[0])
        )
        assert len(responses.calls) == 0

    @responses.activate
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

        result = await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert document == expected
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], ProcessingWarning)
        assert "value for list comparison field 'tenant' is not a scalar value" in _warning_str(
            result.warnings[0]
        )
        assert len(responses.calls) == 0

    @responses.activate
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

        result = await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert document == expected
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], ProcessingWarning)
        assert "missing event field 'tenant' for dynamic list comparison path" in _warning_str(
            result.warnings[0]
        )
        assert len(responses.calls) == 0

    @responses.activate
    async def test_reuses_dynamic_http_compare_set_and_signals_activity(self):
        first_document = {"tenant": "acme", "user": "Foo"}
        second_document = {"tenant": "acme", "user": "Bar"}
        url = "http://localhost/acme/bad_users.list"
        responses.add(responses.GET, url=url, body="Foo\nBar\n", status=200)

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

        with mock.patch("logprep.util.getter.time.monotonic", side_effect=[100.0, 125.0]):
            await processor.process(LogEvent(first_document, original=b"", input_meta=InputMeta()))
            assert HttpGetter._target_to_data_caches[url].last_called == 100.0

            await processor.process(LogEvent(second_document, original=b"", input_meta=InputMeta()))
            assert HttpGetter._target_to_data_caches[url].last_called == 125.0

        assert len(responses.calls) == 1
        assert first_document["user_results"] == {"in_list": ["bad_users.list"]}
        assert second_document["user_results"] == {"in_list": ["bad_users.list"]}

    @responses.activate
    async def test_dynamic_not_in_list_uses_current_event_compare_set(self):
        first_document = {"tenant": "acme", "user": "Foo"}
        second_document = {"tenant": "beta", "user": "Missing"}
        list_name = "bad_users.list"
        first_url = "http://localhost/acme/bad_users.list"
        second_url = "http://localhost/beta/bad_users.list"
        responses.add(responses.GET, url=first_url, body="Foo\n", status=200)
        responses.add(responses.GET, url=second_url, body="Bar\n", status=200)

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

        await processor.process(LogEvent(first_document, original=b"", input_meta=InputMeta()))
        await processor.process(LogEvent(second_document, original=b"", input_meta=InputMeta()))

        assert first_document["user_results"] == {"in_list": [list_name]}
        assert second_document["user_results"] == {"not_in_list": [list_name]}
        assert _compare_sets(rule, {"tenant": "acme"}) == {list_name: {"Foo"}}
        assert _compare_sets(rule, {"tenant": "beta"}) == {list_name: {"Bar"}}

    @responses.activate
    async def test_dynamic_empty_http_list_is_used_for_not_in_list(self):
        document = {"tenant": "acme", "user": "Foo"}
        list_name = "bad_users.list"
        url = "http://localhost/acme/bad_users.list"
        responses.add(responses.GET, url=url, body="", status=200)

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

        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert document == {
            "tenant": "acme",
            "user": "Foo",
            "user_results": {"not_in_list": [list_name]},
        }
        assert _compare_sets(rule, {"tenant": "acme"}) == {list_name: set()}

    @responses.activate
    async def test_dynamic_http_failure_does_not_mark_rule_failed(self):
        failed_document = {"tenant": "acme", "user": "Foo"}
        successful_document = {"tenant": "beta", "user": "Foo"}
        list_name = "bad_users.list"
        failed_url = "http://localhost/acme/bad_users.list"
        successful_url = "http://localhost/beta/bad_users.list"
        responses.add(responses.GET, url=failed_url, status=500)
        responses.add(responses.GET, url=successful_url, body="Foo\n", status=200)

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
        assert len(HttpGetter._target_to_data_caches[failed_url].callbacks) == 0
        assert len(HttpGetter._target_to_data_caches[failed_url].cleanup_callbacks) == 0

        await processor.process(LogEvent(successful_document, original=b"", input_meta=InputMeta()))

        assert successful_document == {
            "tenant": "beta",
            "user": "Foo",
            "user_results": {"in_list": [list_name]},
        }
        assert rule.data_error is None
        assert _compare_sets(rule, {"tenant": "beta"}) == {list_name: {"Foo"}}

    @responses.activate
    async def test_removes_timed_out_dynamic_compare_set(self):
        document = {"tenant": "acme", "user": "Foo"}
        url = "http://localhost/acme/bad_users.list"
        responses.add(responses.GET, url=url, body="Foo\n", status=200)

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

        with mock.patch("logprep.util.getter.time.monotonic", return_value=100.0):
            await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert url in HttpGetter._target_to_data_caches
        assert len(responses.calls) == 1

        with mock.patch("logprep.util.getter.time.monotonic", return_value=161.1):
            refresh_getters()

        assert url not in HttpGetter._target_to_data_caches

        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))
        assert len(responses.calls) == 2

    @pytest.mark.parametrize(
        "http_list_content, expected_content",
        [
            pytest.param("", set(), id="empty-body"),
            pytest.param("\n", {""}, id="single-empty-line"),
        ],
    )
    @responses.activate
    async def test_static_http_empty_body_or_empty_line_updates_compare_set(
        self, http_list_content, expected_content
    ):
        document = {"user": "Foo"}
        list_name = "bad_users.list"
        url = "http://localhost/tests/testdata/bad_users.list?ref=bla"
        responses.add(responses.GET, url=url, body=http_list_content, status=200)

        processor = await self._create_lister(
            [
                {
                    "filter": "user",
                    "list_comparison": {
                        "source_fields": ["user"],
                        "target_field": "user_results",
                        "list_file_paths": [list_name],
                        "list_search_base_path": (
                            "http://localhost/tests/testdata/${LOGPREP_LIST}?ref=bla"
                        ),
                    },
                }
            ]
        )
        rule = processor.rules[0]

        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert document == {"user": "Foo", "user_results": {"not_in_list": [list_name]}}
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == url
        assert _compare_sets(rule) == {list_name: expected_content}

    @responses.activate
    async def test_process_adds_failure_tag_if_http_list_returns_500(self, caplog):
        document = {"user": "Foo"}
        list_name = "bad_users.list"
        url = "http://localhost/tests/testdata/bad_users.list?ref=bla"
        responses.add(responses.GET, url=url, status=500)

        captured_sessions = []
        original_get_requests_session = HttpGetter._get_requests_session

        def capture_session(self):
            session = original_get_requests_session(self)
            captured_sessions.append(session)
            return session

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
                                "http://localhost/tests/testdata/${LOGPREP_LIST}?ref=bla"
                            ),
                        },
                    }
                ],
            }
        )
        rule = processor.rules[0]
        assert rule.data_error is None

        with mock.patch.object(
            HttpGetter, "_get_requests_session", autospec=True, side_effect=capture_session
        ):
            await processor.setup()

        assert isinstance(rule.data_error, RefreshableGetterError)
        assert captured_sessions

        retries = captured_sessions[0].get_adapter(url).max_retries
        assert retries.total == 3
        assert 500 in retries.status_forcelist

        assert "Caused by ResponseError('too many 500 error responses'))" in caplog.text
        assert "ListComparisonRule failed" in caplog.text

        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert document == {"user": "Foo", "tags": ["_list_comparison_failure"]}
        assert len(responses.calls) == retries.total + 1
        assert responses.calls[0].request.url == url

    @responses.activate
    async def test_recovers_after_failed_http_getter_setup(self):
        list_name = "bad_users.list"
        url = "http://localhost/tests/testdata/bad_users.list?ref=bla"
        rules = [
            {
                "filter": "user",
                "list_comparison": {
                    "source_fields": ["user"],
                    "target_field": "user_results",
                    "list_file_paths": [list_name],
                    "list_search_base_path": (
                        "http://localhost/tests/testdata/${LOGPREP_LIST}?ref=bla"
                    ),
                },
            }
        ]

        responses.add(responses.GET, url=url, status=500)
        processor = await self._create_lister(rules)
        rule = processor.rules[0]

        document = {"user": "Foo"}
        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert isinstance(rule.data_error, RefreshableGetterError)
        assert document == {"user": "Foo", "tags": ["_list_comparison_failure"]}
        assert responses.calls[-1].request.url == url
        assert responses.calls[-1].response.status_code == 500

        responses.replace(responses.GET, url=url, body="Foo\n", status=200)

        processor = await self._create_lister(rules)
        rule = processor.rules[0]

        document = {"user": "Foo"}
        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert rule.data_error is None
        assert document == {"user": "Foo", "user_results": {"in_list": [list_name]}}
        assert _compare_sets(rule) == {list_name: {"Foo"}}
        assert responses.calls[-1].request.url == url
        assert responses.calls[-1].response.status_code == 200

    @responses.activate
    async def test_recovers_after_failed_http_getter_while_processing(self, tmp_path):
        list_name = "bad_users.list"
        url = "http://localhost/tests/testdata/bad_users.list?ref=bla"
        responses.add(responses.GET, url=url, status=500)

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
                                "http://localhost/tests/testdata/${LOGPREP_LIST}?ref=bla"
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
            assert responses.calls[-1].request.url == url
            assert responses.calls[-1].response.status_code == 500

            responses.replace(responses.GET, url=url, body="Foo\n", status=200)

            time.sleep(2)
            refresh_getters()

            assert rule.data_error is None
            assert _compare_sets(rule) == {list_name: {"Foo"}}
            assert responses.calls[-1].request.url == url
            assert responses.calls[-1].response.status_code == 200
