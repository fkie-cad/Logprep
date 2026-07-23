# pylint: disable=missing-docstring
# pylint: disable=protected-access
import json
import re
from ipaddress import IPv4Network
from pathlib import Path

import pytest
import responses

from logprep.processor.base.exceptions import ProcessingWarning
from logprep.processor.network_comparison.rule import NetworkComparisonRule
from logprep.util.defaults import ENV_NAME_LOGPREP_GETTER_CONFIG
from logprep.util.getter import HttpGetter, RefreshableGetter, RefreshableGetterError
from tests.conftest import mock_env
from tests.unit.processor.base import BaseProcessorTestCase

LOCAL_BASE_PATH = "tests/testdata/unit/network_comparison/rules"

DUMMY_HTTP_LIST = "# a comment\n127.0.0.1\n127.0.0.0/24\n"
"""Body returned for every HTTP list in ``test_cases`` so matches are deterministic."""


def _compare_sets(rule: NetworkComparisonRule, event: dict | None = None) -> dict[str, set]:
    """Materialize a rule's compare sets via its public ``iter_compare_sets`` API.

    Local and static lists are available with an empty event; dynamic lists
    require the event fields that resolve their target URI.
    """
    return dict(rule.iter_compare_sets(event or {}))


def _warning_str(warning) -> str:
    return f"{type(warning).__name__}: {warning}"


