# pylint: disable=protected-access
# pylint: disable=missing-docstring

from copy import deepcopy

import pytest

from logprep.factory import Factory
from logprep.ng.abc.event import InputMeta, LogEvent
from logprep.ng.processor.domain_label_extractor.processor import DomainLabelExtractor
from logprep.processor.base.exceptions import (
    FieldExistsWarning,
    ProcessingCriticalError,
)
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.domain_label_extractor.test_domain_label_extractor import (
    multi_rule_test_cases as non_ng_multi_rule_test_cases,
)
from tests.unit.processor.domain_label_extractor.test_domain_label_extractor import (
    test_cases as non_ng_test_cases,
)

test_cases = deepcopy(non_ng_test_cases)
multi_rule_test_cases = deepcopy(non_ng_multi_rule_test_cases)


class TestDomainLabelExtractor(BaseProcessorTestCase[DomainLabelExtractor]):
    CONFIG = {
        "type": "domain_label_extractor",
        "rules": ["tests/testdata/unit/domain_label_extractor/rules"],
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }

    @pytest.mark.parametrize(["rule", "document", "expected_output"], test_cases)
    async def test_domain_extractor(self, rule, document, expected_output):
        await self._load_rule(rule)
        await self.object.setup()
        event = LogEvent(deepcopy(document), original=b"", input_meta=InputMeta())
        result = await self.object.process(event)
        assert result.data == expected_output

    @pytest.mark.parametrize(["document", "expected_output"], multi_rule_test_cases)
    async def test_domain_extractor_multi_rule(self, document, expected_output):
        event = LogEvent(deepcopy(document), original=b"", input_meta=InputMeta())

        result = await self.object.process(event)
        assert result.data == expected_output

    async def test_new_non_default_tagging_field(self):
        config = {
            "Test DomainLabelExtractor Name": {
                "type": "domain_label_extractor",
                "rules": ["tests/testdata/unit/domain_label_extractor/rules"],
                "tagging_field_name": "special_tags",
                "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
            }
        }

        domain_label_extractor = Factory.create(configuration=config)
        document = {"url": {"domain": "http://["}}
        expected_output = {
            "url": {"domain": "http://["},
            "special_tags": ["invalid_domain_in_url_domain"],
        }
        log_event = LogEvent(document, original=b"", input_meta=InputMeta())
        await domain_label_extractor.process(log_event)
        assert log_event.data == expected_output

    async def test_append_to_non_default_tagging_field(self):
        config = {
            "Test DomainLabelExtractor Name": {
                "type": "domain_label_extractor",
                "rules": ["tests/testdata/unit/domain_label_extractor/rules"],
                "tagging_field_name": "special_tags",
                "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
            }
        }

        domain_label_extractor = Factory.create(config)
        document = {"url": {"domain": "http://["}, "special_tags": ["source"]}

        expected_output = {
            "url": {"domain": "http://["},
            "special_tags": ["source", "invalid_domain_in_url_domain"],
        }
        log_event = LogEvent(document, original=b"", input_meta=InputMeta())

        await domain_label_extractor.process(log_event)
        assert log_event.data == expected_output

    async def test_domain_extraction_with_existing_output_field(self):
        document = {"url": {"domain": "test.domain.de", "subdomain": "exists already"}}
        event = LogEvent(document, original=b"test_message", input_meta=InputMeta())

        result = await self.object.process(event)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)

    async def test_raises_on_invalid_tagging_field(self):
        config = {
            "Test DomainLabelExtractor Name": {
                "type": "domain_label_extractor",
                "rules": ["tests/testdata/unit/domain_label_extractor/rules"],
                "tagging_field_name": "special_tags",
                "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
            }
        }

        domain_label_extractor = Factory.create(config)
        await domain_label_extractor.setup()
        document = {"url": {"domain": "http://["}, "special_tags": False}
        event = LogEvent(document, original=b"", input_meta=InputMeta())

        result = await domain_label_extractor.process(event)
        assert len(result.errors) == 1
        assert isinstance(result.errors[0], ProcessingCriticalError)

    async def test_raises_field_exists_warning_if_target_field_exits(self):
        document = {"url": {"domain": "test.domain.de", "subdomain": "exists already"}}
        expected = {
            "tags": ["_domain_label_extractor_failure"],
            "url": {
                "domain": "test.domain.de",
                "subdomain": "exists already",
                "registered_domain": "domain.de",
                "top_level_domain": "de",
            },
        }
        event = LogEvent(document, original=b"test_message", input_meta=InputMeta())

        result = await self.object.process(event)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)
        assert result.data == expected
