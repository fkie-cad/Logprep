# pylint: disable=protected-access
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
import copy

import pytest
from pytest import raises

from logprep.ng.event.log_event import LogEvent
from logprep.factory import Factory
from logprep.processor.base.exceptions import ValueDoesnotExistInSchemaError
from logprep.processor.labeler.labeling_schema import LabelingSchema
from logprep.processor.labeler.rule import LabelerRule
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


class TestLabeler(BaseProcessorTestCase):
    timeout = 0.01

    CONFIG = {
        "type": "ng_labeler",
        "schema": "tests/testdata/unit/labeler/schemas/schema.json",
        "rules": ["tests/testdata/unit/labeler/rules"],
    }

    def _load_rule(self, rule, schema=None):  # pylint: disable=arguments-differ
        rule = LabelerRule.create_from_dict(rule)
        if schema:
            rule.add_parent_labels_from_schema(schema)
        self.object._rule_tree.add_rule(rule)

    def test_process_adds_labels_to_event(self):
        rule = {"filter": "applyrule", "labeler": {"label": {"reporter": ["windows"]}}}
        document = {"applyrule": "yes"}
        expected = {"applyrule": "yes", "label": {"reporter": ["windows"]}}

        self._load_rule(rule)
        log_event = LogEvent(document, original=b"test_message")
        self.object.process(log_event)

        assert log_event.data == expected

    def test_process_adds_labels_to_event_with_umlauts(self):
        rule = {
            "filter": "äpplyrüle: nö",
            "labeler": {"label": {"räpörter": ["windöws"]}},
            "description": "this is ä test rüle",
        }

        document = {"äpplyrüle": "nö"}
        expected = {"äpplyrüle": "nö", "label": {"räpörter": ["windöws"]}}

        self._load_rule(rule)
        log_event = LogEvent(document, original=b"test_message")
        self.object.process(log_event)

        assert log_event.data == expected

    def test_process_adds_labels_including_parents_when_flag_was_set(
        self, reporter_schema_expanded
    ):
        rule = {"filter": "applyrule", "labeler": {"label": {"reporter": ["windows"]}}}

        document = {"applyrule": "yes"}
        expected = {"applyrule": "yes", "label": {"reporter": ["parentlabel", "windows"]}}

        self._load_rule(rule, reporter_schema_expanded)
        log_event = LogEvent(document, original=b"test_message")
        self.object.process(log_event)

        assert log_event.data == expected

    def test_process_adds_more_than_one_label(self):
        rule = {
            "filter": "key: value",
            "labeler": {"label": {"reporter": ["client", "windows"], "object": ["file"]}},
        }
        document = {"key": "value"}
        expected = {
            "key": "value",
            "label": {"reporter": ["client", "windows"], "object": ["file"]},
        }

        self._load_rule(rule)
        log_event = LogEvent(document, original=b"test_message")
        self.object.process(log_event)

        assert log_event.data == expected
