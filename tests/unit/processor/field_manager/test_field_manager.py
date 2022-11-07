# pylint: disable=missing-docstring
import pytest
from logprep.processor.base.exceptions import ProcessingWarning
from tests.unit.processor.base import BaseProcessorTestCase


test_cases = [  # testcase, rule, event, expected
    (
        "copies single field to non existing target field",
        {
            "filter": "message",
            "source_target": {
                "source_fields": ["message"],
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": "This is a message"},
    ),
    (
        "copies single field to existing target field",
        {
            "filter": "message",
            "source_target": {
                "source_fields": ["message"],
                "target_field": "new_field",
                "overwrite_target": True,
            },
        },
        {"message": "This is a message", "new_field": "existing value"},
        {"message": "This is a message", "new_field": "This is a message"},
    ),
    (
        "moves single field to non existing target field",
        {
            "filter": "message",
            "source_target": {
                "source_fields": ["message"],
                "target_field": "new_field",
                "delete_source_fields": True,
            },
        },
        {"message": "This is a message"},
        {"new_field": "This is a message"},
    ),
    (
        "moves single field to existing target field",
        {
            "filter": "message",
            "source_target": {
                "source_fields": ["message"],
                "target_field": "new_field",
                "delete_source_fields": True,
                "overwrite_target": True,
            },
        },
        {"message": "This is a message", "new_field": "existing content"},
        {"new_field": "This is a message"},
    ),
    (
        "moves field and writes as list to target field",
        {
            "filter": "message",
            "source_target": {
                "source_fields": ["message"],
                "target_field": "new_field",
                "extend_target_list": True,
                "delete_source_fields": True,
            },
        },
        {
            "message": "This is a message",
        },
        {"new_field": ["This is a message"]},
    ),
    (
        "moves multiple fields and writes them as list to non existing target field",
        {
            "filter": "field1 OR field2 OR field3",
            "source_target": {
                "source_fields": ["field1", "field2", "field3"],
                "target_field": "new_field",
                "extend_target_list": True,
                "delete_source_fields": True,
            },
        },
        {
            "field1": "value1",
            "field2": "value2",
            "field3": "value3",
        },
        {"new_field": ["value1", "value2", "value3"]},
    ),
    (
        "moves multiple fields and writes them as list to existing target field",
        {
            "filter": "field1 OR field2 OR field3",
            "source_target": {
                "source_fields": ["field1", "field2", "field3"],
                "target_field": "new_field",
                "extend_target_list": True,
                "delete_source_fields": True,
                "overwrite_target": True,
            },
        },
        {
            "field1": "value1",
            "field2": "value2",
            "field3": "value3",
            "new_field": "i exist",
        },
        {"new_field": ["value1", "value2", "value3"]},
    ),
    (
        "moves multiple fields and writes them to a existing list",
        {
            "filter": "field1 OR field2 OR field3",
            "source_target": {
                "source_fields": ["field1", "field2", "field3"],
                "target_field": "new_field",
                "extend_target_list": True,
                "delete_source_fields": True,
            },
        },
        {
            "field1": "value1",
            "field2": "value2",
            "field3": "value3",
            "new_field": ["i exist"],
        },
        {"new_field": ["i exist", "value1", "value2", "value3"]},
    ),
    (
        "moves multiple fields and merges to target list",
        {
            "filter": "field1 OR field2 OR field3",
            "source_target": {
                "source_fields": ["field1", "field2", "field3"],
                "target_field": "new_field",
                "extend_target_list": True,
                "delete_source_fields": True,
            },
        },
        {
            "field1": ["value1", "value2", "value3"],
            "field2": ["value4"],
            "field3": ["value5", "value6"],
            "new_field": ["i exist"],
        },
        {"new_field": ["i exist", "value1", "value2", "value3", "value4", "value5", "value6"]},
    ),
    (
        "moves multiple fields and merges to target list with different source types",
        {
            "filter": "field1 OR field2 OR field3",
            "source_target": {
                "source_fields": ["field1", "field2", "field3"],
                "target_field": "new_field",
                "extend_target_list": True,
                "delete_source_fields": True,
            },
        },
        {
            "field1": ["value1", "value2", "value3"],
            "field2": "value4",
            "field3": ["value5", "value6"],
            "new_field": ["i exist"],
        },
        {"new_field": ["i exist", "value1", "value2", "value3", "value4", "value5", "value6"]},
    ),
    (
        (
            "moves multiple fields and merges to target list "
            "with different source types and filters duplicates"
        ),
        {
            "filter": "field1 OR field2 OR field3",
            "source_target": {
                "source_fields": ["field1", "field2", "field3"],
                "target_field": "new_field",
                "extend_target_list": True,
                "delete_source_fields": True,
            },
        },
        {
            "field1": ["value1", "value2", "value3", "value5"],
            "field2": "value4",
            "field3": ["value5", "value6", "value4"],
            "new_field": ["i exist"],
        },
        {"new_field": ["i exist", "value1", "value2", "value3", "value4", "value5", "value6"]},
    ),
]

failure_test_cases = []  # testcase, rule, event, expected


class TestFieldManager(BaseProcessorTestCase):

    CONFIG: dict = {
        "type": "field_manager",
        "specific_rules": ["tests/testdata/unit/field_manager/specific_rules"],
        "generic_rules": ["tests/testdata/unit/field_manager/generic_rules"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_testcases(self, testcase, rule, event, expected):  # pylint: disable=unused-argument
        self._load_specific_rule(rule)
        self.object.process(event)
        assert event == expected

    @pytest.mark.parametrize("testcase, rule, event, expected", failure_test_cases)
    def test_testcases_failure_handling(self, testcase, rule, event, expected):
        self._load_specific_rule(rule)
        with pytest.raises(ProcessingWarning):
            self.object.process(event)
        assert event == expected, testcase
