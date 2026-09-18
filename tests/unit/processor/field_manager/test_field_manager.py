# pylint: disable=missing-docstring
# pylint: disable=line-too-long
import logging
import re

import pytest

from logprep.processor.base.exceptions import FieldExistsWarning
from tests.conftest import normalize_test_cases
from tests.unit.processor.base import BaseProcessorTestCase

example_test_cases = [
    pytest.param(
        {
            "filter": "message",
            "field_manager": {
                "source_fields": ["message"],
                "target_field": "new_field",
            },
        },
        {"message": "This is a message"},
        {"message": "This is a message", "new_field": "This is a message"},
        id="copies_single_field_to_non_existing_target_field",
    ),
    pytest.param(
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
        id="copies_single_field_to_existing_target_field",
    ),
    pytest.param(
        {
            "filter": "field1 OR field2 OR field3",
            "field_manager": {
                "source_fields": ["field1", "field2", "field3"],
                "target_field": "new_field",
                "merge_with_target": True,
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
        id="moves_multiple_fields_and_writes_them_to_a_existing_target_field_as_list",
    ),
]

test_cases = normalize_test_cases(
    *example_test_cases,
    # rule, event, expected
    pytest.param(
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
        id="moves_single_field_to_non_existing_target_field",
    ),
    pytest.param(
        {
            "filter": "message",
            "field_manager": {
                "source_fields": ["message"],
                "target_field": "existing",
                "delete_source_fields": True,
                "overwrite_target": True,
            },
        },
        {"message": "This is a message", "existing": "existing"},
        {"existing": "This is a message"},
        id="moves_single_field_to_existing_target_field",
    ),
    pytest.param(
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
        id="moves_single_field_to_existing_target_field",
    ),
    pytest.param(
        {
            "filter": "message",
            "field_manager": {
                "source_fields": ["message"],
                "target_field": "new_field",
                "merge_with_target": True,
                "delete_source_fields": True,
            },
        },
        {"message": "This is a message"},
        {"new_field": ["This is a message"]},
        id="moves_field_and_writes_as_list_to_target_field",
    ),
    pytest.param(
        {
            "filter": "field1 OR field2 OR field3",
            "field_manager": {
                "source_fields": ["field1", "field2", "field3"],
                "target_field": "new_field",
                "merge_with_target": True,
                "delete_source_fields": True,
            },
        },
        {
            "field1": "value1",
            "field2": "value2",
            "field3": "value3",
        },
        {"new_field": ["value1", "value2", "value3"]},
        id="moves_multiple_fields_and_writes_them_as_list_to_non_existing_target_field",
    ),
    pytest.param(
        {
            "filter": "field1 OR field2 OR field3",
            "field_manager": {
                "source_fields": ["field1", "field2", "field3"],
                "target_field": "new_field",
                "merge_with_target": True,
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
        id="moves_multiple_fields_and_writes_them_as_list_to_existing_target_field",
    ),
    pytest.param(
        {
            "filter": "field1 OR field2 OR field3",
            "field_manager": {
                "source_fields": ["field1", "field2", "field3"],
                "target_field": "new_field",
                "merge_with_target": True,
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
        id="moves_multiple_fields_and_replaces_existing_target_field_with_list_including_the_existing_value",
    ),
    pytest.param(
        {
            "filter": "field1 OR field2 OR field3",
            "field_manager": {
                "source_fields": ["field1", "field2", "field3"],
                "target_field": "new_field",
                "merge_with_target": True,
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
        id="moves_multiple_fields_and_writes_them_to_a_existing_list",
    ),
    pytest.param(
        {
            "filter": "field1 OR field2 OR field3",
            "field_manager": {
                "source_fields": ["field1", "field2", "field3"],
                "target_field": "new_field",
                "merge_with_target": True,
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
        id="moves_multiple_fields_and_merges_to_target_list",
    ),
    pytest.param(
        {
            "filter": "field1 OR field2 OR field3",
            "field_manager": {
                "source_fields": ["field1", "field2", "field3"],
                "target_field": "new_field",
                "merge_with_target": True,
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
        id="moves_multiple_fields_and_merges_to_target_list_with_different_source_types",
    ),
    pytest.param(
        {
            "filter": "field1 OR field2 OR field3",
            "field_manager": {
                "source_fields": ["field1", "field2", "field3"],
                "target_field": "new_field",
                "merge_with_target": True,
                "delete_source_fields": True,
            },
        },
        {
            "field1": ["value1", "value2", "value3", "value5"],
            "field2": "value4",
            "field3": ["value5", "value6", "value4"],
            "new_field": ["i exist"],
        },
        {"new_field": ["i exist", "value1", "value2", "value3", "value5", "value4", "value6"]},
        id="moves_multiple_fields_and_merges_to_target_list_with_different_source_types_and_filters_duplicates",
    ),
    pytest.param(
        {
            "filter": "field1 OR field2 OR field3",
            "field_manager": {
                "source_fields": ["field1", "field2", "field3"],
                "target_field": "new_field",
                "merge_with_target": True,
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
        {"new_field": ["value1", "value2", "value3", "value5", "value4", "value6"]},
        id="moves_multiple_fields_and_merges_to_target_list_with_different_source_types_and_filters_duplicates_and_overwrites_target",
    ),
    pytest.param(
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
                "merge_with_target": True,
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
                    "127.0.0.1",
                    "fe89::",
                    "192.168.5.1",
                    "8.8.8.8",
                    "180.22.66.3",
                    "10.10.2.33",
                    "180.22.66.1",
                    "223.2.3.2",
                ]
            },
        },
        id="real_world_example_from_documentation",
    ),
    pytest.param(
        {
            "filter": "field",
            "field_manager": {
                "mapping": {"field.one": "one", "field.two": "two", "field.three": "three"},
            },
        },
        {"field": {"one": 1, "two": 2, "three": 3}},
        {"field": {"one": 1, "two": 2, "three": 3}, "one": 1, "two": 2, "three": 3},
        id="copies_multiple_fields_to_multiple_target_fields",
    ),
    pytest.param(
        {
            "filter": "field",
            "field_manager": {
                "mapping": {"field.one": "one", "field.two": "two", "field.three": "three"},
                "overwrite_target": True,
            },
        },
        {"field": {"one": 1, "two": 2, "three": 3}, "three": "exists already"},
        {"field": {"one": 1, "two": 2, "three": 3}, "one": 1, "two": 2, "three": 3},
        id="copies_multiple_fields_to_multiple_target_fields,_while_overwriting_existing_fields",
    ),
    pytest.param(
        {
            "filter": "field",
            "field_manager": {
                "mapping": {"field.one": "one", "field.two": "two", "field.three": "three"},
                "merge_with_target": True,
            },
        },
        {"field": {"one": 1, "two": 2, "three": 3}, "three": ["exists already"]},
        {
            "field": {"one": 1, "two": 2, "three": 3},
            "one": 1,
            "two": 2,
            "three": ["exists already", 3],
        },
        id="copies_multiple_fields_to_multiple_target_fields,_while_one_list_will_be_extended",
    ),
    pytest.param(
        {
            "filter": "field",
            "field_manager": {
                "mapping": {
                    "field.one": "one",
                    "field.two": "two",
                    "field.three": "three",
                },
                "merge_with_target": True,
            },
        },
        {"field": {"one": 1, "two": 2, "three": [3, 3]}, "three": ["exists already"]},
        {
            "field": {"one": 1, "two": 2, "three": [3, 3]},
            "one": 1,
            "two": 2,
            "three": ["exists already", 3, 3],
        },
        id="copies_multiple_fields_to_multiple_target_fields,_while_one_list_will_be_extended_with_existing_list",
    ),
    pytest.param(
        {
            "filter": "field",
            "field_manager": {
                "mapping": {"field.one": "one", "field.two": "two", "field.three": "three"},
                "overwrite_target": True,
            },
        },
        {"field": {"one": 1, "two": 2, "three": [3, 3]}, "three": ["exists already"]},
        {"field": {"one": 1, "two": 2, "three": [3, 3]}, "one": 1, "two": 2, "three": [3, 3]},
        id="copies_multiple_fields_to_multiple_target_fields,_while_one_target_list_will_be_overwritten_with_existing_list",
    ),
    pytest.param(
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
        id="copies_multiple_fields_to_multiple_target_fields,_while_one_source_field_is_missing",
    ),
    pytest.param(
        {
            "filter": "field",
            "field_manager": {
                "mapping": {"field.one": "one", "field.two": "two", "field.three": "three"},
                "delete_source_fields": True,
            },
        },
        {"field": {"one": 1, "two": 2, "three": 3}},
        {"one": 1, "two": 2, "three": 3},
        id="moves_multiple_fields_to_multiple_target_fields",
    ),
    pytest.param(
        {
            "filter": "field",
            "field_manager": {
                "source_fields": ["source.one", "source.two"],
                "target_field": "merged",
                "mapping": {"field.one": "one", "field.two": "two", "field.three": "three"},
                "merge_with_target": True,
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
        id="Combine_fields_to_list_and_copy_fields_at_the_same_time",
    ),
    pytest.param(
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
        id="Ignore_missing_fields:_No_warning_and_no_failure_tag_if_source_field_is_missing",
    ),
    pytest.param(
        {
            "filter": "(foo) OR (test)",
            "field_manager": {
                "id": "5cfa7a26-94af-49de-bc82-460c42e9dc56",
                "source_fields": ["foo", "test"],
                "target_field": "existing_list",
                "delete_source_fields": False,
                "overwrite_target": False,
                "merge_with_target": True,
            },
        },
        {"existing_list": ["hello", "world"], "foo": "bar", "test": "value"},
        {"existing_list": ["hello", "world", "bar", "value"], "foo": "bar", "test": "value"},
        id="merge_with_target_preserves_list_ordering",
    ),
    pytest.param(
        {
            "filter": "message",
            "field_manager": {
                "source_fields": ["message"],
                "target_field": "new_field",
                "merge_with_target": True,
            },
        },
        {"message": "Value B", "new_field": "Value A"},
        {"message": "Value B", "new_field": ["Value A", "Value B"]},
        id="Convert_existing_target_to_list",
    ),
    pytest.param(
        {
            "filter": "field1 OR field2 OR field3",
            "field_manager": {
                "source_fields": ["field1", "field2", "field3"],
                "target_field": "new_field",
                "merge_with_target": True,
            },
        },
        {
            "field1": "Value B",
            "field2": "Value C",
            "field3": "Value D",
            "new_field": "Value A",
        },
        {
            "field1": "Value B",
            "field2": "Value C",
            "field3": "Value D",
            "new_field": ["Value A", "Value B", "Value C", "Value D"],
        },
        id="Convert_existing_target_to_list_with_multiple_source_fields",
    ),
    pytest.param(
        {
            "filter": "source",
            "field_manager": {
                "source_fields": ["source"],
                "target_field": "target",
                "merge_with_target": True,
            },
        },
        {"source": {"source1": "value"}, "target": {"target1": "value"}},
        {"source": {"source1": "value"}, "target": {"source1": "value", "target1": "value"}},
        id="Merge_source_dict_into_existing_target_dict",
    ),
    pytest.param(
        {
            "filter": "source1",
            "field_manager": {
                "source_fields": ["source1", "source2", "source3"],
                "target_field": "target",
                "delete_source_fields": True,
                "merge_with_target": True,
            },
        },
        {
            "source1": {"source1": "value"},
            "source2": {"source2": "value"},
            "source3": {"source-nested": {"foo": "bar"}},
            "target": {"target1": "value"},
        },
        {
            "target": {
                "source1": "value",
                "source2": "value",
                "source-nested": {"foo": "bar"},
                "target1": "value",
            },
        },
        id="Merge_multiple_source_dicts_into_existing_target_dict",
    ),
    pytest.param(
        {
            "filter": "host",
            "field_manager": {
                "source_fields": ["host"],
                "target_field": "host.name",
                "overwrite_target": True,
            },
        },
        {"host": "example.com"},
        {"host": {"name": "example.com"}},
        id="overlapping_source_with_target_single_processing",
    ),
    pytest.param(
        {
            "filter": "host",
            "field_manager": {
                "mapping": {
                    "host": "host.name",
                },
                "overwrite_target": True,
            },
        },
        {"host": "example.com"},
        {"host": {"name": "example.com"}},
        id="overlapping_source_with_target_mapping_processing",
    ),
    pytest.param(
        {
            "filter": "kubernetes.labels",
            "field_manager": {
                "mapping": {
                    "kubernetes.labels": "orchestrator.resources.labels",
                },
                "overwrite_target": False,
                "delete_source_fields": True,
            },
        },
        {
            "keep": "this unchanged",
            "kubernetes": {
                "labels": {
                    "app.kubernetes.io/name": "vault",
                    "apps.kubernetes.io/pod-index": "2",
                    "controller-revision-hash": "vault-123456789",
                },
                "annotations": {
                    "common/annotation": "true",
                },
            },
        },
        {
            "keep": "this unchanged",
            "kubernetes": {
                "annotations": {
                    "common/annotation": "true",
                }
            },
            "orchestrator": {
                "resources": {
                    "labels": {
                        "app.kubernetes.io/name": "vault",
                        "apps.kubernetes.io/pod-index": "2",
                        "controller-revision-hash": "vault-123456789",
                    }
                }
            },
        },
        id="move_tree",
    ),
)

failure_test_cases = [  # rule, event, expected, error
    pytest.param(
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
        id="single_source_field_not_found",
    ),
    pytest.param(
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
        id="single_source_field_not_found_and_preexisting_tags",
    ),
    pytest.param(
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
        id="single_source_field_not_found_and_preexisting_tags_with_deduplication",
    ),
    pytest.param(
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
        id="copies_multiple_fields_to_multiple_target_fields,_while_one_target_exists_already",
    ),
    pytest.param(
        {
            "filter": "no-mapped-field",
            "field_manager": {
                "mapping": {"field.one": "one", "field.two": "two", "field.three": "three"},
            },
        },
        {"no-mapped-field": "exists"},
        {"no-mapped-field": "exists", "tags": ["_field_manager_missing_field_warning"]},
        ".*ProcessingWarning.*",
        id="tries_to_move_multiple_fields_to_multiple_target_fields_but_none_exists",
    ),
]


class TestFieldManager(BaseProcessorTestCase):
    CONFIG: dict = {
        "type": "field_manager",
        "rules": ["tests/testdata/unit/field_manager/rules"],
    }

    @pytest.mark.parametrize(["rule", "event", "expected", "context"], test_cases)
    def test_testcases(self, rule, event, expected, context, provision_context):
        provision_context(context)
        self._load_rule(rule)
        result = self.object.process(event)
        assert not result.errors
        assert event == expected

    @pytest.mark.parametrize(["rule", "event", "expected", "error_message"], failure_test_cases)
    def test_testcases_failure_handling(self, rule, event, expected, error_message):
        self._load_rule(rule)
        result = self.object.process(event)
        assert len(result.warnings) == 1
        assert re.match(error_message, str(result.warnings[0]))
        assert event == expected

    def test_process_raises_field_exists_warning_if_target_field_exists_and_should_not_be_overwritten(
        self,
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
        self._load_rule(rule)
        document = {"field": {"a": "first", "b": "second"}, "target_field": "has already content"}
        result = self.object.process(document)
        assert isinstance(result.warnings[0], FieldExistsWarning)
        assert "target_field" in document
        assert document.get("target_field") == "has already content"
        assert document.get("tags") == ["_field_manager_failure"]

    def test_process_raises_processing_warning_with_missing_fields(self):
        rule = {
            "filter": "field.a",
            "field_manager": {
                "source_fields": ["does.not.exists"],
                "target_field": "target_field",
            },
        }
        self._load_rule(rule)
        document = {"field": {"a": "first", "b": "second"}}
        result = self.object.process(document)
        assert len(result.warnings) == 1
        assert re.match(
            r".*ProcessingWarning.*missing source_fields: \['does.not.exists'\]",
            str(result.warnings[0]),
        )

    def test_process_raises_processing_warning_with_missing_fields_but_event_is_processed(self):
        rule = {
            "filter": "field.a",
            "field_manager": {
                "mapping": {
                    "field.a": "target_field",
                    "does.not.exists": "target_field",
                }
            },
        }
        self._load_rule(rule)
        document = {"field": {"a": "first", "b": "second"}}
        expected = {
            "field": {"a": "first", "b": "second"},
            "target_field": "first",
            "tags": ["_field_manager_missing_field_warning"],
        }
        result = self.object.process(document)
        assert len(result.warnings) == 1
        assert re.match(
            r".*ProcessingWarning.*missing source_fields: \['does.not.exists'\]",
            str(result.warnings[0]),
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
        self._load_rule(rule)
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
