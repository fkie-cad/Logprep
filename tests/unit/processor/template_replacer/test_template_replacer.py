from logging import getLogger

import pytest

pytest.importorskip("logprep.processor.template_replacer")

from logprep.processor.template_replacer.factory import TemplateReplacerFactory
from logprep.processor.template_replacer.processor import TemplateReplacerError

logger = getLogger()
rules_dir = "tests/testdata/unit/template_replacer/rules"
replacer_template = "tests/testdata/unit/template_replacer/replacer_template.yml"
replacer_template_invalid = "tests/testdata/unit/template_replacer/replacer_template_invalid.yml"


@pytest.fixture()
def template_replacer():
    config = {
        "type": "template_replacer",
        "rules": [rules_dir],
        "template": replacer_template,
        "pattern": {
            "delimiter": "-",
            "fields": ["winlog.channel", "winlog.provider_name", "winlog.event_id"],
            "allowed_delimiter_field": "winlog.provider_name",
            "target_field": "message",
        },
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }
    template_replacer = TemplateReplacerFactory.create("test-template-replacer", config, logger)
    return template_replacer


@pytest.fixture()
def template_replacer_dotted_field():
    config = {
        "type": "template_replacer",
        "rules": [rules_dir],
        "template": replacer_template,
        "pattern": {
            "delimiter": "-",
            "fields": ["winlog.channel", "winlog.provider_name", "winlog.event_id"],
            "allowed_delimiter_field": "winlog.provider_name",
            "target_field": "dotted.message",
        },
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }
    template_replacer = TemplateReplacerFactory.create("test-template-replacer", config, logger)
    return template_replacer


class TestWinMessageReplacer:
    def test_replace_message_via_template(self, template_replacer):
        assert template_replacer.ps.processed_count == 0
        document = {
            "winlog": {"channel": "System", "provider_name": "Test", "event_id": 123},
            "message": "foo",
        }

        template_replacer.process(document)

        assert document.get("message")
        assert document["message"] == "Test %1 Test %2"

    def test_replace_non_existing_message_via_template(self, template_replacer):
        assert template_replacer.ps.processed_count == 0
        document = {"winlog": {"channel": "System", "provider_name": "Test", "event_id": 123}}

        template_replacer.process(document)

        assert document.get("message") is None

    def test_replace_dotted_message_via_template(self, template_replacer_dotted_field):
        assert template_replacer_dotted_field.ps.processed_count == 0
        document = {
            "winlog": {"channel": "System", "provider_name": "Test", "event_id": 123},
            "dotted": {"message": "foo"},
        }

        template_replacer_dotted_field.process(document)

        assert document.get("dotted")
        assert document["dotted"].get("message")
        assert document["dotted"]["message"] == "Test %1 Test %2"

    def test_replace_with_additional_hyphen(self, template_replacer):
        assert template_replacer.ps.processed_count == 0
        document = {
            "winlog": {"channel": "System", "provider_name": "Test-Test", "event_id": 123},
            "message": "foo",
        }

        template_replacer.process(document)

        assert document.get("message")
        assert document["message"] == "Test %1 Test %2 Test %3"

    def test_replace_fails_because_it_does_not_map_to_anything(self, template_replacer):
        assert template_replacer.ps.processed_count == 0

        document = {
            "winlog": {"channel": "System", "provider_name": "Test-Test", "event_id": 923},
            "message": "foo",
        }
        template_replacer.process(document)
        assert document.get("message") == "foo"

        document = {
            "winlog": {"channel": "System", "provider_name": "Test-Test-No", "event_id": 123},
            "message": "foo",
        }
        template_replacer.process(document)
        assert document.get("message") == "foo"

    def test_replace_fails_with_invalid_template(self):
        config = {
            "type": "template_replacer",
            "rules": [rules_dir],
            "template": replacer_template_invalid,
            "pattern": {
                "delimiter": "-",
                "fields": ["winlog.channel", "winlog.provider_name", "winlog.event_id"],
                "allowed_delimiter_field": "winlog.provider_name",
                "target_field": "message",
            },
            "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
        }

        with pytest.raises(TemplateReplacerError, match="Not enough delimiters"):
            TemplateReplacerFactory.create("test-template-replacer", config, logger)
