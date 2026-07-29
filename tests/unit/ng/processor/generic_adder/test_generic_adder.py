# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments

import re
from copy import deepcopy

import pytest
import responses

from logprep.factory import Factory
from logprep.ng.abc.event import InputMeta, LogEvent
from logprep.ng.processor.generic_adder.processor import GenericAdder
from logprep.processor.base.exceptions import (
    InvalidRuleDefinitionError,
    ProcessingWarning,
)
from logprep.util.getter import HttpGetter, RefreshableGetter
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.generic_adder.test_generic_adder import (
    failure_test_cases as non_ng_failure_test_cases,
)
from tests.unit.processor.generic_adder.test_generic_adder import (
    test_cases as non_ng_test_cases,
)

RULES_DIR_MISSING = "tests/testdata/unit/generic_adder/rules_missing"
RULES_DIR_INVALID = "tests/testdata/unit/generic_adder/rules_invalid"
RULES_DIR_FIRST_EXISTING = "tests/testdata/unit/generic_adder/rules_first_existing"


test_cases = deepcopy(non_ng_test_cases)
failure_test_cases = deepcopy(non_ng_failure_test_cases)


class TestGenericAdder(BaseProcessorTestCase[GenericAdder]):

    CONFIG = {
        "type": "generic_adder",
        "rules": ["tests/testdata/unit/generic_adder/rules"],
    }

    @pytest.mark.parametrize("rule, event, expected", test_cases)
    async def test_generic_adder_testcases(self, rule, event, expected):
        await self._load_rule(rule)
        await self.object.setup()
        log_event = LogEvent(event, original=b"", input_meta=InputMeta())
        await self.object.process(log_event)
        assert event == expected

    @pytest.mark.parametrize("rule, event, expected, error_message", failure_test_cases)
    async def test_generic_adder_testcases_failure_handling(
        self, rule, event, expected, error_message
    ):
        await self._load_rule(rule)
        log_event = LogEvent(event, original=b"", input_meta=InputMeta())
        result = await self.object.process(log_event)
        assert len(result.warnings) == 1
        assert re.match(rf".*FieldExistsWarning.*{error_message}", str(result.warnings[0]))
        assert event == expected

    async def test_add_generic_fields_from_file_missing_and_existing_with_all_required(self):
        with pytest.raises(InvalidRuleDefinitionError, match=r"files do not exist"):
            config = deepcopy(self.CONFIG)
            config["rules"] = [RULES_DIR_MISSING]
            configuration = {"test_instance_name": config}
            await Factory.create(configuration).setup()

    async def test_add_generic_fields_from_file_invalid(self):
        with pytest.raises(
            InvalidRuleDefinitionError,
            match=r"must be a dictionary with string values",
        ):
            config = deepcopy(self.CONFIG)
            config["rules"] = [RULES_DIR_INVALID]
            configuration = {"test processor": config}
            await Factory.create(configuration).setup()

    async def test_add_only_copies(self):
        instance = self._create_test_instance(
            {
                "type": "generic_adder",
                "rules": [
                    {
                        "filter": "*",
                        "generic_adder": {
                            "add": {
                                "some_list_field": ["some_value"],
                                "some_dict_field": {"some_key": "some_value"},
                            }
                        },
                    }
                ],
            }
        )

        event = {}
        log_event = LogEvent(event, original=b"", input_meta=InputMeta())
        await instance.process(log_event)

        rule_add = instance.rules[0].add({})

        assert event["some_list_field"] == ["some_value"]
        assert event["some_list_field"] is not rule_add["some_list_field"], "only copies in events"

        assert event["some_dict_field"] == {"some_key": "some_value"}
        assert event["some_dict_field"] is not rule_add["some_dict_field"], "only copies in events"

    @responses.activate
    async def test_adds_response_from_event_templated_url(self):
        resolved_url = "https://values.example/acme"
        response_content = {"user": {"name": "Alice"}, "risk": {"score": 7}}
        responses.add(responses.GET, resolved_url, json=response_content)
        processor = self._create_test_instance(
            {
                "rules": [
                    {
                        "filter": "*",
                        "generic_adder": {
                            "add_from_url": {
                                "url": "https://values.example/${tenant.id}",
                                "target_field": "enrichment",
                            }
                        },
                    }
                ]
            }
        )
        await processor.setup()
        event = {"tenant": {"id": "acme"}}

        result = await processor.process(LogEvent(event, original=b"", input_meta=InputMeta()))

        assert result.errors == []
        assert event == {
            "tenant": {"id": "acme"},
            "enrichment": response_content,
        }
        assert responses.calls[0].request.url == resolved_url

    @responses.activate
    async def test_dynamic_url_failure_is_event_scoped(self):
        failed_url = "https://values.example/acme"
        successful_url = "https://values.example/beta"
        responses.add(responses.GET, failed_url, status=500)
        responses.add(responses.GET, successful_url, json={"risk": {"score": 7}})
        RefreshableGetter.reset()
        processor = self._create_test_instance(
            {
                "rules": [
                    {
                        "filter": "*",
                        "generic_adder": {
                            "add_from_url": {
                                "url": "https://values.example/${tenant}",
                                "target_field": "enrichment",
                            }
                        },
                    }
                ]
            }
        )
        await processor.setup()
        rule = processor.rules[0]
        failed_event = {"tenant": "acme"}
        successful_event = {"tenant": "beta"}

        failed_result = await processor.process(
            LogEvent(failed_event, original=b"", input_meta=InputMeta())
        )
        successful_result = await processor.process(
            LogEvent(successful_event, original=b"", input_meta=InputMeta())
        )

        assert failed_result.errors == []
        assert len(failed_result.warnings) == 1
        assert isinstance(failed_result.warnings[0], ProcessingWarning)
        assert failed_event == {
            "tenant": "acme",
            "tags": ["_generic_adder_failure"],
        }
        assert rule.data_error is None
        assert len(HttpGetter._target_to_data_caches[failed_url].callbacks) == 0
        assert len(HttpGetter._target_to_data_caches[failed_url].cleanup_callbacks) == 0

        assert successful_result.errors == []
        assert successful_result.warnings == []
        assert successful_event == {
            "tenant": "beta",
            "enrichment": {"risk": {"score": 7}},
        }

    async def test_missing_dynamic_url_field_adds_warning_without_clearing_event(self):
        processor = self._create_test_instance(
            {
                "rules": [
                    {
                        "filter": "*",
                        "generic_adder": {
                            "add_from_url": {
                                "url": "https://values.example/${tenant.id}",
                                "target_field": "enrichment",
                            }
                        },
                    }
                ]
            }
        )
        await processor.setup()
        event = {"message": "preserved"}

        result = await processor.process(LogEvent(event, original=b"", input_meta=InputMeta()))

        assert result.errors == []
        assert len(result.warnings) == 1
        assert "missing event field 'tenant.id'" in str(result.warnings[0])
        assert event == {
            "message": "preserved",
            "tags": ["_generic_adder_failure"],
        }