test_cases = [  # rule, event, expected
    pytest.param(
        {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "ip_results",
                "list_file_paths": ["../lists/network_list.txt"],
                "list_search_base_path": LOCAL_BASE_PATH,
            },
        },
        {"ip": "127.0.0.1"},
        {"ip": "127.0.0.1", "ip_results": {"in_list": ["network_list.txt"]}},
        id="ip matches an explicit address in the list",
    ),
    pytest.param(
        {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "ip_results",
                "list_file_paths": ["../lists/network_only_list.txt"],
                "list_search_base_path": LOCAL_BASE_PATH,
            },
        },
        {"ip": "127.0.0.55"},
        {"ip": "127.0.0.55", "ip_results": {"in_list": ["network_only_list.txt"]}},
        id="ip is contained in a network of the list",
    ),
    pytest.param(
        {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "ip_results",
                "list_file_paths": ["../lists/network_list.txt"],
                "list_search_base_path": LOCAL_BASE_PATH,
            },
        },
        {"ip": "8.8.8.8"},
        {"ip": "8.8.8.8", "ip_results": {"not_in_list": ["network_list.txt"]}},
        id="ip is in no network of the list",
    ),
    pytest.param(
        {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "ip_results",
                "list_file_paths": ["../lists/empty_list.txt"],
                "list_search_base_path": LOCAL_BASE_PATH,
            },
        },
        {"ip": "127.0.0.1"},
        {"ip": "127.0.0.1", "ip_results": {"not_in_list": ["empty_list.txt"]}},
        id="empty list yields not_in_list",
    ),
    pytest.param(
        {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "ip_results",
                "list_file_paths": [
                    "../lists/ip_only_list.txt",
                    "../lists/network_only_list.txt",
                ],
                "list_search_base_path": LOCAL_BASE_PATH,
            },
        },
        {"ip": "127.0.0.1"},
        {
            "ip": "127.0.0.1",
            "ip_results": {"in_list": ["ip_only_list.txt", "network_only_list.txt"]},
        },
        id="ip matches both of two lists",
    ),
    pytest.param(
        {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "ip_results",
                "list_file_paths": [
                    "../lists/ip_only_list.txt",
                    "../lists/network_only_list.txt",
                ],
                "list_search_base_path": LOCAL_BASE_PATH,
            },
        },
        {"ip": "127.0.0.55"},
        {"ip": "127.0.0.55", "ip_results": {"in_list": ["network_only_list.txt"]}},
        id="ip matches only one of two lists",
    ),
    pytest.param(
        {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "ip_results",
                "list_file_paths": [
                    "../lists/ip_only_list.txt",
                    "../lists/network_only_list.txt",
                ],
                "list_search_base_path": LOCAL_BASE_PATH,
            },
        },
        {"ip": "8.8.8.8"},
        {
            "ip": "8.8.8.8",
            "ip_results": {"not_in_list": ["ip_only_list.txt", "network_only_list.txt"]},
        },
        id="ip matches neither of two lists",
    ),
    pytest.param(
        {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "ip_results",
                "list_file_paths": ["../lists/ip_only_list.txt"],
                "list_search_base_path": LOCAL_BASE_PATH,
            },
        },
        {"ip": ["127.0.0.1", "127.0.0.2"]},
        {"ip": ["127.0.0.1", "127.0.0.2"], "ip_results": {"in_list": ["ip_only_list.txt"]}},
        id="matching list is reported once even with multiple matching values",
    ),
    pytest.param(
        {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip.field"],
                "target_field": "ip_results",
                "list_file_paths": ["../lists/network_list.txt"],
                "list_search_base_path": LOCAL_BASE_PATH,
            },
        },
        {"ip": {"field": "127.0.0.1"}},
        {"ip": {"field": "127.0.0.1"}, "ip_results": {"in_list": ["network_list.txt"]}},
        id="dotted source subfield is resolved",
    ),
    pytest.param(
        {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "dotted.ip_results",
                "list_file_paths": ["../lists/network_list.txt"],
                "list_search_base_path": LOCAL_BASE_PATH,
            },
        },
        {"ip": "127.0.0.1"},
        {"ip": "127.0.0.1", "dotted": {"ip_results": {"in_list": ["network_list.txt"]}}},
        id="dotted target field is created",
    ),
    pytest.param(
        {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "dotted.ip_results",
                "list_file_paths": ["../lists/network_list.txt"],
                "list_search_base_path": LOCAL_BASE_PATH,
            },
        },
        {"ip": "127.0.0.1", "dotted": {"ip_results": {"in_list": ["already_present"]}}},
        {
            "ip": "127.0.0.1",
            "dotted": {"ip_results": {"in_list": ["already_present", "network_list.txt"]}},
        },
        id="existing in_list target field is extended",
    ),
    pytest.param(
        {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "ip_results",
                "list_file_paths": ["../lists/network_list.txt"],
                "list_search_base_path": LOCAL_BASE_PATH,
                "delete_source_fields": True,
            },
        },
        {"ip": "127.0.0.1"},
        {"ip_results": {"in_list": ["network_list.txt"]}},
        id="source field is deleted when configured",
    ),
    pytest.param(
        {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "ip_results",
                "list_paths": {"KNOWN_NETWORKS": "../lists/network_list.txt"},
                "list_search_base_path": LOCAL_BASE_PATH,
            },
        },
        {"ip": "127.0.0.1"},
        {"ip": "127.0.0.1", "ip_results": {"in_list": ["KNOWN_NETWORKS"]}},
        id="list_paths mapping reports the configured name on match",
    ),
    pytest.param(
        {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "ip_results",
                "list_paths": {"KNOWN_NETWORKS": "../lists/network_list.txt"},
                "list_search_base_path": LOCAL_BASE_PATH,
            },
        },
        {"ip": "8.8.8.8"},
        {"ip": "8.8.8.8", "ip_results": {"not_in_list": ["KNOWN_NETWORKS"]}},
        id="list_paths mapping reports the configured name on no match",
    ),
    pytest.param(
        {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "ip_results",
                "list_file_paths": ["networks/blocked"],
                "list_search_base_path": "https://api.example/lists/${LOGPREP_LIST}",
            },
        },
        {"ip": "127.0.0.1"},
        {"ip": "127.0.0.1", "ip_results": {"in_list": ["networks/blocked"]}},
        id="http list, ip found",
    ),
    pytest.param(
        {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "ip_results",
                "list_paths": {"BLOCKED_NETWORKS": "networks/blocked"},
                "list_search_base_path": "https://api.example/lists/${LOGPREP_LIST}",
            },
        },
        {"ip": "8.8.8.8"},
        {"ip": "8.8.8.8", "ip_results": {"not_in_list": ["BLOCKED_NETWORKS"]}},
        id="http list_paths mapping, ip not found",
    ),
    pytest.param(
        {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "ip_results",
                "list_paths": {"BLOCKED_NETWORKS": "blocked"},
                "list_search_base_path": "https://api.example/lists/${tenant}/${LOGPREP_LIST}",
            },
        },
        {"tenant": "acme", "ip": "127.0.0.1"},
        {"tenant": "acme", "ip": "127.0.0.1", "ip_results": {"in_list": ["BLOCKED_NETWORKS"]}},
        id="dynamic http list resolved from event field",
    ),
    pytest.param(
        {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "ip_results",
                "list_file_paths": ["${tenant}/blocked"],
                "list_search_base_path": "https://api.example/lists/${LOGPREP_LIST}",
            },
        },
        {"tenant": "acme", "ip": "127.0.0.1"},
        {"tenant": "acme", "ip": "127.0.0.1", "ip_results": {"in_list": ["${tenant}/blocked"]}},
        id="dynamic variable in list_file_paths resolved from event field",
    ),
    pytest.param(
        {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "ip_results",
                "list_file_paths": ["blocked"],
                "list_search_base_path": "https://api.example/lists/${tenant.id}/${LOGPREP_LIST}",
            },
        },
        {"tenant": {"id": "acme"}, "ip": "127.0.0.1"},
        {
            "tenant": {"id": "acme"},
            "ip": "127.0.0.1",
            "ip_results": {"in_list": ["blocked"]},
        },
        id="dotted event field in list_search_base_path",
    ),
    pytest.param(
        {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "ip_results",
                "list_file_paths": ["${tenant.id}/blocked"],
                "list_search_base_path": "https://api.example/lists/${LOGPREP_LIST}",
            },
        },
        {"tenant": {"id": "acme"}, "ip": "127.0.0.1"},
        {
            "tenant": {"id": "acme"},
            "ip": "127.0.0.1",
            "ip_results": {"in_list": ["${tenant.id}/blocked"]},
        },
        id="dotted event field in list_file_paths",
    ),
    pytest.param(
        {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "ip_results",
                "list_paths": {"BLOCKED_NETWORKS": "${tenant.id}/blocked"},
                "list_search_base_path": "https://api.example/lists/${LOGPREP_LIST}",
            },
        },
        {"tenant": {"id": "acme"}, "ip": "8.8.8.8"},
        {
            "tenant": {"id": "acme"},
            "ip": "8.8.8.8",
            "ip_results": {"not_in_list": ["BLOCKED_NETWORKS"]},
        },
        id="dotted event field in list_paths",
    ),
]


