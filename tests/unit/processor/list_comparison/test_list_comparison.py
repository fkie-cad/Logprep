# pylint: disable=missing-docstring
# pylint: disable=protected-access

import responses

from logprep.factory import Factory
from logprep.processor.base.exceptions import FieldExistsWarning
from tests.unit.processor.base import BaseProcessorTestCase


class TestListComparison(BaseProcessorTestCase):
    CONFIG = {
        "type": "list_comparison",
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
        self.object.process(document)
        assert document == expected

    def test_element_not_in_list(self):
        # Test if user Charlotte is not in user list
        document = {"user": "Charlotte"}

        self.object.process(document)

        assert len(document.get("user_results", {}).get("not_in_list")) == 1
        assert document.get("user_results", {}).get("in_list") is None

    def test_element_in_two_lists(self):
        # Tests if the system name Franz appears in two lists, username Mark is in no list
        document = {"user": "Mark", "system": "Franz"}

        self.object.process(document)

        assert len(document.get("user_results", {}).get("not_in_list")) == 1
        assert document.get("user_results", {}).get("in_list") is None
        assert len(document.get("user_and_system_results", {}).get("in_list")) == 2
        assert document.get("user_and_system_results", {}).get("not_in_list") is None

    def test_element_not_in_two_lists(self):
        # Tests if the system Gamma does not appear in two lists,
        # and username Mark is also not in list
        document = {"user": "Mark", "system": "Gamma"}

        self.object.process(document)

        assert len(document.get("user_and_system_results", {}).get("not_in_list")) == 2
        assert document.get("user_and_system_results", {}).get("in_list") is None
        assert len(document.get("user_results", {}).get("not_in_list")) == 1
        assert document.get("user_results", {}).get("in_list") is None

    def test_two_lists_with_one_matched(self):
        document = {"system": "Alpha", "user": "Charlotte"}

        self.object.process(document)

        assert len(document.get("user_results", {}).get("not_in_list")) != 0
        assert document.get("user_results", {}).get("in_list") is None
        assert document.get("user_and_system_results", {}).get("not_in_list") is None
        assert len(document.get("user_and_system_results", {}).get("in_list")) != 0

    def test_dotted_output_field(self):
        # tests if outputting list_comparison results to dotted fields works
        document = {"dot_channel": "test", "user": "Franz"}

        self.object.process(document)

        assert document.get("dotted", {}).get("user_results", {}).get("not_in_list") is None
        document = {"dot_channel": "test", "user": "Franz"}

        self.object.process(document)

        assert (
            document.get("more", {})
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
        self.object.process(document)

        assert document.get("dotted", {}).get("user_results", {}).get("not_in_list") is None
        assert len(document.get("dotted", {}).get("user_results", {}).get("in_list")) == 2

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
        self.object.process(document)

        assert document.get("dotted", {}).get("user_results", {}).get("not_in_list") is None
        assert len(document.get("dotted", {}).get("user_results", {}).get("in_list")) == 1
        assert (
            len(document.get("dotted", {}).get("preexistent_output_field", {}).get("in_list")) == 1
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
        result = self.object.process(document)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)
        assert document == expected

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
        result = self.object.process(document)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)
        assert document == expected

    def test_check_in_dotted_subfield(self):
        document = {"channel": {"type": "fast"}}

        self.object.process(document)

        assert len(document.get("channel_results", {}).get("not_in_list")) == 2
        assert document.get("channel_results", {}).get("in_list") is None

    def test_ignore_comment_in_list(self):
        # Tests for a comment inside a list, but as a field inside a document to check
        # if the comment is actually ignored
        document = {"user": "# This is a doc string for testing"}

        self.object.process(document)

        assert len(document.get("user_results", {}).get("not_in_list")) == 1
        assert document.get("user_results", {}).get("in_list") is None

    def test_delete_source_field(self):
        document = {"user": "Franz"}
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
        self.object.process(document)
        assert document == expected

    def test_overwrite_target_field(self):
        document = {"user": "Franz"}
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
        result = self.object.process(document)
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
        rule = processor.rule_class._create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        processor.setup()
        assert processor.rules[0].compare_sets == {"bad_users.list": {"Franz", "Heinz", "Hans"}}
