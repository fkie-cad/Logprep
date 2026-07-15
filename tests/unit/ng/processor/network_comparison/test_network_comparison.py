# pylint: disable=missing-docstring
# pylint: disable=protected-access
import json
import typing
from ipaddress import IPv4Network
from unittest import mock

import pytest
import responses

from logprep.factory import Factory
from logprep.ng.abc.event import InputMeta, LogEvent
from logprep.ng.processor.network_comparison.processor import NetworkComparison
from logprep.processor.base.exceptions import FieldExistsWarning, ProcessingWarning
from logprep.util.defaults import ENV_NAME_LOGPREP_GETTER_CONFIG
from logprep.util.getter import HttpGetter, RefreshableGetterError
from tests.unit.ng.processor.base import BaseProcessorTestCase


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

    async def test_non_ip_element_has_fail_tag(self):
        document = {"ip1": "Franz"}
        log_event = LogEvent(document, original=b"", input_meta=InputMeta())
        await self.object.process(log_event)
        assert log_event.data.get("tags") == ["_network_comparison_failure"]

    async def test_network_comparison_uses_rule_level_list_search_base_path_without_processor_base_path(
        self,
    ):
        document = {"ip": "127.0.0.1"}
        log_event = LogEvent(document, original=b"", input_meta=InputMeta())
        expected = {"ip": "127.0.0.1", "network_results": {"in_list": ["network_list.txt"]}}
        rule_dict = {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "network_results",
                "list_search_base_path": self.CONFIG["list_search_base_path"],
                "list_file_paths": ["../lists/network_list.txt"],
            },
            "description": "",
        }
        config = {
            "type": "network_comparison",
            "rules": [],
        }
        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        await processor.setup()
        await processor.process(log_event)

        assert log_event.data == expected

    async def test_element_not_in_list(self):
        # Test if ip 1.2.34 is not in ip list
        document = {"ip1": "1.2.3.4"}
        log_event = LogEvent(document, original=b"", input_meta=InputMeta())

        await self.object.process(log_event)

        assert len(log_event.data.get("ip_results", {}).get("not_in_list")) == 1
        assert log_event.data.get("ip_results", {}).get("in_list") is None

    async def test_element_in_two_lists(self):
        # Tests if ip1 127.0.0.1 appears in two lists, ip2 1.1.1.1 is in no list
        document = {"ip1": "1.1.1.1", "ip2": "127.0.0.1"}
        log_event = LogEvent(document, original=b"", input_meta=InputMeta())

        await self.object.process(log_event)

        assert len(log_event.data.get("ip_results", {}).get("not_in_list")) == 1
        assert log_event.data.get("ip_results", {}).get("in_list") is None
        assert len(log_event.data.get("ip1_and_ip2_results", {}).get("in_list")) == 2
        assert log_event.data.get("ip1_and_ip2_results", {}).get("not_in_list") is None

    async def test_element_not_in_two_lists(self):
        # Tests if the ip1 1.1.1.1 does not appear in two lists,
        # and ip2 2.2.2.2 is also not in list
        document = {"ip1": "1.1.1.1", "ip2": "2.2.2.2"}
        log_event = LogEvent(document, original=b"", input_meta=InputMeta())

        await self.object.process(log_event)

        assert len(document.get("ip1_and_ip2_results", {}).get("not_in_list")) == 2
        assert log_event.data.get("ip1_and_ip2_results", {}).get("in_list") is None
        assert len(log_event.data.get("ip_results", {}).get("not_in_list")) == 1
        assert log_event.data.get("ip_results", {}).get("in_list") is None

    async def test_two_lists_with_one_matched(self):
        document = {"ip1": "1.1.1.1", "ip2": "127.0.0.1"}
        log_event = LogEvent(document, original=b"", input_meta=InputMeta())

        await self.object.process(log_event)

        assert len(document.get("ip_results", {}).get("not_in_list")) != 0
        assert log_event.data.get("ip_results", {}).get("in_list") is None
        assert log_event.data.get("ip1_and_ip2_results", {}).get("not_in_list") is None
        assert len(log_event.data.get("ip1_and_ip2_results", {}).get("in_list")) != 0

    async def test_dotted_output_field(self):
        # tests if outputting network_comparison results to dotted fields works
        document = {"dot_ip": "127.0.0.2", "ip1": "127.0.0.1"}
        log_event = LogEvent(document, original=b"", input_meta=InputMeta())

        await self.object.process(log_event)

        assert log_event.data.get("dotted", {}).get("ip_results", {}).get("not_in_list") is None
        document = {"dot_ip": "127.0.0.2", "ip1": "127.0.0.1"}
        log_event = LogEvent(document, original=b"", input_meta=InputMeta())

        await self.object.process(log_event)

        assert (
            document.get("more", {})
            .get("than", {})
            .get("dotted", {})
            .get("ip_results", {})
            .get("not_in_list")
            is None
        )

    async def test_extend_dotted_output_field(self):
        # tests if network_comparison properly extends lists already present in output fields.
        document = {
            "ip1": "127.0.0.1",
            "dotted": {"ip_results": {"in_list": ["already_present"]}},
        }
        log_event = LogEvent(document, original=b"", input_meta=InputMeta())

        rule_dict = {
            "filter": "ip1",
            "network_comparison": {
                "source_fields": ["ip1"],
                "target_field": "dotted.ip_results",
                "list_file_paths": ["../lists/ip_only_list.txt"],
            },
            "description": "",
        }
        await self._load_rule(rule_dict)
        await self.object.setup()
        await self.object.process(log_event)

        assert log_event.data.get("dotted", {}).get("ip_results", {}).get("not_in_list") is None
        assert len(log_event.data.get("dotted", {}).get("ip_results", {}).get("in_list")) == 2

    async def test_dotted_parent_field_exists_but_subfield_doesnt(self):
        # tests if network_comparison properly extends lists already present in output fields.
        document = {
            "ip1": "127.0.0.1",
            "dotted": {"preexistent_output_field": {"in_list": ["already_present"]}},
        }
        log_event = LogEvent(document, original=b"", input_meta=InputMeta())

        rule_dict = {
            "filter": "ip1",
            "network_comparison": {
                "source_fields": ["ip1"],
                "target_field": "dotted.ip_results",
                "list_file_paths": ["../lists/ip_only_list.txt"],
            },
            "description": "",
        }
        await self._load_rule(rule_dict)
        await self.object.setup()
        await self.object.process(log_event)

        assert document.get("dotted", {}).get("ip_results", {}).get("not_in_list") is None
        assert len(log_event.data.get("dotted", {}).get("ip_results", {}).get("in_list")) == 1
        assert (
            len(log_event.data.get("dotted", {}).get("preexistent_output_field", {}).get("in_list"))
            == 1
        )

    async def test_target_field_exists_and_cant_be_extended(self):
        document = {"dot_ip": "127.0.0.2", "ip1": "127.0.0.1", "dotted": "field_exists"}
        log_event = LogEvent(document, original=b"", input_meta=InputMeta())
        expected = {
            "dot_ip": "127.0.0.2",
            "ip1": "127.0.0.1",
            "dotted": "field_exists",
            "tags": ["_network_comparison_failure"],
        }

        rule_dict = {
            "filter": "ip1",
            "network_comparison": {
                "source_fields": ["ip1"],
                "target_field": "dotted.ip_results",
                "list_file_paths": ["../lists/network_list.txt"],
            },
            "description": "",
        }
        await self._load_rule(rule_dict)
        await self.object.setup()
        result = await self.object.process(log_event)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)
        assert log_event.data == expected

    async def test_intermediate_output_field_is_wrong_type(self):
        document = {
            "dot_ip": "127.0.0.2",
            "ip1": "127.0.0.1",
            "dotted": {"ip_results": ["do_not_look_here"]},
        }
        log_event = LogEvent(document, original=b"", input_meta=InputMeta())
        expected = {
            "tags": ["_network_comparison_failure"],
            "dot_ip": "127.0.0.2",
            "ip1": "127.0.0.1",
            "dotted": {"ip_results": ["do_not_look_here"]},
        }

        rule_dict = {
            "filter": "ip1",
            "network_comparison": {
                "source_fields": ["ip1"],
                "target_field": "dotted.ip_results.do_not_look_here",
                "list_file_paths": ["../lists/network_list.txt"],
            },
            "description": "",
        }
        await self._load_rule(rule_dict)
        await self.object.setup()
        result = await self.object.process(log_event)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)
        assert log_event.data == expected

    async def test_check_in_dotted_subfield(self):
        document = {"ip": {"field": "1.1.1.1"}}
        log_event = LogEvent(document, original=b"", input_meta=InputMeta())

        await self.object.process(log_event)

        assert len(log_event.data.get("ip_results", {}).get("not_in_list")) == 2
        assert log_event.data.get("ip_results", {}).get("in_list") is None

    async def test_ignore_comment_in_list(self):
        # Tests for a comment inside a list, but as a field inside a document to check
        # if the comment is actually ignored
        document = {"ip1": "# This is a doc string for testing"}
        log_event = LogEvent(document, original=b"", input_meta=InputMeta())

        await self.object.process(log_event)

        assert len(log_event.data.get("ip_results", {}).get("not_in_list")) == 1
        assert log_event.data.get("ip_results", {}).get("in_list") is None

    async def test_delete_source_field(self):
        document = {"ip1": "127.0.0.1"}
        log_event = LogEvent(document, original=b"", input_meta=InputMeta())
        rule_dict = {
            "filter": "ip1",
            "network_comparison": {
                "source_fields": ["ip1"],
                "target_field": "ip_results",
                "list_file_paths": ["../lists/ip_only_list.txt"],
                "delete_source_fields": True,
            },
            "description": "",
        }
        expected = {"ip_results": {"in_list": ["ip_only_list.txt"]}}
        await self._load_rule(rule_dict)
        await self.object.setup()
        await self.object.process(log_event)
        assert log_event.data == expected

    async def test_overwrite_target_field(self):
        document = {"ip1": "127.0.0.1"}
        log_event = LogEvent(document, original=b"", input_meta=InputMeta())
        expected = {"ip1": "127.0.0.1", "tags": ["_network_comparison_failure"]}
        rule_dict = {
            "filter": "ip1",
            "network_comparison": {
                "source_fields": ["ip1"],
                "target_field": "ip1",
                "list_file_paths": ["../lists/network_list.txt"],
                "overwrite_target": True,
            },
            "description": "",
        }
        await self._load_rule(rule_dict)
        await self.object.setup()
        result = await self.object.process(log_event)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)
        assert log_event.data == expected

    @responses.activate
    async def test_network_comparison_loads_rule_with_http_template_in_list_search_base_path(self):
        url = "http://localhost/tests/testdata/bad_ips.list?ref=bla"
        responses.add(
            responses.GET,
            url,
            """127.0.0.1
127.0.0.2
127.0.0.3
""",
        )
        rule_dict = {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "uip_results",
                "list_file_paths": ["bad_ips.list"],
            },
            "description": "",
        }
        config = {
            "type": "network_comparison",
            "rules": [],
            "list_search_base_path": "http://localhost/tests/testdata/${LOGPREP_LIST}?ref=bla",
        }
        processor = typing.cast(NetworkComparison, Factory.create({"custom_lister": config}))
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        await processor.setup()
        assert processor.rules[0].compare_sets == {
            url: {
                IPv4Network("127.0.0.1/32"),
                IPv4Network("127.0.0.2/32"),
                IPv4Network("127.0.0.3/32"),
            }
        }

    async def test_network_comparison_loads_rule_with_networks(self):
        rule_dict = {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "network_results",
                "list_file_paths": ["../lists/network_list.txt"],
            },
            "description": "",
        }
        config = {
            "type": "network_comparison",
            "rules": [],
            "list_search_base_path": self.CONFIG["list_search_base_path"],
        }
        processor = typing.cast(NetworkComparison, Factory.create({"custom_lister": config}))
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        await processor.setup()
        assert processor.rules[0].compare_sets == {
            "network_list.txt": {IPv4Network("127.0.0.1/32"), IPv4Network("127.0.0.0/24")}
        }

    @responses.activate
    async def test_network_comparison_loads_rule_using_http_and_updates_with_callback(
        self, tmp_path
    ):
        target = "localhost/tests/testdata/bad_ips.list?ref=bla"
        url = f"http://{target}"
        responses.add(
            responses.GET,
            url,
            """127.0.0.1
1.1.1.1
2.2.2.2
""",
        )
        responses.add(
            responses.GET,
            url,
            """127.0.0.1
1.1.1.1
""",
        )
        rule_dict = {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "ip_results",
                "list_file_paths": ["bad_ips.list"],
            },
            "description": "",
        }
        config = {
            "type": "network_comparison",
            "rules": [],
            "list_search_base_path": "http://localhost/tests/testdata/${LOGPREP_LIST}?ref=bla",
        }

        HttpGetter._shared.clear()

        getter_file_content = {url: {"refresh_interval": 10}}
        http_getter_conf = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))
        mock_env = {ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}
        with mock.patch.dict("os.environ", mock_env):
            processor = typing.cast(NetworkComparison, Factory.create({"custom_lister": config}))
            rule = processor.rule_class.create_from_dict(rule_dict)
            processor._rule_tree.add_rule(rule)
            await processor.setup()
            assert processor.rules[0].compare_sets == {
                url: {
                    IPv4Network("1.1.1.1/32"),
                    IPv4Network("2.2.2.2/32"),
                    IPv4Network("127.0.0.1/32"),
                }
            }
            assert processor.rules[0].compare_sets == {
                url: {
                    IPv4Network("1.1.1.1/32"),
                    IPv4Network("2.2.2.2/32"),
                    IPv4Network("127.0.0.1/32"),
                }
            }
            HttpGetter(target=url, protocol="http").scheduler.run_all()
            assert processor.rules[0].compare_sets == {
                url: {IPv4Network("1.1.1.1/32"), IPv4Network("127.0.0.1/32")}
            }

    async def test_network_comparison_does_not_add_duplicates_from_list_source(self):
        document = {"ip": ["127.0.0.1", "127.0.0.2"]}
        log_event = LogEvent(document, original=b"", input_meta=InputMeta())
        expected = {
            "ip": ["127.0.0.1", "127.0.0.2"],
            "network_results": {
                "in_list": [
                    "network_list.txt",
                    "network_only_list.txt",
                    "ip_only_list.txt",
                ]
            },
        }
        rule_dict = {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "network_results",
                "list_file_paths": [
                    "../lists/network_list.txt",
                    "../lists/network_only_list.txt",
                    "../lists/ip_only_list.txt",
                ],
            },
            "description": "",
        }
        await self._load_rule(rule_dict)
        await self.object.setup()
        await self.object.process(log_event)
        assert document == expected

    @pytest.mark.parametrize(
        "testcase, ip, result",
        [
            ("matching IP", "127.0.0.1", {"in_list": ["network_list.txt"]}),
            ("matching network", "127.0.0.123", {"in_list": ["network_list.txt"]}),
            ("not matching IP", "127.0.123.1", {"not_in_list": ["network_list.txt"]}),
            ("not matching IP list", ["127.0.123.1"], {"not_in_list": ["network_list.txt"]}),
            ("matching IP list", ["127.0.0.1"], {"in_list": ["network_list.txt"]}),
            ("matching network list", ["127.0.0.123"], {"in_list": ["network_list.txt"]}),
            ("not matching network list", ["127.0.123.1"], {"not_in_list": ["network_list.txt"]}),
            ("matching from list", ["127.0.123.1", "127.0.0.1"], {"in_list": ["network_list.txt"]}),
        ],
    )
    async def test_match_network_field(self, testcase, ip, result):
        document = {"ip": ip}
        log_event = LogEvent(document, original=b"", input_meta=InputMeta())
        expected = {"ip": ip, "network_results": result}
        rule_dict = {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "network_results",
                "list_file_paths": ["../lists/network_list.txt"],
            },
            "description": "",
        }
        config = {
            "type": "network_comparison",
            "rules": [],
            "list_search_base_path": self.CONFIG["list_search_base_path"],
        }
        processor = typing.cast(NetworkComparison, Factory.create({"custom_lister": config}))
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        await processor.setup()
        await processor.process(log_event)
        assert document == expected, testcase

    @responses.activate
    async def test_network_comparison_dynamic_http_failure_does_not_mark_rule_failed(self):
        failed_document = {"tenant": "acme", "ip": "1.2.3.4"}
        successful_document = {"tenant": "beta", "ip": "1.2.3.4"}
        failed_log_event = LogEvent(failed_document, original=b"", input_meta=InputMeta())
        successful_log_event = LogEvent(successful_document, original=b"", input_meta=InputMeta())
        url_template = "http://localhost/${tenant}/${LOGPREP_LIST}"
        failed_url = "http://localhost/acme/bad_ips.list"
        successful_url = "http://localhost/beta/bad_ips.list"
        expected_failed_document = {
            "tenant": "acme",
            "ip": "1.2.3.4",
            "tags": ["_network_comparison_failure"],
        }
        expected_successful_document = {
            "tenant": "beta",
            "ip": "1.2.3.4",
            "ip_results": {"in_list": [successful_url]},
        }

        responses.add(responses.GET, url=failed_url, status=500)
        responses.add(responses.GET, url=successful_url, body="1.2.3.4\n", status=200)

        rule_dict = {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "ip_results",
                "list_file_paths": ["bad_ips.list"],
            },
            "description": "",
        }
        config = {
            "type": "network_comparison",
            "rules": [],
            "list_search_base_path": url_template,
        }

        HttpGetter._shared.clear()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        await processor.setup()

        result = await processor.process(failed_log_event)

        assert failed_document == expected_failed_document
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], ProcessingWarning)
        assert rule.data_error is None
        assert failed_url not in rule.compare_sets
        assert len(HttpGetter._shared[failed_url].callbacks) == 0
        assert len(HttpGetter._shared[failed_url].cleanup_callbacks) == 0

        await processor.process(successful_log_event)

        assert successful_document == expected_successful_document
        assert rule.data_error is None
        assert rule.compare_sets == {successful_url: {IPv4Network("1.2.3.4/32")}}

    @responses.activate
    async def test_network_comparison_process_adds_failure_tag_if_http_list_request_returns_500(
        self, caplog
    ):
        document = {"ip": "1.2.3.4"}
        log_event = LogEvent(document, original=b"", input_meta=InputMeta())
        expected = {
            "ip": "1.2.3.4",
            "tags": ["_network_comparison_failure"],
        }
        url = "http://localhost/tests/testdata/bad_ips.list?ref=bla"

        responses.add(
            responses.GET,
            url=url,
            status=500,
        )

        rule_dict = {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "ip_results",
                "list_file_paths": ["bad_ips.list"],
            },
            "description": "",
        }

        config = {
            "type": "network_comparison",
            "rules": [],
            "list_search_base_path": "http://localhost/tests/testdata/${LOGPREP_LIST}?ref=bla",
        }

        HttpGetter._shared.clear()

        processor = typing.cast(NetworkComparison, Factory.create({"custom_lister": config}))
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)

        assert rule.data_error is None

        await processor.setup()

        assert "NetworkComparison" in caplog.text
        assert "too many 500 error responses" in caplog.text

        await processor.process(log_event)

        data_error = rule.data_error
        assert isinstance(data_error, RefreshableGetterError)

        assert document == expected
        assert len(responses.calls) == 4
        assert responses.calls[0].request.url == url
        assert rule.compare_sets == {}

    async def test_network_comparison_logs_warning_on_field_exists_warning(
        self,
    ):
        document = {
            "dot_ip": "127.0.0.2",
            "ip1": "127.0.0.1",
            "dotted": {"ip_results": ["do_not_look_here"]},
        }
        log_event = LogEvent(document, original=b"", input_meta=InputMeta())
        expected = {
            "tags": ["_network_comparison_failure"],
            "dot_ip": "127.0.0.2",
            "ip1": "127.0.0.1",
            "dotted": {"ip_results": ["do_not_look_here"]},
        }

        rule_dict = {
            "filter": "ip1",
            "network_comparison": {
                "source_fields": ["ip1"],
                "target_field": "dotted.ip_results.do_not_look_here",
                "list_file_paths": ["../lists/network_list.txt"],
            },
            "description": "",
        }

        config = {
            "type": "network_comparison",
            "rules": [],
            "list_search_base_path": self.CONFIG["list_search_base_path"],
        }

        processor = typing.cast(NetworkComparison, Factory.create({"custom_lister": config}))
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        await processor.setup()

        result = await processor.process(log_event)

        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)
        assert document == expected

    @responses.activate
    async def test_network_comparison_recovers_after_failed_http_getter_setup(
        self,
    ):
        document = {"ip": "1.2.3.4"}
        log_event = LogEvent(document, original=b"", input_meta=InputMeta())
        expected_failed_document = {
            "ip": "1.2.3.4",
            "tags": ["_network_comparison_failure"],
        }
        list_name = "bad_ips.list"
        url = "http://localhost/tests/testdata/bad_ips.list?ref=bla"

        responses.add(
            responses.GET,
            url=url,
            status=500,
        )

        rule_dict = {
            "filter": "ip",
            "network_comparison": {
                "source_fields": ["ip"],
                "target_field": "ip_results",
                "list_file_paths": [list_name],
            },
            "description": "",
        }

        config = {
            "type": "network_comparison",
            "rules": [],
            "list_search_base_path": "http://localhost/tests/testdata/${LOGPREP_LIST}?ref=bla",
        }

        HttpGetter._shared.clear()

        processor = typing.cast(NetworkComparison, Factory.create({"custom_lister": config}))
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        await processor.setup()
        await processor.process(log_event)

        data_error = rule.data_error
        assert isinstance(data_error, RefreshableGetterError)
        assert document == expected_failed_document
        assert rule.compare_sets == {}
        assert responses.calls[-1].request.url == url
        assert responses.calls[-1].response.status_code == 500

        # recovered case:

        responses.replace(
            responses.GET,
            url=url,
            body="1.2.3.4\n",
            status=200,
        )

        document = {"ip": "1.2.3.4"}
        log_event = LogEvent(document, original=b"", input_meta=InputMeta())
        expected_recovered_document = {
            "ip": "1.2.3.4",
            "ip_results": {"in_list": [url]},
        }

        HttpGetter._shared.clear()

        processor = typing.cast(NetworkComparison, Factory.create({"custom_lister": config}))
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)

        await processor.setup()
        await processor.process(log_event)

        assert rule.data_error is None
        assert document == expected_recovered_document
        assert rule.compare_sets == {url: {IPv4Network("1.2.3.4/32")}}
        assert responses.calls[-1].request.url == url
        assert responses.calls[-1].response.status_code == 200