failure_test_cases = [  # rule, event, expected, error_message
    pytest.param(
        {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "ip_results",
                "list_file_paths": ["../lists/network_list.txt"],
                "list_search_base_path": LOCAL_BASE_PATH,
            },
        },
        {"ip": "Franz"},
        {
            "ip": "Franz",
            "tags": ["_network_comparison_failure"],
            "ip_results": {"not_in_list": ["network_list.txt"]},
        },
        r"does not appear to be an IPv4 or IPv6 address",
        id="source value is not an ip address",
    ),
    pytest.param(
        {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "dotted.ip_results.do_not_look_here",
                "list_file_paths": ["../lists/network_list.txt"],
                "list_search_base_path": LOCAL_BASE_PATH,
            },
        },
        {"ip": "127.0.0.1", "dotted": {"ip_results": ["do_not_look_here"]}},
        {
            "ip": "127.0.0.1",
            "dotted": {"ip_results": ["do_not_look_here"]},
            "tags": ["_network_comparison_failure"],
        },
        r"FieldExistsWarning.*could not be extended: dotted.ip_results.do_not_look_here",
        id="intermediate target field has wrong type",
    ),
    pytest.param(
        {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "dotted.ip_results",
                "list_file_paths": ["../lists/network_list.txt"],
                "list_search_base_path": LOCAL_BASE_PATH,
            },
        },
        {"ip": "127.0.0.1", "dotted": "dotted_ip"},
        {
            "ip": "127.0.0.1",
            "dotted": "dotted_ip",
            "tags": ["_network_comparison_failure"],
        },
        r"FieldExistsWarning.*could not be extended: dotted.ip_results",
        id="target parent field exists as string and cannot be extended",
    ),
    pytest.param(
        {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "ip_results",
                "list_file_paths": ["networks/blocked"],
                "list_search_base_path": "https://api.example/lists/${LOGPREP_LIST}",
            },
        },
        {"ip": "127.0.0.1"},
        {"ip": "127.0.0.1", "tags": ["_network_comparison_failure"]},
        r"Max retries exceeded",
        id="http list is unreachable",
    ),
]


