# pylint: disable=missing-docstring
# pylint: disable=protected-access
import pytest

from logprep.processor.list_comparison.processor import DuplicationError
from tests.unit.processor.base import BaseProcessorTestCase


class TestListComparison(BaseProcessorTestCase):
    CONFIG = {
        "type": "list_comparison",
        "specific_rules": ["tests/testdata/unit/list_comparison/rules/specific"],
        "generic_rules": ["tests/testdata/unit/list_comparison/rules/generic"],
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
        "list_search_base_path": "tests/testdata/unit/list_comparison/rules",
    }

    def test_element_in_list(self):
        document = {"user": "Franz"}
        expected = {"user": "Franz", "user_results": {"in_list": ["user_list.txt"]}}
        self.object.process(document)
        assert document == expected

    def test_element_not_in_list(self):
        # Test if user Charlotte is not in user list
        assert self.object.metrics.number_of_processed_events == 0
        document = {"user": "Charlotte"}

        self.object.process(document)

        assert len(document.get("user_results", {}).get("not_in_list")) == 1
        assert document.get("user_results", {}).get("in_list") is None

    def test_element_in_two_lists(self):
        # Tests if the system name Franz appears in two lists, username Mark is in no list
        assert self.object.metrics.number_of_processed_events == 0
        document = {"user": "Mark", "system": "Franz"}

        self.object.process(document)

        assert len(document.get("user_results", {}).get("not_in_list")) == 1
        assert document.get("user_results", {}).get("in_list") is None
        assert len(document.get("user_and_system_results", {}).get("in_list")) == 2
        assert document.get("user_and_system_results", {}).get("not_in_list") is None

    def test_element_not_in_two_lists(self):
        # Tests if the system Gamma does not appear in two lists,
        # and username Mark is also not in list
        assert self.object.metrics.number_of_processed_events == 0
        document = {"user": "Mark", "system": "Gamma"}

        self.object.process(document)

        assert len(document.get("user_and_system_results", {}).get("not_in_list")) == 2
        assert document.get("user_and_system_results", {}).get("in_list") is None
        assert len(document.get("user_results", {}).get("not_in_list")) == 1
        assert document.get("user_results", {}).get("in_list") is None

    def test_two_lists_with_one_matched(self):
        assert self.object.metrics.number_of_processed_events == 0
        document = {"system": "Alpha", "user": "Charlotte"}

        self.object.process(document)

        assert len(document.get("user_results", {}).get("not_in_list")) != 0
        assert document.get("user_results", {}).get("in_list") is None
        assert document.get("user_and_system_results", {}).get("not_in_list") is None
        assert len(document.get("user_and_system_results", {}).get("in_list")) != 0

    def test_dotted_output_field(self):
        # tests if outputting list_comparison results to dotted fields works
        assert self.object.metrics.number_of_processed_events == 0
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
        assert self.object.metrics.number_of_processed_events == 0
        document = {
            "dot_channel": "test",
            "user": "Franz",
            "dotted": {"user_results": {"in_list": ["already_present"]}},
        }

        self.object.process(document)

        assert document.get("dotted", {}).get("user_results", {}).get("not_in_list") is None
        assert len(document.get("dotted", {}).get("user_results", {}).get("in_list")) == 2

    def test_dotted_parent_field_exists_but_subfield_doesnt(self):
        # tests if list_comparison properly extends lists already present in output fields.
        assert self.object.metrics.number_of_processed_events == 0
        document = {
            "dot_channel": "test",
            "user": "Franz",
            "dotted": {"preexistent_output_field": {"in_list": ["already_present"]}},
        }

        self.object.process(document)

        assert document.get("dotted", {}).get("user_results", {}).get("not_in_list") is None
        assert len(document.get("dotted", {}).get("user_results", {}).get("in_list")) == 1
        assert (
            len(document.get("dotted", {}).get("preexistent_output_field", {}).get("in_list")) == 1
        )

    def test_dotted_wrong_type(self):
        assert self.object.metrics.number_of_processed_events == 0
        document = {"dot_channel": "test", "user": "Franz", "dotted": "dotted_Franz"}

        with pytest.raises(DuplicationError):
            self.object.process(document)

    def test_intermediate_output_field_is_wrong_type(self):
        assert self.object.metrics.number_of_processed_events == 0
        document = {
            "dot_channel": "test",
            "user": "Franz",
            "dotted": {"user_results": ["do_not_look_here"]},
        }

        with pytest.raises(DuplicationError):
            self.object.process(document)

    def test_check_in_dotted_subfield(self):
        assert self.object.metrics.number_of_processed_events == 0
        document = {"channel": {"type": "fast"}}

        self.object.process(document)

        assert len(document.get("channel_results", {}).get("not_in_list")) == 2
        assert document.get("channel_results", {}).get("in_list") is None

    def test_ignore_comment_in_list(self):
        # Tests for a comment inside a list, but as a field inside a document to check
        # if the comment is actually ignored
        assert self.object.metrics.number_of_processed_events == 0
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
        self._load_specific_rule(rule_dict)
        self.object._init_rules_list_comparison()
        self.object.process(document)
        assert document == expected

    def test_overwrite_target_field(self):
        document = {"user": "Franz"}
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
        self._load_specific_rule(rule_dict)
        self.object._init_rules_list_comparison()
        match = (
            r"\('Test Instance Name', 'The following fields could not be written, because one "
            r"or more subfields existed and could not be extended: user.in_list'\)"
        )
        with pytest.raises(DuplicationError, match=match):
            self.object.process(document)
