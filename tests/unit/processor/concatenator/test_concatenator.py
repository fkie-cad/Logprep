# pylint: disable=missing-docstring
# pylint: disable=protected-access
import pytest

from logprep.processor.base.exceptions import DuplicationError
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

    @pytest.mark.parametrize(
        ["test_case", "rule", "document", "expected_output"],
        [
            (
                "process_creates_target_field_with_concatenated_source_fields",
                {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b", "other_field.c"],
                        "target_field": "target_field",
                        "separator": "-",
                        "overwrite_target": False,
                        "delete_source_fields": False,
                    },
                },
                {"field": {"a": "first", "b": "second"}, "other_field": {"c": "third"}},
                {
                    "field": {"a": "first", "b": "second"},
                    "other_field": {"c": "third"},
                    "target_field": "first-second-third",
                },
            ),
            (
                "process_ignores_source_fields_that_do_not_exist",
                {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b", "will.be.ignored"],
                        "target_field": "target_field",
                        "separator": "-",
                        "overwrite_target": False,
                        "delete_source_fields": False,
                    },
                },
                {"field": {"a": "first", "b": "second"}},
                {"field": {"a": "first", "b": "second"}, "target_field": "first-second"},
            ),
            (
                "process_does_overwrite_target_field",
                {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b"],
                        "target_field": "target_field",
                        "separator": "-",
                        "overwrite_target": True,
                        "delete_source_fields": False,
                    },
                },
                {"field": {"a": "first", "b": "second"}, "target_field": "has already content"},
                {"field": {"a": "first", "b": "second"}, "target_field": "first-second"},
            ),
            (
                "process_deletes_source_fields",
                {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b"],
                        "target_field": "target_field",
                        "separator": "-",
                        "overwrite_target": False,
                        "delete_source_fields": True,
                    },
                },
                {"field": {"a": "first", "b": "second", "c": "not third"}, "another": "field"},
                {
                    "field": {"c": "not third"},
                    "another": "field",
                    "target_field": "first-second",
                },
            ),
            (
                "process_deletes_source_fields_and_all_remaining_empty_dicts",
                {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b"],
                        "target_field": "target_field",
                        "separator": "-",
                        "overwrite_target": False,
                        "delete_source_fields": True,
                    },
                },
                {"field": {"a": "first", "b": "second"}, "another": "field"},
                {"another": "field", "target_field": "first-second"},
            ),
            (
                "process_deletes_source_fields_in_small_dict_such_that_only_target_field_remains",
                {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b"],
                        "target_field": "target_field",
                        "separator": "-",
                        "overwrite_target": False,
                        "delete_source_fields": True,
                    },
                },
                {"field": {"a": "first", "b": "second"}},
                {"target_field": "first-second"},
            ),
            (
                "process_overwrites_target_and_deletes_source_fields",
                {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b"],
                        "target_field": "target_field",
                        "separator": "-",
                        "overwrite_target": True,
                        "delete_source_fields": True,
                    },
                },
                {
                    "field": {"a": "first", "b": "second", "c": "another one"},
                    "target_field": "has already content",
                },
                {"field": {"c": "another one"}, "target_field": "first-second"},
            ),
        ],
    )
    def test_for_expected_output(self, test_case, rule, document, expected_output):
        self._load_specific_rule(rule)
        self.object.process(document)
        assert document == expected_output, test_case

    def test_process_raises_duplication_error_if_target_field_exists_and_should_not_be_overwritten(
        self,
    ):
        rule = {
            "filter": "field.a",
            "concatenator": {
                "source_fields": ["field.a", "field.b"],
                "target_field": "target_field",
                "separator": "-",
                "overwrite_target": False,
                "delete_source_fields": False,
            },
        }
        self._load_specific_rule(rule)
        document = {"field": {"a": "first", "b": "second"}, "target_field": "has already content"}
        with pytest.raises(
            DuplicationError,
            match=r"('Test Instance Name', 'The following fields could not be written, "
            r"because one or more subfields existed and could not be extended: target_field')",
        ):
            self.object.process(document)
        assert "target_field" in document
        assert document.get("target_field") == "has already content"
