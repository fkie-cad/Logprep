# pylint: disable=missing-module-docstring
from copy import deepcopy

import pytest

from logprep.factory import Factory
from logprep.ng.event.log_event import LogEvent
from logprep.ng.processor.template_replacer.processor import (
    TemplateReplacer,
    TemplateReplacerError,
)
from logprep.processor.base.exceptions import FieldExistsWarning
from tests.unit.ng.processor.base import BaseProcessorTestCase


class TestTemplateReplacer(BaseProcessorTestCase[TemplateReplacer]):
    CONFIG = {
        "type": "ng_template_replacer",
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

    async def async_setup(self):
        await super().async_setup()
        await self.object.setup()

    async def test_replace_message_via_template(self):
        document = {
            "winlog": {"channel": "System", "provider_name": "Test", "event_id": 123},
            "message": "foo",
        }
        log_event = LogEvent(document, original=b"")

        await self.object.process(log_event)

        assert log_event.data.get("message")
        assert log_event.data["message"] == "Test %1 Test %2"

    async def test_replace_message_with_dots_via_template(self):
        document = {
            "winlog": {"channel": "Dotted.System", "provider_name": ".Test", "event_id": "123."},
            "message": "foo",
        }
        log_event = LogEvent(document, original=b"")

        await self.object.process(log_event)

        assert log_event.data.get("message")
        assert log_event.data["message"] == "Test %1 Test %2"

    async def test_replace_non_existing_message_via_template(self):
        document = {"winlog": {"channel": "System", "provider_name": "Test", "event_id": 123}}
        log_event = LogEvent(document, original=b"")

        await self.object.process(log_event)

        assert log_event.data.get("message")
        assert log_event.data["message"] == "Test %1 Test %2"

    async def test_replace_with_additional_hyphen(self):
        document = {
            "winlog": {"channel": "System", "provider_name": "Test-Test", "event_id": 123},
            "message": "foo",
        }
        log_event = LogEvent(document, original=b"")

        await self.object.process(log_event)

        assert log_event.data.get("message")
        assert log_event.data["message"] == "Test %1 Test %2 Test %3"

    async def test_replace_fails_because_it_does_not_map_to_anything(self):
        document = {
            "winlog": {"channel": "System", "provider_name": "Test-Test", "event_id": 923},
            "message": "foo",
        }
        log_event = LogEvent(document, original=b"")
        await self.object.process(log_event)
        assert log_event.data.get("message") == "foo"

        document = {
            "winlog": {"channel": "System", "provider_name": "Test-Test-No", "event_id": 123},
            "message": "foo",
        }
        log_event = LogEvent(document, original=b"")
        await self.object.process(log_event)
        assert log_event.data.get("message") == "foo"

    async def test_replace_dotted_message_via_template(self):
        config = deepcopy(self.CONFIG)
        config.get("pattern").update({"target_field": "dotted.message"})
        template_replacer = await self._create_template_replacer(config)
        document = {
            "winlog": {"channel": "System", "provider_name": "Test", "event_id": 123},
            "dotted": {"message": "foo"},
        }
        log_event = LogEvent(document, original=b"")

        await template_replacer.process(log_event)

        assert log_event.data.get("dotted")
        assert log_event.data["dotted"].get("message")
        assert log_event.data["dotted"]["message"] == "Test %1 Test %2"

    async def test_replace_non_existing_dotted_message_via_template(self):
        config = deepcopy(self.CONFIG)
        config.get("pattern").update({"target_field": "dotted.message"})
        template_replacer = await self._create_template_replacer(config)
        document = {"winlog": {"channel": "System", "provider_name": "Test", "event_id": 123}}
        log_event = LogEvent(document, original=b"")

        await template_replacer.process(log_event)

        assert log_event.data.get("dotted")
        assert log_event.data["dotted"].get("message")
        assert log_event.data["dotted"]["message"] == "Test %1 Test %2"

    async def test_replace_partly_existing_dotted_message_via_template(self):
        config = deepcopy(self.CONFIG)
        config.get("pattern").update({"target_field": "dotted.message"})
        template_replacer = await self._create_template_replacer(config)
        document = {
            "winlog": {"channel": "System", "provider_name": "Test", "event_id": 123},
            "dotted": {"bar": "foo"},
        }
        log_event = LogEvent(document, original=b"")

        await template_replacer.process(log_event)

        assert log_event.data.get("dotted")
        assert log_event.data["dotted"].get("message")
        assert log_event.data["dotted"]["message"] == "Test %1 Test %2"
        assert log_event.data["dotted"]["bar"] == "foo"

    async def test_replace_existing_dotted_message_dict_via_template(self):
        config = deepcopy(self.CONFIG)
        config.get("pattern").update({"target_field": "dotted.message"})
        template_replacer = await self._create_template_replacer(config)
        document = {
            "winlog": {"channel": "System", "provider_name": "Test", "event_id": 123},
            "dotted": {"message": {"foo": "bar"}},
        }
        log_event = LogEvent(document, original=b"")

        await template_replacer.process(log_event)

        assert log_event.data.get("dotted")
        assert log_event.data["dotted"].get("message")
        assert log_event.data["dotted"]["message"] == "Test %1 Test %2"

    async def test_replace_incompatible_existing_dotted_message_parent_via_template(self):
        config = deepcopy(self.CONFIG)
        config.get("pattern").update({"target_field": "dotted.message"})
        template_replacer = await self._create_template_replacer(config)
        document = {
            "winlog": {"channel": "System", "provider_name": "Test", "event_id": 123},
            "dotted": "foo",
        }
        log_event = LogEvent(document, original=b"")
        result = await template_replacer.process(log_event)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)

    async def test_replace_fails_with_invalid_template(self):
        config = deepcopy(self.CONFIG)
        config.update(
            {"template": "tests/testdata/unit/template_replacer/replacer_template_invalid.yml"}
        )
        with pytest.raises(TemplateReplacerError, match="Not enough delimiters"):
            await self._create_template_replacer(config)

    async def _create_template_replacer(self, config):
        template_replacer = Factory.create({"test instance": config})
        await template_replacer.setup()
        return template_replacer
