# pylint: disable=missing-docstring
# pylint: disable=protected-access

import responses

from logprep.factory import Factory
from logprep.ng.event.log_event import LogEvent
from logprep.processor.base.exceptions import FieldExistsWarning
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
