# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments

import pytest

from logprep.ng.event.log_event import LogEvent
from logprep.processor.base.exceptions import FieldExistsWarning
from tests.unit.ng.processor.base import BaseProcessorTestCase


class TestConcatenator(BaseProcessorTestCase):
    CONFIG = {
        "type": "ng_concatenator",
        "rules": ["tests/testdata/unit/concatenator/rules"],
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }

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
                        "ignore_missing_fields": True,
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
            (
                "ignore missing fields",
                {
                    "filter": "field.a",
                    "concatenator": {
                        "source_fields": ["field.a", "field.b", "other_field.c"],
                        "target_field": "target_field",
                        "separator": "-",
                        "overwrite_target": False,
                        "delete_source_fields": False,
                        "ignore_missing_fields": True,
                    },
                },
                {"field": {"a": "first"}, "other_field": {"c": "third"}},
                {
                    "field": {"a": "first"},
                    "other_field": {"c": "third"},
                    "target_field": "first-third",
                },
            ),
        ],
    )
    def test_for_expected_output(self, test_case, rule, document, expected_output):
        log_event = LogEvent(document, original=b"test_message")
        self._load_rule(rule)
        self.object.process(log_event)
        assert log_event == LogEvent(expected_output, original=b"test_message"), test_case

    def test_process_handles_field_exists_warning_if_target_field_exists_and_should_not_be_overwritten(
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
        self._load_rule(rule)
        document = LogEvent(
            {"field": {"a": "first", "b": "second"}, "target_field": "has already content"},
            original=b"test_message",
        )
        result = self.object.process(document)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)
        assert "target_field" in document.data
        assert document.data["target_field"] == "has already content"
        assert document.data["tags"] == ["_concatenator_failure"]
