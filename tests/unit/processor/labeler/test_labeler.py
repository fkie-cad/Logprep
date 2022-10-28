# pylint: disable=protected-access
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
import copy

import pytest
from pytest import raises

from logprep.processor.base.exceptions import ValueDoesnotExistInSchemaError
from logprep.processor.labeler.labeling_schema import LabelingSchema
from logprep.processor.labeler.rule import LabelerRule
from logprep.factory import Factory
from tests.testdata.metadata import path_to_schema, path_to_schema2
from tests.unit.processor.base import BaseProcessorTestCase


@pytest.fixture(name="reporter_schema")
def create_reporter_schema():
    schema = LabelingSchema()
    schema.ingest_schema(
        {
            "reporter": {
                "category": "category description",
                "windows": {"description": "windows description"},
            }
        }
    )
    return schema


@pytest.fixture(name="reporter_schema_expanded")
def create_reporter_schema_expanded():
    expanded_schema = LabelingSchema()
    expanded_schema.ingest_schema(
        {
            "reporter": {
                "category": "category description",
                "parentlabel": {
                    "description": "parentlabel description",
                    "windows": {"description": "windows description"},
                },
            }
        }
    )
    return expanded_schema


@pytest.fixture(name="empty_schema")
def create_empty_schema():
    empty_schema = LabelingSchema()
    empty_schema.ingest_schema({})
    return empty_schema


