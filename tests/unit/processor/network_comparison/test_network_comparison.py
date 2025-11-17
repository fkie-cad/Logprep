# pylint: disable=missing-docstring
# pylint: disable=protected-access
import json
from ipaddress import IPv4Network
from pathlib import Path
from unittest import mock

import pytest
import responses

from logprep.factory import Factory
from logprep.processor.base.exceptions import FieldExistsWarning
from logprep.util.defaults import ENV_NAME_LOGPREP_GETTER_CONFIG
from logprep.util.getter import HttpGetter
from tests.unit.processor.base import BaseProcessorTestCase


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

    def test_non_ip_element_has_fail_tag(self):
        document = {"ip1": "Franz"}
        self.object.process(document)
        assert document.get("tags") == ["_network_comparison_failure"]

    def test_element_not_in_list(self):
        # Test if ip 1.2.34 is not in ip list
        document = {"ip1": "1.2.3.4"}

        self.object.process(document)

        assert len(document.get("ip_results", {}).get("not_in_list")) == 1
        assert document.get("ip_results", {}).get("in_list") is None

    def test_element_in_two_lists(self):
        # Tests if ip1 127.0.0.1 appears in two lists, ip2 1.1.1.1 is in no list
        document = {"ip1": "1.1.1.1", "ip2": "127.0.0.1"}

        self.object.process(document)

        assert len(document.get("ip_results", {}).get("not_in_list")) == 1
        assert document.get("ip_results", {}).get("in_list") is None
        assert len(document.get("ip1_and_ip2_results", {}).get("in_list")) == 2
        assert document.get("ip1_and_ip2_results", {}).get("not_in_list") is None

    def test_element_not_in_two_lists(self):
        # Tests if the ip1 1.1.1.1 does not appear in two lists,
        # and ip2 2.2.2.2 is also not in list
        document = {"ip1": "1.1.1.1", "ip2": "2.2.2.2"}

        self.object.process(document)

        assert len(document.get("ip1_and_ip2_results", {}).get("not_in_list")) == 2
        assert document.get("ip1_and_ip2_results", {}).get("in_list") is None
        assert len(document.get("ip_results", {}).get("not_in_list")) == 1
        assert document.get("ip_results", {}).get("in_list") is None

    def test_two_lists_with_one_matched(self):
        document = {"ip1": "1.1.1.1", "ip2": "127.0.0.1"}

        self.object.process(document)

        assert len(document.get("ip_results", {}).get("not_in_list")) != 0
        assert document.get("ip_results", {}).get("in_list") is None
        assert document.get("ip1_and_ip2_results", {}).get("not_in_list") is None
        assert len(document.get("ip1_and_ip2_results", {}).get("in_list")) != 0

    def test_dotted_output_field(self):
        # tests if outputting network_comparison results to dotted fields works
        document = {"dot_ip": "127.0.0.2", "ip1": "127.0.0.1"}

        self.object.process(document)

        assert document.get("dotted", {}).get("ip_results", {}).get("not_in_list") is None
        document = {"dot_ip": "127.0.0.2", "ip1": "127.0.0.1"}

        self.object.process(document)

        assert (
            document.get("more", {})
            .get("than", {})
            .get("dotted", {})
            .get("ip_results", {})
            .get("not_in_list")
            is None
        )

    def test_extend_dotted_output_field(self):
        # tests if network_comparison properly extends lists already present in output fields.
        document = {
            "ip1": "127.0.0.1",
            "dotted": {"ip_results": {"in_list": ["already_present"]}},
        }

        rule_dict = {
            "filter": "ip1",
            "network_comparison": {
                "source_fields": ["ip1"],
                "target_field": "dotted.ip_results",
                "list_file_paths": ["../lists/ip_only_list.txt"],
            },
            "description": "",
        }
        self._load_rule(rule_dict)
        self.object.setup()
        self.object.process(document)

        assert document.get("dotted", {}).get("ip_results", {}).get("not_in_list") is None
        assert len(document.get("dotted", {}).get("ip_results", {}).get("in_list")) == 2

    def test_dotted_parent_field_exists_but_subfield_doesnt(self):
        # tests if network_comparison properly extends lists already present in output fields.
        document = {
            "ip1": "127.0.0.1",
            "dotted": {"preexistent_output_field": {"in_list": ["already_present"]}},
        }

        rule_dict = {
            "filter": "ip1",
            "network_comparison": {
                "source_fields": ["ip1"],
                "target_field": "dotted.ip_results",
                "list_file_paths": ["../lists/ip_only_list.txt"],
            },
            "description": "",
        }
        self._load_rule(rule_dict)
        self.object.setup()
        self.object.process(document)

        assert document.get("dotted", {}).get("ip_results", {}).get("not_in_list") is None
        assert len(document.get("dotted", {}).get("ip_results", {}).get("in_list")) == 1
        assert (
            len(document.get("dotted", {}).get("preexistent_output_field", {}).get("in_list")) == 1
        )

    def test_target_field_exists_and_cant_be_extended(self):
        document = {"dot_ip": "127.0.0.2", "ip1": "127.0.0.1", "dotted": "field_exists"}
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
        self._load_rule(rule_dict)
        self.object.setup()
        result = self.object.process(document)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)
        assert document == expected

    def test_intermediate_output_field_is_wrong_type(self):
        document = {
            "dot_ip": "127.0.0.2",
            "ip1": "127.0.0.1",
            "dotted": {"ip_results": ["do_not_look_here"]},
        }
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
        self._load_rule(rule_dict)
        self.object.setup()
        result = self.object.process(document)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)
        assert document == expected

    def test_check_in_dotted_subfield(self):
        document = {"ip": {"field": "1.1.1.1"}}

        self.object.process(document)

        assert len(document.get("ip_results", {}).get("not_in_list")) == 2
        assert document.get("ip_results", {}).get("in_list") is None

    def test_ignore_comment_in_list(self):
        # Tests for a comment inside a list, but as a field inside a document to check
        # if the comment is actually ignored
        document = {"ip1": "# This is a doc string for testing"}

        self.object.process(document)

        assert len(document.get("ip_results", {}).get("not_in_list")) == 1
        assert document.get("ip_results", {}).get("in_list") is None

    def test_delete_source_field(self):
        document = {"ip1": "127.0.0.1"}
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
        self._load_rule(rule_dict)
        self.object.setup()
        self.object.process(document)
        assert document == expected

    def test_overwrite_target_field(self):
        document = {"ip1": "127.0.0.1"}
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
        self._load_rule(rule_dict)
        self.object.setup()
        result = self.object.process(document)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)
        assert document == expected

    @responses.activate
    def test_network_comparison_loads_rule_with_http_template_in_list_search_base_path(self):
        responses.add(
            responses.GET,
            "http://localhost/tests/testdata/bad_ips.list?ref=bla",
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
        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        processor.setup()
        assert processor.rules[0].compare_sets == {
            "bad_ips.list": {
                IPv4Network("127.0.0.1/32"),
                IPv4Network("127.0.0.2/32"),
                IPv4Network("127.0.0.3/32"),
            }
        }

    def test_network_comparison_loads_rule_with_networks(self):
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
        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        processor.setup()
        assert processor.rules[0].compare_sets == {
            "network_list.txt": {IPv4Network("127.0.0.1/32"), IPv4Network("127.0.0.0/24")}
        }

    @responses.activate
    def test_network_comparison_loads_rule_using_http_and_updates_with_callback(self, tmp_path):
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

        getter_file_content = {target: {"refresh_interval": 10}}
        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))
        mock_env = {ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}
        with mock.patch.dict("os.environ", mock_env):
            processor = Factory.create({"custom_lister": config})
            rule = processor.rule_class.create_from_dict(rule_dict)
            processor._rule_tree.add_rule(rule)
            processor.setup()
            assert processor.rules[0].compare_sets == {
                "bad_ips.list": {
                    IPv4Network("1.1.1.1/32"),
                    IPv4Network("2.2.2.2/32"),
                    IPv4Network("127.0.0.1/32"),
                }
            }
            assert processor.rules[0].compare_sets == {
                "bad_ips.list": {
                    IPv4Network("1.1.1.1/32"),
                    IPv4Network("2.2.2.2/32"),
                    IPv4Network("127.0.0.1/32"),
                }
            }
            HttpGetter(target=target, protocol="http").scheduler.run_all()
            assert processor.rules[0].compare_sets == {
                "bad_ips.list": {IPv4Network("1.1.1.1/32"), IPv4Network("127.0.0.1/32")}
            }

    def test_network_comparison_does_not_add_duplicates_from_list_source(self):
        document = {"ip": ["127.0.0.1", "127.0.0.2"]}
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
        self._load_rule(rule_dict)
        self.object.setup()
        self.object.process(document)
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
    def test_match_network_field(self, testcase, ip, result):
        document = {"ip": ip}
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
        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        processor.setup()
        processor.process(document)
        assert document == expected, testcase
