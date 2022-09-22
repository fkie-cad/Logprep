# pylint: disable=missing-docstring
# pylint: disable=protected-access
import pytest

from logprep.processor.concatenator.processor import DuplicationError
from logprep.processor.concatenator.rule import ConcatenatorRule
from tests.unit.processor.base import BaseProcessorTestCase


class TestConcatenator(BaseProcessorTestCase):
    CONFIG = {
        "type": "concatenator",
        "specific_rules": ["tests/testdata/unit/concatenator/rules/specific"],
        "generic_rules": ["tests/testdata/unit/concatenator/rules/generic"],
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }

    @property
    def generic_rules_dirs(self):
        return self.CONFIG["generic_rules"]

    @property
    def specific_rules_dirs(self):
        return self.CONFIG["specific_rules"]

    def test_process_creates_target_field_with_concatenated_source_fields(self):
        rule = ConcatenatorRule._create_from_dict(
            {
                "filter": "field.a",
                "concatenator": {
                    "source_fields": ["field.a", "field.b", "other_field.c"],
                    "target_field": "target_field",
                    "seperator": "-",
                    "overwrite_target": False,
                    "delete_source_fields": False,
                },
            }
        )
        self.object._specific_tree.add_rule(rule)
        document = {"field": {"a": "first", "b": "second"}, "other_field": {"c": "third"}}
        self.object.process(document)
        assert "target_field" in document
        assert document.get("target_field") == "first-second-third"

    def test_process_ignores_source_fields_that_do_not_exist(self):
        rule = ConcatenatorRule._create_from_dict(
            {
                "filter": "field.a",
                "concatenator": {
                    "source_fields": ["field.a", "field.b", "will.be.ignored"],
                    "target_field": "target_field",
                    "seperator": "-",
                    "overwrite_target": False,
                    "delete_source_fields": False,
                },
            }
        )
        self.object._specific_tree.add_rule(rule)
        document = {"field": {"a": "first", "b": "second"}}
        self.object.process(document)
        assert "target_field" in document
        assert document.get("target_field") == "first-second"

    def test_process_does_not_overwrite_target_field_and_raise_duplication_error(self):
        rule = ConcatenatorRule._create_from_dict(
            {
                "filter": "field.a",
                "concatenator": {
                    "source_fields": ["field.a", "field.b"],
                    "target_field": "target_field",
                    "seperator": "-",
                    "overwrite_target": False,
                    "delete_source_fields": False,
                },
            }
        )
        self.object._specific_tree.add_rule(rule)
        document = {"field": {"a": "first", "b": "second"}, "target_field": "has already content"}
        with pytest.raises(
            DuplicationError,
            match=r"Concatenator \(Test Instance Name\): The following fields could not be "
            r"written, because one or more subfields existed and could not be extended: "
            r"target_field",
        ):
            self.object.process(document)
        assert "target_field" in document
        assert document.get("target_field") == "has already content"

    def test_process_does_overwrite_target_field(self):
        rule = ConcatenatorRule._create_from_dict(
            {
                "filter": "field.a",
                "concatenator": {
                    "source_fields": ["field.a", "field.b"],
                    "target_field": "target_field",
                    "seperator": "-",
                    "overwrite_target": True,
                    "delete_source_fields": False,
                },
            }
        )
        self.object._specific_tree.add_rule(rule)
        document = {"field": {"a": "first", "b": "second"}, "target_field": "has already content"}
        self.object.process(document)
        assert "target_field" in document
        assert document.get("target_field") == "first-second"

    def test_process_deletes_source_fields(self):
        rule = ConcatenatorRule._create_from_dict(
            {
                "filter": "field.a",
                "concatenator": {
                    "source_fields": ["field.a", "field.b"],
                    "target_field": "target_field",
                    "seperator": "-",
                    "overwrite_target": False,
                    "delete_source_fields": True,
                },
            }
        )
        self.object._specific_tree.add_rule(rule)
        document = {"field": {"a": "first", "b": "second", "c": "not third"}, "another": "field"}
        self.object.process(document)
        assert document == {
            "field": {"c": "not third"},
            "another": "field",
            "target_field": "first-second",
        }

    def test_process_deletes_source_fields_and_all_remaining_empty_dicts(self):
        rule = ConcatenatorRule._create_from_dict(
            {
                "filter": "field.a",
                "concatenator": {
                    "source_fields": ["field.a", "field.b"],
                    "target_field": "target_field",
                    "seperator": "-",
                    "overwrite_target": False,
                    "delete_source_fields": True,
                },
            }
        )
        self.object._specific_tree.add_rule(rule)
        document = {"field": {"a": "first", "b": "second"}, "another": "field"}
        self.object.process(document)
        assert document == {"another": "field", "target_field": "first-second"}

    def test_process_deletes_source_fields_in_small_dict_such_that_only_target_field_remains(self):
        rule = ConcatenatorRule._create_from_dict(
            {
                "filter": "field.a",
                "concatenator": {
                    "source_fields": ["field.a", "field.b"],
                    "target_field": "target_field",
                    "seperator": "-",
                    "overwrite_target": False,
                    "delete_source_fields": True,
                },
            }
        )
        self.object._specific_tree.add_rule(rule)
        document = {"field": {"a": "first", "b": "second"}}
        self.object.process(document)
        assert document == {"target_field": "first-second"}

    def test_process_overwrites_target_and_deletes_source_fields(self):
        rule = ConcatenatorRule._create_from_dict(
            {
                "filter": "field.a",
                "concatenator": {
                    "source_fields": ["field.a", "field.b"],
                    "target_field": "target_field",
                    "seperator": "-",
                    "overwrite_target": True,
                    "delete_source_fields": True,
                },
            }
        )
        self.object._specific_tree.add_rule(rule)
        document = {
            "field": {"a": "first", "b": "second", "c": "another one"},
            "target_field": "has already content",
        }
        self.object.process(document)
        assert document == {"field": {"c": "another one"}, "target_field": "first-second"}
