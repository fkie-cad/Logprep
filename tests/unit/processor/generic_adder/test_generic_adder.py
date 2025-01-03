# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=unused-argument
# pylint: disable=too-many-arguments
import re
from copy import deepcopy

import pytest

from logprep.factory import Factory
from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from tests.unit.processor.base import BaseProcessorTestCase

RULES_DIR_MISSING = "tests/testdata/unit/generic_adder/rules_missing"
RULES_DIR_INVALID = "tests/testdata/unit/generic_adder/rules_invalid"
RULES_DIR_FIRST_EXISTING = "tests/testdata/unit/generic_adder/rules_first_existing"


class TestGenericAdder(BaseProcessorTestCase):
    test_cases = [  # testcase, rule, event, expected
        (
            "Add from file",
            {
                "filter": "add_list_generic_test",
                "generic_adder": {
                    "add_from_file": "tests/testdata/unit/generic_adder/additions_file.yml"
                },
            },
            {"add_list_generic_test": "Test", "event_id": 123},
            {
                "add_list_generic_test": "Test",
                "event_id": 123,
                "some_added_field": "some value",
                "another_added_field": "another_value",
                "dotted": {"added": {"field": "yet_another_value"}},
            },
        ),
        (
            "Add from file in list",
            {
                "filter": "add_lists_one_generic_test",
                "generic_adder": {
                    "add_from_file": ["tests/testdata/unit/generic_adder/additions_file.yml"]
                },
            },
            {"add_lists_one_generic_test": "Test", "event_id": 123},
            {
                "add_lists_one_generic_test": "Test",
                "event_id": 123,
                "some_added_field": "some value",
                "another_added_field": "another_value",
                "dotted": {"added": {"field": "yet_another_value"}},
            },
        ),
        (
            "Add from two files",
            {
                "filter": "add_lists_two_generic_test",
                "generic_adder": {
                    "add_from_file": [
                        "tests/testdata/unit/generic_adder/additions_file.yml",
                        "tests/testdata/unit/generic_adder/additions_file_2.yml",
                    ]
                },
            },
            {"add_lists_two_generic_test": "Test", "event_id": 123},
            {
                "add_lists_two_generic_test": "Test",
                "event_id": 123,
                "added_from_other_file": "some field from another file",
                "some_added_field": "some value",
                "another_added_field": "another_value",
                "dotted": {"added": {"field": "yet_another_value"}},
            },
        ),
        (
            "Add from two files using only first existing file",
            {
                "filter": "add_first_existing_generic_test",
                "generic_adder": {
                    "add_from_file": [
                        "tests/testdata/unit/generic_adder/additions_file.yml",
                        "tests/testdata/unit/generic_adder/additions_file_2.yml",
                    ],
                    "only_first_existing_file": True,
                },
            },
            {"add_first_existing_generic_test": "Test", "event_id": 123},
            {
                "add_first_existing_generic_test": "Test",
                "event_id": 123,
                "some_added_field": "some value",
                "another_added_field": "another_value",
                "dotted": {"added": {"field": "yet_another_value"}},
            },
        ),
        (
            "Add from two files using only first existing file, but first file doesn't exist",
            {
                "filter": "add_first_existing_with_missing_generic_test",
                "generic_adder": {
                    "add_from_file": [
                        "I_DO_NOT_EXIST",
                        "tests/testdata/unit/generic_adder/additions_file.yml",
                    ],
                    "only_first_existing_file": True,
                },
            },
            {
                "add_first_existing_with_missing_generic_test": "Test",
                "event_id": 123,
            },
            {
                "add_first_existing_with_missing_generic_test": "Test",
                "event_id": 123,
                "some_added_field": "some value",
                "another_added_field": "another_value",
                "dotted": {"added": {"field": "yet_another_value"}},
            },
        ),
        (
            "Add from rule definition",
            {
                "filter": "add_generic_test",
                "generic_adder": {
                    "add": {
                        "some_added_field": "some value",
                        "another_added_field": "another_value",
                        "dotted.added.field": "yet_another_value",
                    }
                },
                "description": "",
            },
            {"add_generic_test": "Test", "event_id": 123},
            {
                "add_generic_test": "Test",
                "event_id": 123,
                "some_added_field": "some value",
                "another_added_field": "another_value",
                "dotted": {"added": {"field": "yet_another_value"}},
            },
        ),
        (
            "Add to existing dict without conflict",
            {
                "filter": "add_generic_test",
                "generic_adder": {
                    "add": {
                        "some_added_field": "some value",
                        "another_added_field": "another_value",
                        "dotted.added.field": "yet_another_value",
                    }
                },
                "description": "",
            },
            {
                "add_generic_test": "Test",
                "event_id": 123,
                "dotted": {"i_exist": "already"},
            },
            {
                "add_generic_test": "Test",
                "event_id": 123,
                "some_added_field": "some value",
                "another_added_field": "another_value",
                "dotted": {"added": {"field": "yet_another_value"}, "i_exist": "already"},
            },
        ),
        (
            "Add to existing with setting overwrite",
            {
                "filter": "add_generic_test",
                "generic_adder": {
                    "add": {
                        "some_added_field": "some value",
                        "another_added_field": "another_value",
                        "dotted.added.field": "yet_another_value",
                    },
                    "overwrite_target": True,
                },
            },
            {
                "add_generic_test": "Test",
                "event_id": 123,
                "some_added_field": "some_non_dict",
            },
            {
                "add_generic_test": "Test",
                "event_id": 123,
                "some_added_field": "some value",
                "another_added_field": "another_value",
                "dotted": {"added": {"field": "yet_another_value"}},
            },
        ),
        (
            "Extend list field with 'merge_with_target' enabled",
            {
                "filter": "extend_generic_test",
                "generic_adder": {
                    "add": {
                        "some_added_field": "some value",
                        "another_added_field": "another_value",
                        "dotted.added.field": "yet_another_value",
                    },
                    "merge_with_target": True,
                },
            },
            {"extend_generic_test": "Test", "event_id": 123, "some_added_field": []},
            {
                "extend_generic_test": "Test",
                "event_id": 123,
                "some_added_field": ["some value"],
                "another_added_field": "another_value",
                "dotted": {"added": {"field": "yet_another_value"}},
            },
        ),
        (
            "Extend list field with 'merge_with_target' enabled",
            {
                "filter": "*",
                "generic_adder": {
                    "add": {
                        "some_added_field": ["some value"],
                    },
                },
            },
            {"extend_generic_test": "Test"},
            {"extend_generic_test": "Test", "some_added_field": ["some value"]},
        ),
    ]

    failure_test_cases = [  # testcase, rule, event, expected, error_message
        (
            "Add to existing value with 'overwrite_target' disabled",
            {
                "filter": "add_generic_test",
                "generic_adder": {
                    "add": {
                        "some_added_field": "some value",
                        "another_added_field": "another_value",
                        "dotted.added.field": "yet_another_value",
                    },
                    "overwrite_target": False,
                },
            },
            {
                "add_generic_test": "Test",
                "event_id": 123,
                "some_added_field": "some_non_dict",
            },
            {
                "add_generic_test": "Test",
                "event_id": 123,
                "some_added_field": "some_non_dict",
                "another_added_field": "another_value",
                "dotted": {"added": {"field": "yet_another_value"}},
                "tags": ["_generic_adder_failure"],
            },
            r"subfields existed and could not be extended: some_added_field",
        ),
        (
            "Extend list field with 'merge_with_target' disabled",
            {
                "filter": "extend_generic_test",
                "generic_adder": {
                    "add": {
                        "some_added_field": "some value",
                        "another_added_field": "another_value",
                        "dotted.added.field": "yet_another_value",
                    },
                    "merge_with_target": False,
                },
            },
            {"extend_generic_test": "Test", "event_id": 123, "some_added_field": []},
            {
                "extend_generic_test": "Test",
                "event_id": 123,
                "some_added_field": [],
                "another_added_field": "another_value",
                "dotted": {"added": {"field": "yet_another_value"}},
                "tags": ["_generic_adder_failure"],
            },
            r"subfields existed and could not be extended: some_added_field",
        ),
        (
            "Extend list field with 'merge_with_target' enabled, but non-list target",
            {
                "filter": "extend_generic_test",
                "generic_adder": {
                    "add": {
                        "some_added_field": "some value",
                        "another_added_field": "another_value",
                        "dotted.added.field": "yet_another_value",
                    },
                    "merge_with_target": True,
                },
            },
            {"extend_generic_test": "Test", "event_id": 123, "some_added_field": "not_a_list"},
            {
                "extend_generic_test": "Test",
                "event_id": 123,
                "some_added_field": "not_a_list",
                "another_added_field": "another_value",
                "dotted": {"added": {"field": "yet_another_value"}},
                "tags": ["_generic_adder_failure"],
            },
            r"subfields existed and could not be extended: some_added_field",
        ),
    ]

    CONFIG = {
        "type": "generic_adder",
        "rules": ["tests/testdata/unit/generic_adder/rules"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_generic_adder_testcases(
        self, testcase, rule, event, expected
    ):  # pylint: disable=unused-argument
        self._load_rule(rule)
        self.object.process(event)
        assert event == expected

    @pytest.mark.parametrize("testcase, rule, event, expected, error_message", failure_test_cases)
    def test_generic_adder_testcases_failure_handling(
        self, testcase, rule, event, expected, error_message
    ):
        self._load_rule(rule)
        result = self.object.process(event)
        assert len(result.warnings) == 1
        assert re.match(rf".*FieldExistsWarning.*{error_message}", str(result.warnings[0]))
        assert event == expected, testcase

    def test_add_generic_fields_from_file_missing_and_existing_with_all_required(self):
        with pytest.raises(InvalidRuleDefinitionError, match=r"files do not exist"):
            config = deepcopy(self.CONFIG)
            config["rules"] = [RULES_DIR_MISSING]
            configuration = {"test_instance_name": config}
            Factory.create(configuration)

    def test_add_generic_fields_from_file_invalid(self):
        with pytest.raises(
            InvalidRuleDefinitionError,
            match=r"must be a dictionary with string values",
        ):
            config = deepcopy(self.CONFIG)
            config["rules"] = [RULES_DIR_INVALID]
            configuration = {"test processor": config}
            Factory.create(configuration)