class TestLabeler(BaseProcessorTestCase):
    timeout = 0.01

    CONFIG = {
        "type": "labeler",
        "schema": "tests/testdata/unit/labeler/schemas/schema.json",
        "specific_rules": ["tests/testdata/unit/labeler/rules/specific/"],
        "generic_rules": ["tests/testdata/unit/labeler/rules/generic/"],
    }

    @property
    def specific_rules_dirs(self):
        """Return path to specific rule directories"""
        return self.CONFIG["specific_rules"]

    @property
    def generic_rules_dirs(self):
        """Return path to generic rule directories"""
        return self.CONFIG["generic_rules"]

    def _load_specific_rule(self, rule, schema=None):  # pylint: disable=arguments-differ
        specific_rule = LabelerRule._create_from_dict(rule)
        if schema:
            specific_rule.add_parent_labels_from_schema(schema)
        self.object._specific_tree.add_rule(specific_rule, self.logger)

    def test_process_adds_labels_to_event(self):
        rule = {"filter": "applyrule", "label": {"reporter": ["windows"]}}
        document = {"applyrule": "yes"}
        expected = {"applyrule": "yes", "label": {"reporter": ["windows"]}}

        self._load_specific_rule(rule)
        self.object.process(document)

        assert document == expected

    def test_process_adds_labels_to_event_with_umlauts(self):
        rule = {
            "filter": "äpplyrüle: nö",
            "label": {"räpörter": ["windöws"]},
            "description": "this is ä test rüle",
        }

        document = {"äpplyrüle": "nö"}
        expected = {"äpplyrüle": "nö", "label": {"räpörter": ["windöws"]}}

        self._load_specific_rule(rule)
        self.object.process(document)

        assert document == expected

    def test_process_adds_labels_including_parents_when_flag_was_set(
        self, reporter_schema_expanded
    ):
        rule = {"filter": "applyrule", "label": {"reporter": ["windows"]}}

        document = {"applyrule": "yes"}
        expected = {"applyrule": "yes", "label": {"reporter": ["parentlabel", "windows"]}}

        self._load_specific_rule(rule, reporter_schema_expanded)
        self.object.process(document)

        assert document == expected

    def test_process_adds_more_than_one_label(self):
        rule = {
            "filter": "key: value",
            "label": {"reporter": ["client", "windows"], "object": ["file"]},
        }
        document = {"key": "value"}
        expected = {
            "key": "value",
            "label": {"reporter": ["client", "windows"], "object": ["file"]},
        }

        self._load_specific_rule(rule)
        self.object.process(document)

        assert document == expected

    def test_process_does_not_overwrite_existing_values(self):
        rule = {"filter": "applyrule", "label": {"reporter": ["windows"]}}
        document = {"applyrule": "yes", "label": {"reporter": ["windows"]}}
        expected = {"applyrule": "yes", "label": {"reporter": ["windows"]}}

        self._load_specific_rule(rule)
        self.object.process(document)

        assert document == expected

    def test_process_returns_labels_in_alphabetical_order(self, reporter_schema_expanded):
        event = {"applyrule": "yes"}
        rule = {"filter": "applyrule", "label": {"reporter": ["windows"]}}

        self._load_specific_rule(rule, reporter_schema_expanded)
        self.object.process(event)

        assert event["label"]["reporter"] == ["parentlabel", "windows"]

    def test_process_matches_event_with_array_with_one_element(self):
        document = {"field_with_array": ["im_inside_an_array"]}
        expected = {
            "field_with_array": ["im_inside_an_array"],
            "label": {"some_new_label": ["some_new_value"]},
        }

        rule = {
            "filter": "field_with_array: im_inside_an_array",
            "label": {"some_new_label": ["some_new_value"]},
            "description": "This does even match with arrays!",
        }

        self._load_specific_rule(rule)
        self.object.process(document)

        assert document == expected

    def test_process_matches_event_with_array_if_at_least_one_element_matches(self):
        document = {"field_with_array": ["im_inside_an_array", "im_also_inside_that_array!"]}
        expected = {
            "field_with_array": ["im_inside_an_array", "im_also_inside_that_array!"],
            "label": {"some_new_label": ["some_new_value"]},
        }

        rule = {
            "filter": "field_with_array: im_inside_an_array",
            "label": {"some_new_label": ["some_new_value"]},
            "description": "This does even match with arrays!",
        }

        self._load_specific_rule(rule)
        self.object.process(document)

        assert document == expected

    def test_process_matches_event_with_array_with_one_element_with_regex(self):
        document = {"field_with_array": ["im_inside_an_array"]}
        expected = {
            "field_with_array": ["im_inside_an_array"],
            "label": {"some_new_label": ["some_new_value"]},
        }

        rule = {
            "filter": "field_with_array: im_inside_an_a.*y",
            "regex_fields": ["field_with_array"],
            "label": {"some_new_label": ["some_new_value"]},
            "description": "This does even match with arrays!",
        }

        self._load_specific_rule(rule)
        self.object.process(document)

        assert document == expected

    def test_process_matches_event_with_array_with_one_element_with_regex_one_without(self):
        document = {"field_with_array": ["im_inside_an_array", "im_also_inside_that_array!"]}
        expected = {
            "field_with_array": ["im_inside_an_array", "im_also_inside_that_array!"],
            "label": {"some_new_label": ["some_new_value"]},
        }

        rule_dict = {
            "filter": (
                "field_with_array: im_inside_.*y AND "
                "field_with_array: im_also_inside_that_array!"
            ),
            "regex_fields": ["field_with_array"],
            "label": {"some_new_label": ["some_new_value"]},
            "description": "This does even match with arrays!",
        }

        self._load_specific_rule(rule_dict)

        self.object.process(document)

        assert document == expected

    def test_create_fails_when_include_parent_labels_is_not_boolean(self):
        config = copy.deepcopy(self.CONFIG)
        config["include_parent_labels"] = "this is a string"
        with raises(
            TypeError,
            match="'include_parent_labels' must be <class 'bool'>",
        ):
            Factory.create({"test instance": config}, self.logger)

    def test_create_fails_when_rules_do_not_conform_to_labeling_schema(self):
        config = copy.deepcopy(self.CONFIG)
        config["schema"] = path_to_schema2
        with raises(
            ValueDoesnotExistInSchemaError, match="Invalid value 'windows' for key 'reporter'."
        ):
            Factory.create({"test instance": config}, self.logger)

    def test_create_loads_the_specified_labeling_schema(self):
        config = copy.deepcopy(self.CONFIG)
        config["schema"] = path_to_schema
        expected_schema = LabelingSchema.create_from_file(path_to_schema)
        labeler = Factory.create({"test instance": config}, self.logger)

        assert labeler._schema == expected_schema
