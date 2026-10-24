# pylint: disable=protected-access
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
import copy
from copy import deepcopy
from unittest import mock

import pytest
from pytest import raises

from logprep.factory import Factory
from logprep.ng.abc.event import InputMeta, LogEvent
from logprep.ng.processor.labeler.processor import Labeler
from logprep.ng.processor.labeler.rule import LabelerRule
from logprep.processor.base.exceptions import ValueDoesnotExistInSchemaError
from logprep.processor.labeler.labeling_schema import LabelingSchema
from tests.testdata.metadata import path_to_schema, path_to_schema2
from tests.unit.ng.processor.base import BaseProcessorTestCase


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


class TestLabeler(BaseProcessorTestCase[Labeler]):
    timeout = 0.01

    CONFIG = {
        "type": "labeler",
        "schema": "tests/testdata/unit/labeler/schemas/schema.json",
        "rules": ["tests/testdata/unit/labeler/rules"],
    }

    async def _load_rule(
        self, rule, schema=None, instance=None
    ):  # pylint: disable=arguments-differ
        rule = LabelerRule.create_from_dict(rule)
        if schema:
            rule.add_parent_labels_from_schema(schema)

        if instance is None:
            self.object._rule_tree.add_rule(rule)
        else:
            instance._rule_tree.add_rule(rule)

    async def test_process_adds_labels_to_event(self):
        rule = {"filter": "applyrule", "labeler": {"label": {"reporter": ["windows"]}}}
        config = deepcopy(self.CONFIG)
        config["rules"] = [rule]
        document = {"applyrule": "yes"}
        event = LogEvent(document, original=b"", input_meta=InputMeta())
        expected = {"applyrule": "yes", "label": {"reporter": ["windows"]}}

        async with self.create_and_setup_processor(config_patch=config) as instance:
            await instance.process(event)

        assert event.data == expected

    async def test_process_adds_labels_to_event_with_umlauts(self):
        rule = {
            "filter": "äpplyrüle: nö",
            "labeler": {"label": {"räpörter": ["windöws"]}},
            "description": "this is ä test rüle",
        }
        config = deepcopy(self.CONFIG)
        config["rules"] = [rule]
        document = {"äpplyrüle": "nö"}
        event = LogEvent(document, original=b"", input_meta=InputMeta())
        expected = {"äpplyrüle": "nö", "label": {"räpörter": ["windöws"]}}

        # TODO(async-followup): adapt tests to new setup logic; temporarily mock additional calls.
        with mock.patch(
            "logprep.ng.processor.labeler.labeling_schema.LabelingSchema.validate_labels"
        ):
            async with self.create_and_setup_processor(config_patch=config) as instance:
                await instance.process(event)

        assert event.data == expected

    async def test_process_adds_labels_including_parents_when_flag_was_set(
        self, reporter_schema_expanded
    ):
        rule = {"filter": "applyrule", "labeler": {"label": {"reporter": ["windows"]}}}
        document = {"applyrule": "yes"}
        event = LogEvent(document, original=b"", input_meta=InputMeta())
        expected = {"applyrule": "yes", "label": {"reporter": ["parentlabel", "windows"]}}

        async with self.create_and_setup_processor() as instance:
            await self._load_rule(rule, schema=reporter_schema_expanded, instance=instance)
            await instance.process(event)

        assert event.data == expected

    async def test_process_adds_more_than_one_label(self):
        rule = {
            "filter": "key: value",
            "labeler": {"label": {"reporter": ["client", "windows"], "object": ["file"]}},
        }
        config = deepcopy(self.CONFIG)
        config["rules"] = [rule]
        document = {"key": "value"}
        event = LogEvent(document, original=b"", input_meta=InputMeta())
        expected = {
            "key": "value",
            "label": {"reporter": ["client", "windows"], "object": ["file"]},
        }

        # TODO(async-followup): adapt tests to new setup logic; temporarily mock additional calls.
        with mock.patch(
            "logprep.ng.processor.labeler.labeling_schema.LabelingSchema.validate_labels"
        ):
            async with self.create_and_setup_processor(config_patch=config) as instance:
                await instance.process(event)

        assert event.data == expected

    async def test_process_does_not_overwrite_existing_values(self):
        rule = {"filter": "applyrule", "labeler": {"label": {"reporter": ["windows"]}}}
        config = deepcopy(self.CONFIG)
        config["rules"] = [rule]
        document = {"applyrule": "yes", "label": {"reporter": ["windows"]}}
        event = LogEvent(document, original=b"", input_meta=InputMeta())
        expected = {"applyrule": "yes", "label": {"reporter": ["windows"]}}

        async with self.create_and_setup_processor(config_patch=config) as instance:
            await instance.process(event)

        assert event.data == expected

    async def test_process_returns_labels_in_alphabetical_order(self, reporter_schema_expanded):
        rule = {"filter": "applyrule", "labeler": {"label": {"reporter": ["windows"]}}}

        document = {"applyrule": "yes"}
        event = LogEvent(document, original=b"", input_meta=InputMeta())

        async with self.create_and_setup_processor() as instance:
            await self._load_rule(rule, schema=reporter_schema_expanded, instance=instance)
            await instance.process(event)

        assert event.data["label"]["reporter"] == ["parentlabel", "windows"]

    async def test_process_matches_event_with_array_with_one_element(self):
        rule = {
            "filter": "field_with_array: im_inside_an_array",
            "labeler": {"label": {"some_new_label": ["some_new_value"]}},
            "description": "This does even match with arrays!",
        }
        config = deepcopy(self.CONFIG)
        config["rules"] = [rule]
        document = {"field_with_array": ["im_inside_an_array"]}
        event = LogEvent(document, original=b"", input_meta=InputMeta())
        expected = {
            "field_with_array": ["im_inside_an_array"],
            "label": {"some_new_label": ["some_new_value"]},
        }

        # TODO(async-followup): adapt tests to new setup logic; temporarily mock additional calls.
        with mock.patch(
            "logprep.ng.processor.labeler.labeling_schema.LabelingSchema.validate_labels"
        ):
            async with self.create_and_setup_processor(config_patch=config) as instance:
                await instance.process(event)

        assert event.data == expected

    async def test_process_matches_event_with_array_if_at_least_one_element_matches(self):
        rule = {
            "filter": "field_with_array: im_inside_an_array",
            "labeler": {"label": {"some_new_label": ["some_new_value"]}},
            "description": "This does even match with arrays!",
        }
        config = deepcopy(self.CONFIG)
        config["rules"] = [rule]
        document = {"field_with_array": ["im_inside_an_array", "im_also_inside_that_array!"]}
        event = LogEvent(document, original=b"", input_meta=InputMeta())
        expected = {
            "field_with_array": ["im_inside_an_array", "im_also_inside_that_array!"],
            "label": {"some_new_label": ["some_new_value"]},
        }

        # TODO(async-followup): adapt tests to new setup logic; temporarily mock additional calls.
        with mock.patch(
            "logprep.ng.processor.labeler.labeling_schema.LabelingSchema.validate_labels"
        ):
            async with self.create_and_setup_processor(config_patch=config) as instance:
                await instance.process(event)

        assert event.data == expected

    async def test_process_matches_event_with_array_with_one_element_with_regex(self):
        rule = {
            "filter": "field_with_array: im_inside_an_a.*y",
            "regex_fields": ["field_with_array"],
            "labeler": {"label": {"some_new_label": ["some_new_value"]}},
            "description": "This does even match with arrays!",
        }
        config = deepcopy(self.CONFIG)
        config["rules"] = [rule]
        document = {"field_with_array": ["im_inside_an_array"]}
        event = LogEvent(document, original=b"", input_meta=InputMeta())
        expected = {
            "field_with_array": ["im_inside_an_array"],
            "label": {"some_new_label": ["some_new_value"]},
        }

        # TODO(async-followup): adapt tests to new setup logic; temporarily mock additional calls.
        with mock.patch(
            "logprep.ng.processor.labeler.labeling_schema.LabelingSchema.validate_labels"
        ):
            async with self.create_and_setup_processor(config_patch=config) as instance:
                await instance.process(event)

        assert event.data == expected

    async def test_process_matches_event_with_array_with_one_element_with_regex_one_without(self):
        rule = {
            "filter": (
                "field_with_array: im_inside_.*y AND "
                "field_with_array: im_also_inside_that_array!"
            ),
            "regex_fields": ["field_with_array"],
            "labeler": {"label": {"some_new_label": ["some_new_value"]}},
            "description": "This does even match with arrays!",
        }
        config = deepcopy(self.CONFIG)
        config["rules"] = [rule]
        document = {"field_with_array": ["im_inside_an_array", "im_also_inside_that_array!"]}
        event = LogEvent(document, original=b"", input_meta=InputMeta())
        expected = {
            "field_with_array": ["im_inside_an_array", "im_also_inside_that_array!"],
            "label": {"some_new_label": ["some_new_value"]},
        }

        # TODO(async-followup): adapt tests to new setup logic; temporarily mock additional calls.
        with mock.patch(
            "logprep.ng.processor.labeler.labeling_schema.LabelingSchema.validate_labels"
        ):
            async with self.create_and_setup_processor(config_patch=config) as instance:
                await instance.process(event)

        assert event.data == expected

    async def test_create_fails_when_include_parent_labels_is_not_boolean(self):
        config = copy.deepcopy(self.CONFIG)
        config["include_parent_labels"] = "this is a string"
        with raises(
            TypeError,
            match="'include_parent_labels' must be <class 'bool'>",
        ):
            Factory.create({"test instance": config})

    async def test_create_fails_when_rules_do_not_conform_to_labeling_schema(self):
        config = copy.deepcopy(self.CONFIG)
        config["schema"] = path_to_schema2
        with raises(
            ValueDoesnotExistInSchemaError, match="Invalid value 'windows' for key 'reporter'."
        ):
            labeler = Factory.create({"test instance": config})
            await labeler.setup()

    async def test_create_loads_the_specified_labeling_schema(self):
        config = copy.deepcopy(self.CONFIG)
        config["schema"] = path_to_schema
        expected_schema = LabelingSchema.create_from_file(path_to_schema)

        async with self.create_and_setup_processor(config_patch=config) as instance:
            assert instance._schema == expected_schema

    async def test_extend_list_of_existing_labels(self):
        rule = {"filter": "applyrule", "labeler": {"label": {"reporter": ["windows", "foo"]}}}
        config = deepcopy(self.CONFIG)
        config["rules"] = [rule]
        document = {"applyrule": "yes", "label": {"reporter": ["windows"]}}
        event = LogEvent(document, original=b"", input_meta=InputMeta())
        expected = {"applyrule": "yes", "label": {"reporter": ["foo", "windows"]}}

        # TODO(async-followup): adapt tests to new setup logic; temporarily mock additional calls.
        with mock.patch(
            "logprep.ng.processor.labeler.labeling_schema.LabelingSchema.validate_labels"
        ):
            async with self.create_and_setup_processor(config_patch=config) as instance:
                await instance.process(event)

        assert event.data == expected
