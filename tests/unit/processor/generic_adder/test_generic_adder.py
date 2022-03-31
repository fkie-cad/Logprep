from copy import deepcopy
from logging import getLogger

import pytest
from logprep.processor.generic_adder.rule import InvalidGenericAdderDefinition

from tests.unit.processor.base import BaseProcessorTestCase

pytest.importorskip("logprep.processor.generic_adder")

from logprep.processor.base.exceptions import InvalidRuleFileError

from logprep.processor.generic_adder.factory import GenericAdderFactory
from logprep.processor.generic_adder.processor import DuplicationError


rules_dir_missing = "tests/testdata/unit/generic_adder/rules_missing"
rules_dir_invalid = "tests/testdata/unit/generic_adder/rules_invalid"
rules_dir_first_existing = "tests/testdata/unit/generic_adder/rules_first_existing"


class TestGenericAdder(BaseProcessorTestCase):

    factory = GenericAdderFactory

    CONFIG = {
        "type": "generic_adder",
        "generic_rules": ["tests/testdata/unit/generic_adder/rules/generic"],
        "specific_rules": ["tests/testdata/unit/generic_adder/rules/specific"],
    }

    @property
    def generic_rules_dirs(self):
        return self.CONFIG.get("generic_rules")

    @property
    def specific_rules_dirs(self):
        return self.CONFIG.get("specific_rules")

    def test_add_generic_fields(self):
        assert self.object.ps.processed_count == 0
        expected = {
            "add_generic_test": "Test",
            "event_id": 123,
            "some_added_field": "some value",
            "another_added_field": "another_value",
            "dotted": {"added": {"field": "yet_another_value"}},
        }
        document = {"add_generic_test": "Test", "event_id": 123}

        self.object.process(document)

        assert document == expected

    def test_add_generic_fields_from_file(self):
        assert self.object.ps.processed_count == 0
        expected = {
            "add_list_generic_test": "Test",
            "event_id": 123,
            "some_added_field": "some value",
            "another_added_field": "another_value",
            "dotted": {"added": {"field": "yet_another_value"}},
        }
        document = {"add_list_generic_test": "Test", "event_id": 123}

        self.object.process(document)

        assert document == expected

    def test_add_generic_fields_from_file_list_one_element(self):
        assert self.object.ps.processed_count == 0
        expected = {
            "add_lists_one_generic_test": "Test",
            "event_id": 123,
            "some_added_field": "some value",
            "another_added_field": "another_value",
            "dotted": {"added": {"field": "yet_another_value"}},
        }
        document = {"add_lists_one_generic_test": "Test", "event_id": 123}

        self.object.process(document)

        assert document == expected

    def test_add_generic_fields_from_file_list_two_elements(self):
        assert self.object.ps.processed_count == 0
        expected = {
            "add_lists_two_generic_test": "Test",
            "event_id": 123,
            "added_from_other_file": "some field from another file",
            "some_added_field": "some value",
            "another_added_field": "another_value",
            "dotted": {"added": {"field": "yet_another_value"}},
        }
        document = {"add_lists_two_generic_test": "Test", "event_id": 123}

        self.object.process(document)

        assert document == expected

    def test_add_generic_fields_from_file_first_existing(self):
        config = deepcopy(self.CONFIG)
        config["generic_rules"] = [rules_dir_first_existing]
        config["specific_rules"] = []

        generic_adder = GenericAdderFactory.create("test-generic-adder", config, self.logger)

        assert generic_adder.ps.processed_count == 0
        expected = {
            "add_first_existing_generic_test": "Test",
            "event_id": 123,
            "some_added_field": "some value",
            "another_added_field": "another_value",
            "dotted": {"added": {"field": "yet_another_value"}},
        }
        document = {"add_first_existing_generic_test": "Test", "event_id": 123}

        generic_adder.process(document)

        assert document == expected

    def test_add_generic_fields_from_file_first_existing_with_missing(self):
        config = deepcopy(self.CONFIG)
        config["specific_rules"] = [rules_dir_first_existing]
        config["generic_rules"] = []

        generic_adder = GenericAdderFactory.create("test-generic-adder", config, self.logger)

        assert generic_adder.ps.processed_count == 0
        expected = {
            "add_first_existing_with_missing_generic_test": "Test",
            "event_id": 123,
            "some_added_field": "some value",
            "another_added_field": "another_value",
            "dotted": {"added": {"field": "yet_another_value"}},
        }
        document = {
            "add_first_existing_with_missing_generic_test": "Test",
            "event_id": 123,
        }

        generic_adder.process(document)

        assert document == expected

    def test_add_generic_fields_from_file_missing_and_existing_with_all_required(self):
        with pytest.raises(InvalidGenericAdderDefinition, match=r"files do not exist"):
            config = deepcopy(self.CONFIG)
            config["specific_rules"] = [rules_dir_missing]

            GenericAdderFactory.create("test-generic-adder", config, self.logger)

    def test_add_generic_fields_from_file_invalid(self):
        with pytest.raises(
            InvalidGenericAdderDefinition,
            match=r"must be a dictionary with string values",
        ):
            config = deepcopy(self.CONFIG)
            config["generic_rules"] = [rules_dir_invalid]

            GenericAdderFactory.create("test-generic-adder", config, self.logger)

    def test_add_generic_fields_to_co_existing_field(self):
        expected = {
            "add_generic_test": "Test",
            "event_id": 123,
            "some_added_field": "some value",
            "another_added_field": "another_value",
            "dotted": {"added": {"field": "yet_another_value"}, "i_exist": "already"},
        }
        document = {
            "add_generic_test": "Test",
            "event_id": 123,
            "dotted": {"i_exist": "already"},
        }

        self.object.process(document)

        assert document == expected

    def test_add_generic_fields_to_existing_value(self):
        expected = {
            "add_generic_test": "Test",
            "event_id": 123,
            "some_added_field": "some_non_dict",
            "another_added_field": "another_value",
            "dotted": {"added": {"field": "yet_another_value"}},
        }
        document = {
            "add_generic_test": "Test",
            "event_id": 123,
            "some_added_field": "some_non_dict",
        }

        with pytest.raises(DuplicationError):
            self.object.process(document)

        assert document == expected
