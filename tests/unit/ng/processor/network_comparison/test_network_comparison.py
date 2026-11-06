# pylint: disable=missing-docstring
# pylint: disable=protected-access
import json
import re
from copy import deepcopy
from ipaddress import IPv4Network
from pathlib import Path

import pytest

from logprep.factory_error import InvalidResourcesError
from logprep.ng.abc.event import InputMeta, LogEvent
from logprep.ng.processor.network_comparison.processor import NetworkComparison
from logprep.ng.processor.network_comparison.rule import NetworkComparisonRule
from logprep.processor.base.exceptions import ProcessingWarning
from logprep.util.defaults import ENV_NAME_LOGPREP_GETTER_CONFIG
from logprep.util.getter import HttpGetter, RefreshableGetter
from tests.conftest import Endpoint, Response, mock_env
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.network_comparison.test_network_comparison import (
    failure_test_cases as non_ng_failure_test_cases,
)
from tests.unit.processor.network_comparison.test_network_comparison import (
    invalid_config_cases as non_ng_invalid_config_cases,
)
from tests.unit.processor.network_comparison.test_network_comparison import (
    test_cases as non_ng_test_cases,
)

LOCAL_BASE_PATH = "tests/testdata/unit/network_comparison/rules"

DUMMY_HTTP_LIST = "# a comment\n127.0.0.1\n127.0.0.0/24\n"
"""Body returned for every HTTP list in ``test_cases`` so matches are deterministic."""


async def _compare_sets(rule: NetworkComparisonRule, event: dict | None = None) -> dict[str, set]:
    """Materialize a rule's compare sets via its public ``iter_compare_sets`` API.

    Local and static lists are available with an empty event; dynamic lists
    require the event fields that resolve their target URI.
    """

    return {key: set(value) async for key, value in rule.iter_compare_sets(event or {})}


def _warning_str(warning) -> str:
    return f"{type(warning).__name__}: {warning}"


test_cases = deepcopy(non_ng_test_cases)
failure_test_cases = deepcopy(non_ng_failure_test_cases)
invalid_config_cases = deepcopy(non_ng_invalid_config_cases)


