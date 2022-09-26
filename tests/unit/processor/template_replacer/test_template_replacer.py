# pylint: disable=missing-module-docstring
from copy import deepcopy

import pytest

from logprep.factory import Factory
from logprep.processor.template_replacer.processor import TemplateReplacerError
from tests.unit.processor.base import BaseProcessorTestCase


class TestTemplateReplacer(BaseProcessorTestCase):

    CONFIG = {
        "type": "template_replacer",
        "generic_rules": ["tests/testdata/unit/template_replacer/rules/generic"],
        "specific_rules": ["tests/testdata/unit/template_replacer/rules/specific"],
        "template": "tests/testdata/unit/template_replacer/replacer_template.yml",
        "pattern": {
            "delimiter": "-",
            "fields": ["winlog.channel", "winlog.provider_name", "winlog.event_id"],
            "allowed_delimiter_field": "winlog.provider_name",
            "target_field": "message",
        },
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }

    @property
    def generic_rules_dirs(self):
        return self.CONFIG.get("generic_rules")

    @property
    def specific_rules_dirs(self):
        return self.CONFIG.get("specific_rules")

    def test_replace_message_via_template(self):
        assert self.object.metrics.number_of_processed_events == 0
        document = {
            "winlog": {"channel": "System", "provider_name": "Test", "event_id": 123},
            "message": "foo",
        }

        self.object.process(document)

        assert document.get("message")
        assert document["message"] == "Test %1 Test %2"

    def test_replace_non_existing_message_via_template(self):
        assert self.object.metrics.number_of_processed_events == 0
        document = {"winlog": {"channel": "System", "provider_name": "Test", "event_id": 123}}

        self.object.process(document)

        assert document.get("message")
        assert document["message"] == "Test %1 Test %2"

    def test_replace_with_additional_hyphen(self):
        assert self.object.metrics.number_of_processed_events == 0
        document = {
            "winlog": {"channel": "System", "provider_name": "Test-Test", "event_id": 123},
            "message": "foo",
        }

        self.object.process(document)

        assert document.get("message")
        assert document["message"] == "Test %1 Test %2 Test %3"

    def test_replace_fails_because_it_does_not_map_to_anything(self):
        assert self.object.metrics.number_of_processed_events == 0

        document = {
            "winlog": {"channel": "System", "provider_name": "Test-Test", "event_id": 923},
            "message": "foo",
        }
        self.object.process(document)
        assert document.get("message") == "foo"

        document = {
            "winlog": {"channel": "System", "provider_name": "Test-Test-No", "event_id": 123},
            "message": "foo",
        }
        self.object.process(document)
        assert document.get("message") == "foo"

    def test_replace_dotted_message_via_template(self):
        config = deepcopy(self.CONFIG)
        config.get("pattern").update({"target_field": "dotted.message"})
        self.object = Factory.create({"test instance": config}, self.logger)
        assert self.object.metrics.number_of_processed_events == 0
        document = {
            "winlog": {"channel": "System", "provider_name": "Test", "event_id": 123},
            "dotted": {"message": "foo"},
        }

        self.object.process(document)

        assert document.get("dotted")
        assert document["dotted"].get("message")
        assert document["dotted"]["message"] == "Test %1 Test %2"

    def test_replace_non_existing_dotted_message_via_template(self):
        config = deepcopy(self.CONFIG)
        config.get("pattern").update({"target_field": "dotted.message"})
        self.object = Factory.create({"test instance": config}, self.logger)
        assert self.object.metrics.number_of_processed_events == 0
        document = {"winlog": {"channel": "System", "provider_name": "Test", "event_id": 123}}

        self.object.process(document)

        assert document.get("dotted")
        assert document["dotted"].get("message")
        assert document["dotted"]["message"] == "Test %1 Test %2"

    def test_replace_partly_existing_dotted_message_via_template(self):
        config = deepcopy(self.CONFIG)
        config.get("pattern").update({"target_field": "dotted.message"})
        self.object = Factory.create({"test instance": config}, self.logger)
        assert self.object.metrics.number_of_processed_events == 0
        document = {
            "winlog": {"channel": "System", "provider_name": "Test", "event_id": 123},
            "dotted": {"bar": "foo"},
        }

        self.object.process(document)

        assert document.get("dotted")
        assert document["dotted"].get("message")
        assert document["dotted"]["message"] == "Test %1 Test %2"
        assert document["dotted"]["bar"] == "foo"

    def test_replace_existing_dotted_message_dict_via_template(self):
        config = deepcopy(self.CONFIG)
        config.get("pattern").update({"target_field": "dotted.message"})
        self.object = Factory.create({"test instance": config}, self.logger)
        assert self.object.metrics.number_of_processed_events == 0
        document = {
            "winlog": {"channel": "System", "provider_name": "Test", "event_id": 123},
            "dotted": {"message": {"foo": "bar"}},
        }

        self.object.process(document)

        assert document.get("dotted")
        assert document["dotted"].get("message")
        assert document["dotted"]["message"] == "Test %1 Test %2"

    def test_replace_incompatible_existing_dotted_message_parent_via_template(self):
        config = deepcopy(self.CONFIG)
        config.get("pattern").update({"target_field": "dotted.message"})
        self.object = Factory.create({"test instance": config}, self.logger)
        assert self.object.metrics.number_of_processed_events == 0
        document = {
            "winlog": {"channel": "System", "provider_name": "Test", "event_id": 123},
            "dotted": "foo",
        }

        with pytest.raises(
            TemplateReplacerError,
            match="Parent field 'dotted' of target field 'dotted.message' exists "
            "and is not a dict!",
        ):
            self.object.process(document)

    def test_replace_fails_with_invalid_template(self):
        config = deepcopy(self.CONFIG)
        config.update(
            {"template": "tests/testdata/unit/template_replacer/replacer_template_invalid.yml"}
        )
        with pytest.raises(TemplateReplacerError, match="Not enough delimiters"):
            Factory.create({"test instance": config}, self.logger)