invalid_config_cases = [  # network_comparison_config, error_message
    pytest.param(
        {
            "source_fields": ["ip"],
            "target_field": "ip_results",
            "list_file_paths": ["../lists/network_list.txt"],
            "list_paths": {"KNOWN_NETWORKS": "../lists/network_list.txt"},
        },
        r"must not both be specified",
        id="list_file_paths and list_paths are mutually exclusive",
    ),
    pytest.param(
        {
            "source_fields": ["ip"],
            "target_field": "ip_results",
        },
        r"needs to be specified",
        id="one of list_file_paths or list_paths is required",
    ),
]


class TestNetworkComparison(BaseProcessorTestCase):
    CONFIG = {
        "type": "network_comparison",
        "rules": ["tests/testdata/unit/network_comparison/rules"],
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
        "list_search_base_path": "tests/testdata/unit/network_comparison/rules",
    }

    def setup_method(self):
        super().setup_method()
        self.object.setup()

    def _create_lister(self, rules: list[dict], **extra_config):
        RefreshableGetter.reset()
        config = {"type": "network_comparison", "rules": rules, **extra_config}
        processor = self._create_test_instance({"custom_lister": config})
        processor.setup()
        return processor

    @pytest.mark.parametrize("rule, event, expected", test_cases)
    def test_testcases(self, rule, event, expected):
        with responses.RequestsMock(assert_all_requests_are_fired=False) as mocked:
            mocked.add_callback(
                responses.GET,
                re.compile(r"http.*"),
                callback=lambda _: (200, {}, DUMMY_HTTP_LIST),
            )
            processor = self._create_lister([rule])
            processor.process(event)
        assert event == expected

    @pytest.mark.parametrize("rule, event, expected, error_message", failure_test_cases)
    def test_testcases_failure_handling(self, rule, event, expected, error_message):
        with responses.RequestsMock(assert_all_requests_are_fired=False) as mocked:
            mocked.add_callback(
                responses.GET, re.compile(r"http.*"), callback=lambda _: (500, {}, "")
            )
            processor = self._create_lister([rule])
            result = processor.process(event)
        assert len(result.warnings) == 1
        assert re.search(error_message, _warning_str(result.warnings[0]))
        assert event == expected

    @pytest.mark.parametrize("network_comparison_config, error_message", invalid_config_cases)
    def test_rule_config_is_validated(self, network_comparison_config, error_message):
        rule_dict = {"filter": "ip", "network_comparison": network_comparison_config}
        with pytest.raises(ValueError, match=error_message):
            NetworkComparisonRule.create_from_dict(rule_dict)

    def test_multiple_rules_write_independent_target_fields(self):
        document = {"ip1": "127.0.0.1", "ip2": "127.0.0.2"}

        self.object.process(document)

        assert document["ip_results"] == {"in_list": ["ip_only_list.txt"]}
        assert document["ip1_and_ip2_results"] == {
            "in_list": ["ip_only_list.txt", "network_only_list.txt"]
        }

    def test_multiple_rules_all_not_in_list(self):
        document = {"ip1": "8.8.8.8", "ip2": "9.9.9.9"}

        self.object.process(document)

        assert document["ip_results"] == {"not_in_list": ["ip_only_list.txt"]}
        assert document["ip1_and_ip2_results"] == {
            "not_in_list": ["ip_only_list.txt", "network_only_list.txt"]
        }

    def test_rule_level_base_path_takes_precedence_over_processor_base_path(self):
        document = {"ip": "127.0.0.1"}
        processor = self._create_lister(
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
        processor.process(document)
        assert document == {
            "ip": "127.0.0.1",
            "network_results": {"in_list": ["network_list.txt"]},
        }

    def test_local_list_is_converted_to_networks(self):
        processor = self._create_lister(
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
        assert _compare_sets(processor.rules[0]) == {
            "network_list.txt": {IPv4Network("127.0.0.1/32"), IPv4Network("127.0.0.0/24")}
        }

    @responses.activate
    def test_loads_static_http_list_with_template_base_path(self):
        url = "http://localhost/tests/testdata/bad_ips.list?ref=bla"
        responses.add(responses.GET, url, "127.0.0.1\n127.0.0.2\n127.0.0.3\n")
        processor = self._create_lister(
            [
                {
                    "filter": "ip",
                    "network_comparison": {
                        "source_fields": ["ip"],
                        "target_field": "ip_results",
                        "list_file_paths": ["bad_ips.list"],
                        "list_search_base_path": (
                            "http://localhost/tests/testdata/${LOGPREP_LIST}?ref=bla"
                        ),
                    },
                }
            ]
        )
        assert _compare_sets(processor.rules[0]) == {
            "bad_ips.list": {
                IPv4Network("127.0.0.1/32"),
                IPv4Network("127.0.0.2/32"),
                IPv4Network("127.0.0.3/32"),
            }
        }

    @responses.activate
    def test_static_http_list_is_updated_by_refresh_callback(self, tmp_path):
        url = "http://localhost/tests/testdata/bad_ips.list?ref=bla"
        responses.add(responses.GET, url, "127.0.0.1\n1.1.1.1\n2.2.2.2\n")
        responses.add(responses.GET, url, "127.0.0.1\n1.1.1.1\n")

        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps({url: {"refresh_interval": 10}}))

        with mock_env({ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}):
            processor = self._create_lister(
                [
                    {
                        "filter": "ip",
                        "network_comparison": {
                            "source_fields": ["ip"],
                            "target_field": "ip_results",
                            "list_file_paths": ["bad_ips.list"],
                            "list_search_base_path": (
                                "http://localhost/tests/testdata/${LOGPREP_LIST}?ref=bla"
                            ),
                        },
                    }
                ]
            )
            rule = processor.rules[0]
            assert _compare_sets(rule) == {
                "bad_ips.list": {
                    IPv4Network("1.1.1.1/32"),
                    IPv4Network("2.2.2.2/32"),
                    IPv4Network("127.0.0.1/32"),
                }
            }

            HttpGetter(target=url, protocol="http").scheduler.run_all()
            assert _compare_sets(rule) == {
                "bad_ips.list": {IPv4Network("1.1.1.1/32"), IPv4Network("127.0.0.1/32")}
            }

    @responses.activate
    def test_refresh_of_one_list_does_not_affect_unmodified_entries(self, tmp_path):
        url1 = "http://localhost/tests/testdata/bad_ips_1.list?ref=bla"
        responses.add(responses.GET, url1, "127.0.0.1")
        responses.add(responses.GET, url1, "1.1.1.1")

        url2 = "http://localhost/tests/testdata/bad_ips_2.list?ref=bla"
        responses.add(responses.GET, url2, "2.2.2.2", headers={"etag": "1"})
        responses.add(responses.GET, url2, headers={"etag": "1"}, status=304)

        http_getter_conf = tmp_path / "http_getter.json"
        http_getter_conf.write_text(
            json.dumps({url1: {"refresh_interval": 10}, url2: {"refresh_interval": 10}})
        )

        with mock_env({ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}):
            processor = self._create_lister(
                [
                    {
                        "filter": "ip",
                        "network_comparison": {
                            "source_fields": ["ip"],
                            "target_field": "ip_results",
                            "list_file_paths": ["bad_ips_1.list", "bad_ips_2.list"],
                            "list_search_base_path": (
                                "http://localhost/tests/testdata/${LOGPREP_LIST}?ref=bla"
                            ),
                        },
                    }
                ]
            )
            rule = processor.rules[0]
            assert _compare_sets(rule) == {
                "bad_ips_1.list": {IPv4Network("127.0.0.1/32")},
                "bad_ips_2.list": {IPv4Network("2.2.2.2/32")},
            }

            HttpGetter(target=url1, protocol="http").scheduler.run_all()
            assert _compare_sets(rule) == {
                "bad_ips_1.list": {IPv4Network("1.1.1.1/32")},
                "bad_ips_2.list": {IPv4Network("2.2.2.2/32")},
            }

    @responses.activate
    def test_dynamic_http_failure_does_not_mark_rule_failed(self):
        failed_document = {"tenant": "acme", "ip": "1.2.3.4"}
        successful_document = {"tenant": "beta", "ip": "1.2.3.4"}
        list_name = "bad_ips.list"
        failed_url = "http://localhost/acme/bad_ips.list"
        successful_url = "http://localhost/beta/bad_ips.list"
        responses.add(responses.GET, url=failed_url, status=500)
        responses.add(responses.GET, url=successful_url, body="1.2.3.4\n", status=200)

        processor = self._create_lister(
            [
                {
                    "filter": "ip",
                    "network_comparison": {
                        "source_fields": ["ip"],
                        "target_field": "ip_results",
                        "list_file_paths": [list_name],
                        "list_search_base_path": "http://localhost/${tenant}/${LOGPREP_LIST}",
                    },
                }
            ]
        )
        rule = processor.rules[0]

        result = processor.process(failed_document)

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

        processor.process(successful_document)

        assert successful_document == {
            "tenant": "beta",
            "ip": "1.2.3.4",
            "ip_results": {"in_list": [list_name]},
        }
        assert rule.data_error is None
        assert _compare_sets(rule, {"tenant": "beta"}) == {list_name: {IPv4Network("1.2.3.4/32")}}

    @responses.activate
    def test_process_adds_failure_tag_if_http_list_returns_500(self, caplog):
        document = {"ip": "1.2.3.4"}
        list_name = "bad_ips.list"
        url = "http://localhost/tests/testdata/bad_ips.list?ref=bla"
        responses.add(responses.GET, url=url, status=500)

        processor = self._create_lister(
            [
                {
                    "filter": "ip",
                    "network_comparison": {
                        "source_fields": ["ip"],
                        "target_field": "ip_results",
                        "list_file_paths": [list_name],
                        "list_search_base_path": (
                            "http://localhost/tests/testdata/${LOGPREP_LIST}?ref=bla"
                        ),
                    },
                }
            ]
        )
        rule = processor.rules[0]

        assert "NetworkComparison" in caplog.text
        assert "too many 500 error responses" in caplog.text

        processor.process(document)

        assert isinstance(rule.data_error, RefreshableGetterError)
        assert document == {"ip": "1.2.3.4", "tags": ["_network_comparison_failure"]}
        assert len(responses.calls) == 4
        assert responses.calls[0].request.url == url

    @responses.activate
    def test_recovers_after_failed_http_getter_setup(self):
        list_name = "bad_ips.list"
        url = "http://localhost/tests/testdata/bad_ips.list?ref=bla"
        rules = [
            {
                "filter": "ip",
                "network_comparison": {
                    "source_fields": ["ip"],
                    "target_field": "ip_results",
                    "list_file_paths": [list_name],
                    "list_search_base_path": (
                        "http://localhost/tests/testdata/${LOGPREP_LIST}?ref=bla"
                    ),
                },
            }
        ]

        responses.add(responses.GET, url=url, status=500)
        processor = self._create_lister(rules)
        rule = processor.rules[0]

        document = {"ip": "1.2.3.4"}
        processor.process(document)

        assert isinstance(rule.data_error, RefreshableGetterError)
        assert document == {"ip": "1.2.3.4", "tags": ["_network_comparison_failure"]}
        assert responses.calls[-1].request.url == url
        assert responses.calls[-1].response.status_code == 500

        responses.replace(responses.GET, url=url, body="1.2.3.4\n", status=200)

        processor = self._create_lister(rules)
        rule = processor.rules[0]

        document = {"ip": "1.2.3.4"}
        processor.process(document)

        assert rule.data_error is None
        assert document == {"ip": "1.2.3.4", "ip_results": {"in_list": [list_name]}}
        assert _compare_sets(rule) == {list_name: {IPv4Network("1.2.3.4/32")}}
        assert responses.calls[-1].request.url == url
        assert responses.calls[-1].response.status_code == 200

    @responses.activate
    def test_refresh_updates_all_compare_sets_resolving_to_same_uri(self, tmp_path):
        url = "http://localhost/tests/testdata/shared_ips.list?ref=bla"

        responses.add(responses.GET, url, "127.0.0.1")
        responses.add(responses.GET, url, "1.1.1.1")

        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps({url: {"refresh_interval": 10}}))

        with mock_env({ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}):
            processor = self._create_lister(
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
                                "http://localhost/tests/testdata/${LOGPREP_LIST}?ref=bla"
                            ),
                        },
                    }
                ]
            )
            rule = processor.rules[0]

            assert _compare_sets(rule) == {
                "FIRST_LIST": {IPv4Network("127.0.0.1/32")},
                "SECOND_LIST": {IPv4Network("127.0.0.1/32")},
            }

            assert len(HttpGetter._target_to_data_caches[url].callbacks) == 2

            HttpGetter(target=url, protocol="http").scheduler.run_all()

            assert _compare_sets(rule) == {
                "FIRST_LIST": {IPv4Network("1.1.1.1/32")},
                "SECOND_LIST": {IPv4Network("1.1.1.1/32")},
            }