class TestNetworkComparison(BaseProcessorTestCase[NetworkComparison]):
    CONFIG = {
        "type": "network_comparison",
        "rules": ["tests/testdata/unit/network_comparison/rules"],
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
        "list_search_base_path": "tests/testdata/unit/network_comparison/rules",
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

        provision_context(Endpoint(body=DUMMY_HTTP_LIST))

        processor = await self._create_lister([rule])
        log_event = LogEvent(event, original=b"", input_meta=InputMeta())
        await processor.process(log_event)
        assert log_event.data == expected

    @pytest.mark.parametrize("rule, event, expected, error_message", failure_test_cases)
    async def test_testcases_failure_handling(
        self,
        rule,
        event,
        expected,
        error_message,
        provision_context,
    ):
        rule = deepcopy(rule)
        list_search_base_path = rule["network_comparison"].get("list_search_base_path")

        provision_context(Endpoint(status=500))

        processor = await self._create_lister([rule])
        log_event = LogEvent(event, original=b"", input_meta=InputMeta())

        result = await processor.process(log_event)

        assert len(result.warnings) == 1

        assert re.search(error_message, _warning_str(result.warnings[0]))

        assert log_event.data == expected

    @pytest.mark.parametrize("network_comparison_config, error_message", invalid_config_cases)
    async def test_rule_config_is_validated(self, network_comparison_config, error_message):
        rule_dict = {"filter": "ip", "network_comparison": network_comparison_config}
        with pytest.raises(ValueError, match=error_message):
            NetworkComparisonRule.create_from_dict(rule_dict)

    async def test_multiple_rules_write_independent_target_fields(self):
        document = {"ip1": "127.0.0.1", "ip2": "127.0.0.2"}

        await self.object.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert document["ip_results"] == {"in_list": ["ip_only_list.txt"]}
        assert document["ip1_and_ip2_results"] == {
            "in_list": ["ip_only_list.txt", "network_only_list.txt"]
        }

    async def test_multiple_rules_all_not_in_list(self):
        document = {"ip1": "8.8.8.8", "ip2": "9.9.9.9"}

        await self.object.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert document["ip_results"] == {"not_in_list": ["ip_only_list.txt"]}
        assert document["ip1_and_ip2_results"] == {
            "not_in_list": ["ip_only_list.txt", "network_only_list.txt"]
        }

    async def test_rule_level_base_path_takes_precedence_over_processor_base_path(self):
        document = {"ip": "127.0.0.1"}
        processor = await self._create_lister(
            [
                {
                    "filter": "ip",
                    "network_comparison": {
                        "source_fields": ["ip"],
                        "target_field": "network_results",
                        "list_search_base_path": LOCAL_BASE_PATH,
                        "list_file_paths": ["../lists/network_list.txt"],
                    },
                }
            ],
            list_search_base_path="some/nonexistent/base/path",
        )
        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))
        assert document == {
            "ip": "127.0.0.1",
            "network_results": {"in_list": ["network_list.txt"]},
        }

    async def test_local_list_is_converted_to_networks(self):
        processor = await self._create_lister(
            [
                {
                    "filter": "ip",
                    "network_comparison": {
                        "source_fields": ["ip"],
                        "target_field": "network_results",
                        "list_file_paths": ["../lists/network_list.txt"],
                        "list_search_base_path": LOCAL_BASE_PATH,
                    },
                }
            ]
        )
        assert await _compare_sets(processor.rules[0]) == {
            "network_list.txt": {IPv4Network("127.0.0.1/32"), IPv4Network("127.0.0.0/24")}
        }

    async def test_loads_static_http_list_with_template_base_path(self, provision_context):
        base_url = "http://example.dd"
        path = "tests/testdata"
        list_name = "bad_ips.list"
        endpoint = Endpoint(
            url=f"{base_url}/{path}/{list_name}",
            body="127.0.0.1\n127.0.0.2\n127.0.0.3\n",
        )

        provision_context(endpoint)

        processor = await self._create_lister(
            [
                {
                    "filter": "ip",
                    "network_comparison": {
                        "source_fields": ["ip"],
                        "target_field": "ip_results",
                        "list_file_paths": ["bad_ips.list"],
                        "list_search_base_path": (f"{base_url}/{path}/${{LOGPREP_LIST}}"),
                    },
                }
            ]
        )
        assert await _compare_sets(processor.rules[0]) == {
            "bad_ips.list": {
                IPv4Network("127.0.0.1/32"),
                IPv4Network("127.0.0.2/32"),
                IPv4Network("127.0.0.3/32"),
            }
        }

    async def test_static_http_list_is_updated_by_refresh_callback(
        self,
        tmp_path,
        provision_context,
    ):
        base_url = "http://zombo.dd"
        url = f"{base_url}/tests/testdata/bad_ips.list?ref=bla"

        endpoint = Endpoint(
            url=url,
            responses=[
                Response(body="127.0.0.1\n1.1.1.1\n2.2.2.2\n"),
                Response(body="127.0.0.1\n1.1.1.1\n"),
            ],
        )

        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps({url: {"refresh_interval": 10}}))

        with mock_env({ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}):
            processor = await self._create_lister(
                [
                    {
                        "filter": "ip",
                        "network_comparison": {
                            "source_fields": ["ip"],
                            "target_field": "ip_results",
                            "list_file_paths": ["bad_ips.list"],
                            "list_search_base_path": (
                                f"{base_url}/tests/testdata/${{LOGPREP_LIST}}?ref=bla"
                            ),
                        },
                    }
                ]
            )
            rule = processor.rules[0]
            assert await _compare_sets(rule) == {
                "bad_ips.list": {
                    IPv4Network("1.1.1.1/32"),
                    IPv4Network("2.2.2.2/32"),
                    IPv4Network("127.0.0.1/32"),
                }
            }

            HttpGetter(target=url, protocol="http").scheduler.run_all()
            assert await _compare_sets(rule) == {
                "bad_ips.list": {IPv4Network("1.1.1.1/32"), IPv4Network("127.0.0.1/32")}
            }

    async def test_refresh_of_one_list_does_not_affect_unmodified_entries(
        self,
        tmp_path,
        provision_context,
    ):
        request_counts = {
            "bad_ips_1.list": 0,
            "bad_ips_2.list": 0,
        }
        base_url = "http://example.dd"
        url1 = f"{base_url}/tests/testdata/bad_ips_1.list?ref=bla"
        url2 = f"{base_url}/tests/testdata/bad_ips_2.list?ref=bla"
        endpoint1 = Endpoint(
            url=url1,
            responses=[
                Response(body="127.0.0.1"),
                Response(body="1.1.1.1"),
            ],
        )
        endpoint2 = Endpoint(
            url=url2,
            responses=[
                Response(body="2.2.2.2", headers={"ETag": "1"}),
                Response(status=304, headers={"ETag": "1"}),
            ],
        )
        provision_context(endpoint1, endpoint2)

        http_getter_conf = tmp_path / "http_getter.json"
        http_getter_conf.write_text(
            json.dumps({url1: {"refresh_interval": 10}, url2: {"refresh_interval": 10}})
        )

        with mock_env({ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}):
            processor = await self._create_lister(
                [
                    {
                        "filter": "ip",
                        "network_comparison": {
                            "source_fields": ["ip"],
                            "target_field": "ip_results",
                            "list_file_paths": ["bad_ips_1.list", "bad_ips_2.list"],
                            "list_search_base_path": (
                                f"{base_url}/tests/testdata/${{LOGPREP_LIST}}?ref=bla"
                            ),
                        },
                    }
                ]
            )
            rule = processor.rules[0]
            assert (await _compare_sets(rule)) == {
                "bad_ips_1.list": {IPv4Network("127.0.0.1/32")},
                "bad_ips_2.list": {IPv4Network("2.2.2.2/32")},
            }
            assert endpoint1.call_count == 1
            HttpGetter(target=url1, protocol="http").scheduler.run_all()
            assert endpoint1.call_count == 2
            assert (await _compare_sets(rule)) == {
                "bad_ips_1.list": {IPv4Network("1.1.1.1/32")},
                "bad_ips_2.list": {IPv4Network("2.2.2.2/32")},
            }

    async def test_dynamic_http_failure_does_not_mark_rule_failed(
        self,
        provision_context,
    ):
        failed_document = {"tenant": "acme", "ip": "1.2.3.4"}
        successful_document = {"tenant": "beta", "ip": "1.2.3.4"}
        list_name = "bad_ips.list"

        base_url = "http://example.dd"
        failed_url = f"{base_url}/acme/{list_name}"
        successful_url = f"{base_url}/beta/{list_name}"

        provision_context(
            Endpoint(url=failed_url, status=500),
            Endpoint(url=successful_url, body="1.2.3.4\n"),
        )

        dynamic_base_path = f"{base_url}/${{tenant}}/${{LOGPREP_LIST}}"

        processor = await self._create_lister(
            [
                {
                    "filter": "ip",
                    "network_comparison": {
                        "source_fields": ["ip"],
                        "target_field": "ip_results",
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
            "ip": "1.2.3.4",
            "tags": ["_network_comparison_failure"],
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
            "ip": "1.2.3.4",
            "ip_results": {"in_list": [list_name]},
        }
        assert rule.data_error is None
        assert await _compare_sets(rule, {"tenant": "beta"}) == {
            list_name: {IPv4Network("1.2.3.4/32")}
        }
        assert len(HttpGetter._target_to_data_caches[successful_url].callbacks) == 1
        assert len(HttpGetter._target_to_data_caches[successful_url].cleanup_callbacks) == 1

    async def test_process_adds_failure_tag_if_http_list_returns_500(
        self,
        caplog,
        provision_context,
    ):
        document = {"ip": "1.2.3.4"}
        list_name = "bad_ips.list"
        base_url = "http://example.dd"

        url = f"{base_url}/tests/testdata/{list_name}?ref=bla"
        endpoint = Endpoint(url=url, status=500)
        provision_context(endpoint)
        processor = await self._create_lister(
            [
                {
                    "filter": "ip",
                    "network_comparison": {
                        "source_fields": ["ip"],
                        "target_field": "ip_results",
                        "list_file_paths": [list_name],
                        "list_search_base_path": (
                            f"{base_url}/tests/testdata/${{LOGPREP_LIST}}?ref=bla"
                        ),
                    },
                }
            ]
        )
        rule = processor.rules[0]

        assert isinstance(rule.data_error, InvalidResourcesError)
        assert "NetworkComparisonRule failed" in caplog.text
        assert "500" in caplog.text
        assert endpoint.call_count == 4
        assert url in HttpGetter._target_to_data_caches

        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert document == {"ip": "1.2.3.4", "tags": ["_network_comparison_failure"]}
        assert endpoint.call_count == 4

    async def test_recovers_after_failed_http_getter_setup(self, provision_context):
        base_url = "http://example.dd"
        list_name = "bad_ips.list"
        endpoint = Endpoint(
            responses=[
                Response(status=500),
                Response(status=500),
                Response(status=500),
                Response(status=500),
                Response(body="1.2.3.4\n"),
            ]
        )
        provision_context(endpoint)

        rules = [
            {
                "filter": "ip",
                "network_comparison": {
                    "source_fields": ["ip"],
                    "target_field": "ip_results",
                    "list_file_paths": [list_name],
                    "list_search_base_path": (
                        f"{base_url}/tests/testdata/${{LOGPREP_LIST}}?ref=bla"
                    ),
                },
            }
        ]

        processor = await self._create_lister(rules)
        rule = processor.rules[0]

        document = {"ip": "1.2.3.4"}
        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert isinstance(rule.data_error, InvalidResourcesError)
        assert document == {"ip": "1.2.3.4", "tags": ["_network_comparison_failure"]}
        assert endpoint.call_count == 4

        processor = await self._create_lister(rules)
        rule = processor.rules[0]

        document = {"ip": "1.2.3.4"}
        await processor.process(LogEvent(document, original=b"", input_meta=InputMeta()))

        assert rule.data_error is None
        assert document == {"ip": "1.2.3.4", "ip_results": {"in_list": [list_name]}}
        assert await _compare_sets(rule) == {list_name: {IPv4Network("1.2.3.4/32")}}
        assert endpoint.call_count == 5

    async def test_refresh_updates_all_compare_sets_resolving_to_same_uri(
        self,
        tmp_path,
        provision_context,
    ):
        base_url = "http://example.dd"
        url = f"{base_url}/tests/testdata/shared_ips.list?ref=bla"

        endpoint = Endpoint(
            url=url,
            responses=[
                Response(body="127.0.0.1"),
                Response(body="1.1.1.1"),
            ],
        )
        provision_context(endpoint)

        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps({url: {"refresh_interval": 10}}))

        with mock_env({ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}):
            processor = await self._create_lister(
                [
                    {
                        "filter": "ip",
                        "network_comparison": {
                            "source_fields": ["ip"],
                            "target_field": "ip_results",
                            "list_paths": {
                                "FIRST_LIST": "shared_ips.list",
                                "SECOND_LIST": "shared_ips.list",
                            },
                            "list_search_base_path": (
                                f"{base_url}/tests/testdata/${{LOGPREP_LIST}}?ref=bla"
                            ),
                        },
                    }
                ]
            )
            rule = processor.rules[0]

            assert await _compare_sets(rule) == {
                "FIRST_LIST": {IPv4Network("127.0.0.1/32")},
                "SECOND_LIST": {IPv4Network("127.0.0.1/32")},
            }

            assert len(HttpGetter._target_to_data_caches[url].callbacks) == 2

            HttpGetter(target=url, protocol="http").scheduler.run_all()

            assert _compare_sets(rule) == {
                "FIRST_LIST": {IPv4Network("1.1.1.1/32")},
                "SECOND_LIST": {IPv4Network("1.1.1.1/32")},
            }

    async def test_has_async_io(self):
        assert await self.object.has_asyncio() is True
