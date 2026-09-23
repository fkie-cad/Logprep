# pylint: disable=missing-module-docstring
from copy import deepcopy

import pytest

from logprep.factory import Factory
from logprep.processor.base.exceptions import FieldExistsWarning
from logprep.processor.template_replacer.processor import TemplateReplacerError
from tests.conftest import normalize_test_cases
from tests.unit.processor.base import BaseProcessorTestCase

# example_test_cases = []
# RULE, EVENT, EXPECTED, CONTEXT
test_cases = normalize_test_cases(
    # *example_test_cases,
    pytest.param(
        {
            "filter": "winlog.provider_name AND winlog.event_id",
            "template_replacer": {},
            "description": "",
        },
        {
            "winlog": {"channel": "System", "provider_name": "Test", "event_id": 123},
            "message": "foo",
        },
        {
            "winlog": {"channel": "System", "provider_name": "Test", "event_id": 123},
            "message": "Test %1 Test %2",
        },
        id="test_replace_message_via_template",
    ),
    pytest.param(
        {
            "filter": "winlog.provider_name AND winlog.event_id",
            "template_replacer": {},
            "description": "",
        },
        {
            "winlog": {"channel": "System", "provider_name": "Test", "event_id": 123},
            "message": "foo",
        },
        {
            "winlog": {"channel": "System", "provider_name": "Test", "event_id": 123},
            "message": "Test %1 Test %2",
        },
        id="test_replace_message_via_template",
    ),
    pytest.param(
        {
            "filter": "winlog.provider_name AND winlog.event_id",
            "template_replacer": {},
            "description": "",
        },
        {
            "winlog": {"channel": "Dotted.System", "provider_name": ".Test", "event_id": "123."},
            "message": "foo",
        },
        {
            "winlog": {"channel": "Dotted.System", "provider_name": ".Test", "event_id": "123."},
            "message": "Test %1 Test %2",
        },
        id="test_replace_message_with_dots_via_template",
    ),
    pytest.param(
        {
            "filter": "winlog.provider_name AND winlog.event_id",
            "template_replacer": {},
            "description": "",
        },
        {"winlog": {"channel": "System", "provider_name": "Test", "event_id": 123}},
        {
            "winlog": {"channel": "System", "provider_name": "Test", "event_id": 123},
            "message": "Test %1 Test %2",
        },
        id="test_replace_non_existing_message_via_template",
    ),
    pytest.param(
        {
            "filter": "winlog.provider_name AND winlog.event_id",
            "template_replacer": {},
            "description": "",
        },
        {
            "winlog": {"channel": "System", "provider_name": "Test-Test", "event_id": 123},
            "message": "foo",
        },
        {
            "winlog": {"channel": "System", "provider_name": "Test-Test", "event_id": 123},
            "message": "Test %1 Test %2 Test %3",
        },
        id="test_replace_with_additional_hyphen",
    ),
    pytest.param(
        {
            "filter": "winlog.provider_name AND winlog.event_id",
            "template_replacer": {},
            "description": "",
        },
        {
            "winlog": {"channel": "System", "provider_name": "Test-Test", "event_id": 923},
            "message": "foo",
        },
        {
            "winlog": {"channel": "System", "provider_name": "Test-Test", "event_id": 923},
            "message": "foo",
        },
        id="test_replace_fails_because_it_does_not_map_to_anything_1",
    ),
    pytest.param(
        {
            "filter": "winlog.provider_name AND winlog.event_id",
            "template_replacer": {},
            "description": "",
        },
        {
            "winlog": {"channel": "System", "provider_name": "Test-Test-No", "event_id": 123},
            "message": "foo",
        },
        {
            "winlog": {"channel": "System", "provider_name": "Test-Test-No", "event_id": 123},
            "message": "foo",
        },
        id="test_replace_fails_because_it_does_not_map_to_anything_2",
    ),
)


class TestTemplateReplacer(BaseProcessorTestCase):
    CONFIG = {
        "type": "template_replacer",
        "rules": ["tests/testdata/unit/template_replacer/rules"],
        "template": "tests/testdata/unit/template_replacer/replacer_template.yml",
        "pattern": {
            "delimiter": "-",
            "fields": ["winlog.channel", "winlog.provider_name", "winlog.event_id"],
            "allowed_delimiter_field": "winlog.provider_name",
            "target_field": "message",
        },
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }

    def setup_method(self):
        super().setup_method()
        self.object.setup()

    @pytest.mark.parametrize(["rule", "event", "expected", "context"], test_cases)
    def test_testcases(self, rule, event, expected, context, provision_context):
        provision_context(context)
        self._load_rule(rule)
        self.object.process(event)
        assert event == expected

    def test_replace_dotted_message_via_template(self):
        config = deepcopy(self.CONFIG)
        config.get("pattern").update({"target_field": "dotted.message"})
        template_replacer = self._create_template_replacer(config)
        document = {
            "winlog": {"channel": "System", "provider_name": "Test", "event_id": 123},
            "dotted": {"message": "foo"},
        }

        template_replacer.process(document)

        assert document.get("dotted")
        assert document["dotted"].get("message")
        assert document["dotted"]["message"] == "Test %1 Test %2"

    def test_replace_non_existing_dotted_message_via_template(self):
        config = deepcopy(self.CONFIG)
        config.get("pattern").update({"target_field": "dotted.message"})
        template_replacer = self._create_template_replacer(config)
        document = {"winlog": {"channel": "System", "provider_name": "Test", "event_id": 123}}

        template_replacer.process(document)

        assert document.get("dotted")
        assert document["dotted"].get("message")
        assert document["dotted"]["message"] == "Test %1 Test %2"

    def test_replace_partly_existing_dotted_message_via_template(self):
        config = deepcopy(self.CONFIG)
        config.get("pattern").update({"target_field": "dotted.message"})
        template_replacer = self._create_template_replacer(config)
        document = {
            "winlog": {"channel": "System", "provider_name": "Test", "event_id": 123},
            "dotted": {"bar": "foo"},
        }

        template_replacer.process(document)

        assert document.get("dotted")
        assert document["dotted"].get("message")
        assert document["dotted"]["message"] == "Test %1 Test %2"
        assert document["dotted"]["bar"] == "foo"

    def test_replace_existing_dotted_message_dict_via_template(self):
        config = deepcopy(self.CONFIG)
        config.get("pattern").update({"target_field": "dotted.message"})
        template_replacer = self._create_template_replacer(config)
        document = {
            "winlog": {"channel": "System", "provider_name": "Test", "event_id": 123},
            "dotted": {"message": {"foo": "bar"}},
        }

        template_replacer.process(document)

        assert document.get("dotted")
        assert document["dotted"].get("message")
        assert document["dotted"]["message"] == "Test %1 Test %2"

    def test_replace_incompatible_existing_dotted_message_parent_via_template(self):
        config = deepcopy(self.CONFIG)
        config.get("pattern").update({"target_field": "dotted.message"})
        template_replacer = self._create_template_replacer(config)
        document = {
            "winlog": {"channel": "System", "provider_name": "Test", "event_id": 123},
            "dotted": "foo",
        }
        result = template_replacer.process(document)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)

    def test_replace_fails_with_invalid_template(self):
        config = deepcopy(self.CONFIG)
        config.update(
            {"template": "tests/testdata/unit/template_replacer/replacer_template_invalid.yml"}
        )
        with pytest.raises(TemplateReplacerError, match="Not enough delimiters"):
            self._create_template_replacer(config)

    def _create_template_replacer(self, config):
        template_replacer = Factory.create({"test instance": config})
        template_replacer.setup()
        return template_replacer
