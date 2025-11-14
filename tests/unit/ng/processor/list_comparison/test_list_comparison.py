# pylint: disable=missing-docstring
# pylint: disable=protected-access
import json
from pathlib import Path
from unittest import mock

import pytest
import responses

from logprep.factory import Factory
from logprep.ng.event.log_event import LogEvent
from logprep.processor.base.exceptions import FieldExistsWarning
from logprep.util.defaults import ENV_NAME_LOGPREP_GETTER_CONFIG
from logprep.util.getter import HttpGetter
from tests.unit.ng.processor.base import BaseProcessorTestCase


class TestListComparison(BaseProcessorTestCase):
    CONFIG = {
        "type": "ng_list_comparison",
        "rules": ["tests/testdata/unit/list_comparison/rules"],
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
        "list_search_base_path": "tests/testdata/unit/list_comparison/rules",
    }

    def setup_method(self):
        super().setup_method()
        self.object.setup()

    def test_element_in_list(self):
        document = {"user": "Franz"}
        expected = {"user": "Franz", "user_results": {"in_list": ["user_list.txt"]}}
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        assert log_event.data == expected

    def test_element_not_in_list(self):
        # Test if user Charlotte is not in user list
        document = {"user": "Charlotte"}
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)
        assert len(log_event.data.get("user_results", {}).get("not_in_list")) == 1
        assert log_event.data.get("user_results", {}).get("in_list") is None

    def test_element_in_two_lists(self):
        # Tests if the system name Franz appears in two lists, username Mark is in no list
        document = {"user": "Mark", "system": "Franz"}
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)

        assert len(log_event.data.get("user_results", {}).get("not_in_list")) == 1
        assert log_event.data.get("user_results", {}).get("in_list") is None
        assert len(log_event.data.get("user_and_system_results", {}).get("in_list")) == 2
        assert log_event.data.get("user_and_system_results", {}).get("not_in_list") is None

    def test_element_not_in_two_lists(self):
        # Tests if the system Gamma does not appear in two lists,
        # and username Mark is also not in list
        document = {"user": "Mark", "system": "Gamma"}
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)

        assert len(log_event.data.get("user_and_system_results", {}).get("not_in_list")) == 2
        assert log_event.data.get("user_and_system_results", {}).get("in_list") is None
        assert len(log_event.data.get("user_results", {}).get("not_in_list")) == 1
        assert log_event.data.get("user_results", {}).get("in_list") is None

    def test_two_lists_with_one_matched(self):
        document = {"system": "Alpha", "user": "Charlotte"}
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)

        assert len(log_event.data.get("user_results", {}).get("not_in_list")) != 0
        assert log_event.data.get("user_results", {}).get("in_list") is None
        assert log_event.data.get("user_and_system_results", {}).get("not_in_list") is None
        assert len(log_event.data.get("user_and_system_results", {}).get("in_list")) != 0

    def test_dotted_output_field(self):
        # tests if outputting list_comparison results to dotted fields works
        document = {"dot_channel": "test", "user": "Franz"}
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)

        assert log_event.data.get("dotted", {}).get("user_results", {}).get("not_in_list") is None
        log_event.data = {"dot_channel": "test", "user": "Franz"}

        self.object.process(log_event)

        assert (
            log_event.data.get("more", {})
            .get("than", {})
            .get("dotted", {})
            .get("user_results", {})
            .get("not_in_list")
            is None
        )

    def test_extend_dotted_output_field(self):
        # tests if list_comparison properly extends lists already present in output fields.
        document = {
            "user": "Franz",
            "dotted": {"user_results": {"in_list": ["already_present"]}},
        }
        log_event = LogEvent(document, original=b"")

        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "dotted.user_results",
                "list_file_paths": ["../lists/user_list.txt"],
            },
            "description": "",
        }
        self._load_rule(rule_dict)
        self.object.setup()
        self.object.process(log_event)

        assert log_event.data.get("dotted", {}).get("user_results", {}).get("not_in_list") is None
        assert len(log_event.data.get("dotted", {}).get("user_results", {}).get("in_list")) == 2

    def test_dotted_parent_field_exists_but_subfield_doesnt(self):
        # tests if list_comparison properly extends lists already present in output fields.
        document = {
            "user": "Franz",
            "dotted": {"preexistent_output_field": {"in_list": ["already_present"]}},
        }

        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "dotted.user_results",
                "list_file_paths": ["../lists/user_list.txt"],
            },
            "description": "",
        }
        self._load_rule(rule_dict)
        self.object.setup()
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)

        assert log_event.data.get("dotted", {}).get("user_results", {}).get("not_in_list") is None
        assert len(log_event.data.get("dotted", {}).get("user_results", {}).get("in_list")) == 1
        assert (
            len(log_event.data.get("dotted", {}).get("preexistent_output_field", {}).get("in_list"))
            == 1
        )

    def test_target_field_exists_and_cant_be_extended(self):
        document = {"dot_channel": "test", "user": "Franz", "dotted": "dotted_Franz"}
        expected = {
            "dot_channel": "test",
            "user": "Franz",
            "dotted": "dotted_Franz",
            "tags": ["_list_comparison_failure"],
        }

        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "dotted.user_results",
                "list_file_paths": ["../lists/user_list.txt"],
            },
            "description": "",
        }
        self._load_rule(rule_dict)
        self.object.setup()

        log_event = LogEvent(document, original=b"")
        result = self.object.process(log_event)

        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)
        assert log_event.data == expected

    def test_intermediate_output_field_is_wrong_type(self):
        document = {
            "dot_channel": "test",
            "user": "Franz",
            "dotted": {"user_results": ["do_not_look_here"]},
        }
        expected = {
            "tags": ["_list_comparison_failure"],
            "dot_channel": "test",
            "user": "Franz",
            "dotted": {"user_results": ["do_not_look_here"]},
        }

        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "dotted.user_results.do_not_look_here",
                "list_file_paths": ["../lists/user_list.txt"],
            },
            "description": "",
        }
        self._load_rule(rule_dict)
        self.object.setup()
        log_event = LogEvent(document, original=b"")
        result = self.object.process(log_event)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)
        assert log_event.data == expected

    def test_check_in_dotted_subfield(self):
        document = {"channel": {"type": "fast"}}
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)

        assert len(log_event.data.get("channel_results", {}).get("not_in_list")) == 2
        assert log_event.data.get("channel_results", {}).get("in_list") is None

    def test_ignore_comment_in_list(self):
        # Tests for a comment inside a list, but as a field inside a document to check
        # if the comment is actually ignored
        document = {"user": "# This is a doc string for testing"}
        log_event = LogEvent(document, original=b"")
        self.object.process(log_event)

        assert len(log_event.data.get("user_results", {}).get("not_in_list")) == 1
        assert log_event.data.get("user_results", {}).get("in_list") is None

    def test_delete_source_field(self):
        document = {"user": "Franz"}
        log_event = LogEvent(document, original=b"")

        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": ["../lists/user_list.txt"],
                "delete_source_fields": True,
            },
            "description": "",
        }
        expected = {"user_results": {"in_list": ["user_list.txt"]}}
        self._load_rule(rule_dict)
        self.object.setup()
        self.object.process(log_event)
        assert log_event.data == expected

    def test_overwrite_target_field(self):
        document = {"user": "Franz"}
        log_event = LogEvent(document, original=b"")

        expected = {"user": "Franz", "tags": ["_list_comparison_failure"]}
        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user",
                "list_file_paths": ["../lists/user_list.txt"],
                "overwrite_target": True,
            },
            "description": "",
        }
        self._load_rule(rule_dict)
        self.object.setup()
        result = self.object.process(log_event)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)
        assert document == expected

    @responses.activate
    def test_list_comparison_loads_rule_with_http_template_in_list_search_base_path(self):
        responses.add(
            responses.GET,
            "http://localhost/tests/testdata/bad_users.list?ref=bla",
            """Franz
Heinz
Hans
""",
        )
        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": ["bad_users.list"],
            },
            "description": "",
        }
        config = {
            "type": "list_comparison",
            "rules": [],
            "list_search_base_path": "http://localhost/tests/testdata/${LOGPREP_LIST}?ref=bla",
        }
        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        processor.setup()
        assert processor.rules[0].compare_sets == {"bad_users.list": {"Franz", "Heinz", "Hans"}}

    @responses.activate
    def test_list_comparison_loads_rule_using_http_and_updates_with_callback(self, tmp_path):
        target = "localhost/tests/testdata/bad_users.list?ref=bla"
        url = f"http://{target}"
        responses.add(
            responses.GET,
            url,
            """Franz
Heinz
Hans
""",
        )
        responses.add(
            responses.GET,
            url,
            """Franz
Heinz
""",
        )
        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": ["bad_users.list"],
            },
            "description": "",
        }
        config = {
            "type": "list_comparison",
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
            assert processor.rules[0].compare_sets == {"bad_users.list": {"Franz", "Heinz", "Hans"}}
            assert processor.rules[0].compare_sets == {"bad_users.list": {"Franz", "Heinz", "Hans"}}
            HttpGetter(target=target, protocol="http").scheduler.run_all()
            assert processor.rules[0].compare_sets == {"bad_users.list": {"Franz", "Heinz"}}

    def test_list_comparison_does_not_add_duplicates_from_list_source(self):
        document = {"users": ["Franz", "Alpha"]}
        log_event = LogEvent(document, original=b"")
        expected = {
            "users": ["Franz", "Alpha"],
            "user_results": {
                "in_list": [
                    "system_list.txt",
                    "user_list.txt",
                ]
            },
        }
        rule_dict = {
            "filter": "users",
            "list_comparison": {
                "source_fields": ["users"],
                "target_field": "user_results",
                "list_file_paths": [
                    "../lists/system_list.txt",
                    "../lists/user_list.txt",
                ],
            },
            "description": "",
        }
        self._load_rule(rule_dict)
        self.object.setup()
        self.object.process(log_event)
        assert document == expected

    @pytest.mark.parametrize(
        "testcase, system, result",
        [
            ("string in list", "Alpha", {"in_list": ["system_list.txt"]}),
            ("string not in list", "Omega", {"not_in_list": ["system_list.txt"]}),
            ("list element in list", ["Alpha"], {"in_list": ["system_list.txt"]}),
            ("list element not in list", ["Omega"], {"not_in_list": ["system_list.txt"]}),
            ("one list element in list", ["Alpha", "Omega"], {"in_list": ["system_list.txt"]}),
            ("multiple list elements in list", ["Alpha", "Beta"], {"in_list": ["system_list.txt"]}),
        ],
    )
    def test_match_list_field(self, testcase, system, result):
        document = {"system": system}
        log_event = LogEvent(document, original=b"")
        expected = {"system": system, "system_results": result}
        rule_dict = {
            "filter": "system",
            "list_comparison": {
                "source_fields": ["system"],
                "target_field": "system_results",
                "list_file_paths": ["../lists/system_list.txt"],
            },
            "description": "",
        }
        config = {
            "type": "ng_list_comparison",
            "rules": [],
            "list_search_base_path": self.CONFIG["list_search_base_path"],
        }
        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        processor.setup()
        processor.process(log_event)
        assert document == expected, testcase
