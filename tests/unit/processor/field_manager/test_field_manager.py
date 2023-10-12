# pylint: disable=missing-docstring
import logging
import re

import pytest

from tests.unit.processor.base import BaseProcessorTestCase

test_cases = [  # testcase, rule, event, expected
    (
        "copies single field to non existing target field",
        {
            "filter": "message",
            "field_manager": {
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
            "field_manager": {
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
            "field_manager": {
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
            "field_manager": {
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
            "field_manager": {
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
            "field_manager": {
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
            "field_manager": {
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
            "field_manager": {
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
        "moves multiple fields and writes them to a existing target field as list",
        {
            "filter": "field1 OR field2 OR field3",
            "field_manager": {
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
            "new_field": "i exist",
        },
        {"new_field": ["i exist", "value1", "value2", "value3"]},
    ),
    (
        "moves multiple fields and merges to target list",
        {
            "filter": "field1 OR field2 OR field3",
            "field_manager": {
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
            "field_manager": {
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
            "moves multiple fields and merges to target list ",
            "with different source types and filters duplicates",
        ),
        {
            "filter": "field1 OR field2 OR field3",
            "field_manager": {
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
    (
        (
            "moves multiple fields and merges to target list ",
            "with different source types and filters duplicates and overwrites target",
        ),
        {
            "filter": "field1 OR field2 OR field3",
            "field_manager": {
                "source_fields": ["field1", "field2", "field3"],
                "target_field": "new_field",
                "extend_target_list": True,
                "delete_source_fields": True,
                "overwrite_target": True,
            },
        },
        {
            "field1": ["value1", "value2", "value3", "value5"],
            "field2": "value4",
            "field3": ["value5", "value6", "value4"],
            "new_field": ["i exist"],
        },
        {"new_field": ["value1", "value2", "value3", "value4", "value5", "value6"]},
    ),
    (
        "real world example from documentation",
        {
            "filter": "client.ip",
            "field_manager": {
                "source_fields": [
                    "client.ip",
                    "destination.ip",
                    "host.ip",
                    "observer.ip",
                    "server.ip",
                    "source.ip",
                    "server.nat.ip",
                    "client.nat.ip",
                ],
                "target_field": "related.ip",
                "extend_target_list": True,
            },
        },
        {
            "client": {"ip": ["127.0.0.1", "fe89::", "192.168.5.1"], "nat": {"ip": "223.2.3.2"}},
            "destination": {"ip": "8.8.8.8"},
            "host": {"ip": ["192.168.5.1", "180.22.66.3"]},
            "observer": {"ip": "10.10.2.33"},
            "server": {"ip": "10.10.2.33", "nat": {"ip": "180.22.66.1"}},
            "source": {"ip": "10.10.2.33"},
        },
        {
            "client": {"ip": ["127.0.0.1", "fe89::", "192.168.5.1"], "nat": {"ip": "223.2.3.2"}},
            "destination": {"ip": "8.8.8.8"},
            "host": {"ip": ["192.168.5.1", "180.22.66.3"]},
            "observer": {"ip": "10.10.2.33"},
            "server": {"ip": "10.10.2.33", "nat": {"ip": "180.22.66.1"}},
            "source": {"ip": "10.10.2.33"},
            "related": {
                "ip": [
                    "10.10.2.33",
                    "127.0.0.1",
                    "180.22.66.1",
                    "180.22.66.3",
                    "192.168.5.1",
                    "223.2.3.2",
                    "8.8.8.8",
                    "fe89::",
                ]
            },
        },
    ),
    (
        "copies multiple fields to multiple target fields",
        {
            "filter": "field",
            "field_manager": {
                "mapping": {"field.one": "one", "field.two": "two", "field.three": "three"},
            },
        },
        {"field": {"one": 1, "two": 2, "three": 3}},
        {"field": {"one": 1, "two": 2, "three": 3}, "one": 1, "two": 2, "three": 3},
    ),
    (
        "copies multiple fields to multiple target fields, while overwriting existing fields",
        {
            "filter": "field",
            "field_manager": {
                "mapping": {"field.one": "one", "field.two": "two", "field.three": "three"},
                "overwrite_target": True,
            },
        },
        {"field": {"one": 1, "two": 2, "three": 3}, "three": "exists already"},
        {"field": {"one": 1, "two": 2, "three": 3}, "one": 1, "two": 2, "three": 3},
    ),
    (
        "copies multiple fields to multiple target fields, while one list will be extended",
        {
            "filter": "field",
            "field_manager": {
                "mapping": {"field.one": "one", "field.two": "two", "field.three": "three"},
                "extend_target_list": True,
            },
        },
        {"field": {"one": 1, "two": 2, "three": 3}, "three": ["exists already"]},
        {
            "field": {"one": 1, "two": 2, "three": 3},
            "one": 1,
            "two": 2,
            "three": ["exists already", 3],
        },
    ),
    (
        "copies multiple fields to multiple target fields, while one list will be extended with existing list",
        {
            "filter": "field",
            "field_manager": {
                "mapping": {"field.one": "one", "field.two": "two", "field.three": "three"},
                "extend_target_list": True,
            },
        },
        {"field": {"one": 1, "two": 2, "three": [3, 3]}, "three": ["exists already"]},
        {
            "field": {"one": 1, "two": 2, "three": [3, 3]},
            "one": 1,
            "two": 2,
            "three": ["exists already", 3, 3],
        },
    ),
    (
        "copies multiple fields to multiple target fields, while one target list will be overwritten with existing list",
        {
            "filter": "field",
            "field_manager": {
                "mapping": {"field.one": "one", "field.two": "two", "field.three": "three"},
                "overwrite_target": True,
            },
        },
        {"field": {"one": 1, "two": 2, "three": [3, 3]}, "three": ["exists already"]},
        {"field": {"one": 1, "two": 2, "three": [3, 3]}, "one": 1, "two": 2, "three": [3, 3]},
    ),
    (
        "copies multiple fields to multiple target fields, while one source field is missing",
        {
            "filter": "field",
            "field_manager": {
                "mapping": {"field.one": "one", "field.two": "two", "field.three": "three"},
            },
        },
        {
            "field": {"one": 1, "three": 3},
        },
        {
            "field": {"one": 1, "three": 3},
            "one": 1,
            "three": 3,
            "tags": ["_field_manager_missing_field_warning"],
        },
    ),
    (
        "moves multiple fields to multiple target fields",
        {
            "filter": "field",
            "field_manager": {
                "mapping": {"field.one": "one", "field.two": "two", "field.three": "three"},
                "delete_source_fields": True,
            },
        },
        {"field": {"one": 1, "two": 2, "three": 3}},
        {"one": 1, "two": 2, "three": 3},
    ),
    (
        "Combine fields to list and copy fields at the same time",
        {
            "filter": "field",
            "field_manager": {
                "source_fields": ["source.one", "source.two"],
                "target_field": "merged",
                "mapping": {"field.one": "one", "field.two": "two", "field.three": "three"},
                "extend_target_list": True,
            },
        },
        {"field": {"one": 1, "two": 2, "three": 3}, "source": {"one": ["a"], "two": ["b"]}},
        {
            "field": {"one": 1, "two": 2, "three": 3},
            "source": {"one": ["a"], "two": ["b"]},
            "one": 1,
            "two": 2,
            "three": 3,
            "merged": ["a", "b"],
        },
    ),
    (
        "Ignore missing fields: No warning and no failure tag if source field is missing",
        {
            "filter": "field.a",
            "field_manager": {
                "mapping": {
                    "field.a": "target_field",
                    "does.not.exists": "target_field",
                },
                "ignore_missing_fields": True,
            },
        },
        {"field": {"a": "first", "b": "second"}},
        {
            "field": {"a": "first", "b": "second"},
            "target_field": "first",
        },
    ),
]

failure_test_cases = [
    (
        "single source field not found",
        {
            "filter": "message",
            "field_manager": {
                "source_fields": ["do.not.exits"],
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "tags": ["_field_manager_missing_field_warning"]},
        ".*ProcessingWarning.*",
    ),
    (
        "single source field not found and preexisting tags",
        {
            "filter": "message",
            "field_manager": {
                "source_fields": ["do.not.exits"],
                "target_field": "new_field",
            },
        },
        {"message": "This is a message", "tags": ["preexisting"]},
        {
            "message": "This is a message",
            "tags": ["_field_manager_missing_field_warning", "preexisting"],
        },
        ".*ProcessingWarning.*",
    ),
    (
        "single source field not found and preexisting tags with deduplication",
        {
            "filter": "message",
            "field_manager": {
                "source_fields": ["do.not.exits"],
                "target_field": "new_field",
            },
        },
        {
            "message": "This is a message",
            "tags": ["_field_manager_missing_field_warning", "preexisting"],
        },
        {
            "message": "This is a message",
            "tags": ["_field_manager_missing_field_warning", "preexisting"],
        },
        ".*ProcessingWarning.*",
    ),
    (
        "copies multiple fields to multiple target fields, while one target exists already",
        {
            "filter": "field",
            "field_manager": {
                "mapping": {"field.one": "one", "field.two": "two", "field.three": "three"},
            },
        },
        {"field": {"one": 1, "two": 2, "three": 3}, "three": "exists"},
        {
            "field": {"one": 1, "two": 2, "three": 3},
            "one": 1,
            "two": 2,
            "three": "exists",
            "tags": ["_field_manager_failure"],
        },
        ".*FieldExistsWarning.*",
    ),
    (
        "tries to move multiple fields to multiple target fields but none exists",
        {
            "filter": "no-mapped-field",
            "field_manager": {
                "mapping": {"field.one": "one", "field.two": "two", "field.three": "three"},
            },
        },
        {"no-mapped-field": "exists"},
        {"no-mapped-field": "exists", "tags": ["_field_manager_missing_field_warning"]},
        ".*ProcessingWarning.*",
    ),
]  # testcase, rule, event, expected, error


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

    @pytest.mark.parametrize("testcase, rule, event, expected, error", failure_test_cases)
    def test_testcases_failure_handling(self, testcase, rule, event, expected, error, caplog):
        self._load_specific_rule(rule)
        with caplog.at_level(logging.WARNING):
            self.object.process(event)
        assert re.match(error, caplog.text)
        assert event == expected, testcase

    def test_process_raises_duplication_error_if_target_field_exists_and_should_not_be_overwritten(
        self, caplog
    ):
        rule = {
            "filter": "field.a",
            "field_manager": {
                "source_fields": ["field.a", "field.b"],
                "target_field": "target_field",
                "overwrite_target": False,
                "delete_source_fields": False,
            },
        }
        self._load_specific_rule(rule)
        document = {"field": {"a": "first", "b": "second"}, "target_field": "has already content"}
        with caplog.at_level(logging.WARNING):
            self.object.process(document)
        assert re.match(".*FieldExistsWarning.*", caplog.text)
        assert "target_field" in document
        assert document.get("target_field") == "has already content"
        assert document.get("tags") == ["_field_manager_failure"]

    def test_process_raises_processing_warning_with_missing_fields(self, caplog):
        rule = {
            "filter": "field.a",
            "field_manager": {
                "source_fields": ["does.not.exists"],
                "target_field": "target_field",
            },
        }
        self._load_specific_rule(rule)
        document = {"field": {"a": "first", "b": "second"}}
        with caplog.at_level(logging.WARNING):
            self.object.process(document)
        assert re.match(
            r".*ProcessingWarning.*missing source_fields: \['does.not.exists'\]", caplog.text
        )

    def test_process_raises_processing_warning_with_missing_fields_but_event_is_processed(
        self, caplog
    ):
        rule = {
            "filter": "field.a",
            "field_manager": {
                "mapping": {
                    "field.a": "target_field",
                    "does.not.exists": "target_field",
                }
            },
        }
        self._load_specific_rule(rule)
        document = {"field": {"a": "first", "b": "second"}}
        expected = {
            "field": {"a": "first", "b": "second"},
            "target_field": "first",
            "tags": ["_field_manager_missing_field_warning"],
        }
        with caplog.at_level(logging.WARNING):
            self.object.process(document)
        assert re.match(
            r".*ProcessingWarning.*missing source_fields: \['does.not.exists'\]", caplog.text
        )
        assert document == expected

    def test_process_dos_not_raises_processing_warning_with_missing_fields_and_event_is_processed(
        self, caplog
    ):
        rule = {
            "filter": "field.a",
            "field_manager": {
                "mapping": {
                    "field.a": "target_field",
                    "does.not.exists": "target_field",
                },
                "ignore_missing_fields": True,
            },
        }
        self._load_specific_rule(rule)
        document = {"field": {"a": "first", "b": "second"}}
        expected = {
            "field": {"a": "first", "b": "second"},
            "target_field": "first",
        }
        with caplog.at_level(logging.WARNING):
            self.object.process(document)
        assert not re.match(
            r".*ProcessingWarning.*missing source_fields: \['does.not.exists'\]", caplog.text
        )
        assert document == expected
