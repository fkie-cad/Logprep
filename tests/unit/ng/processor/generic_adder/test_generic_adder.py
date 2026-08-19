# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments

import re
from copy import deepcopy

import pytest
from aiohttp import web

from logprep.factory import Factory
from logprep.ng.abc.event import InputMeta, LogEvent
from logprep.ng.processor.generic_adder.processor import GenericAdder
from logprep.ng.util.getter import HttpGetter, RefreshableGetter
from logprep.processor.base.exceptions import (
    InvalidRuleDefinitionError,
    ProcessingWarning,
)
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.generic_adder.test_generic_adder import (
    dynamic_uri_failure_test_cases as non_ng_dynamic_uri_failure_test_cases,
)
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
dynamic_uri_failure_test_cases = deepcopy(non_ng_dynamic_uri_failure_test_cases)


class TestGenericAdder(BaseProcessorTestCase[GenericAdder]):

    CONFIG = {
        "type": "generic_adder",
        "rules": ["tests/testdata/unit/generic_adder/rules"],
    }

    @pytest.fixture(autouse=True)
    def reset_refreshable_getters(self):
        RefreshableGetter.reset()
        yield
        RefreshableGetter.reset()

    @pytest.mark.parametrize("rule, event, expected", test_cases)
    async def test_generic_adder_testcases(self, rule, event, expected):
        config = deepcopy(self.CONFIG)
        config["rules"] = [rule]

        processor = Factory.create({"test instance": config})
        log_event = LogEvent(event, original=b"", input_meta=InputMeta())

        await processor.setup()
        await processor.process(log_event)

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

    @pytest.mark.parametrize("rule, event, error_message", dynamic_uri_failure_test_cases)
    async def test_dynamic_uri_failure_handling(self, rule, event, error_message):
        config = deepcopy(self.CONFIG)
        config["rules"] = [rule]
        self.object = Factory.create({"test instance": config})

        log_event = LogEvent(event, original=b"", input_meta=InputMeta())

        await self.object.setup()
        result = await self.object.process(log_event)

        assert result.errors == []
        assert len(result.warnings) == 1
        assert error_message in str(result.warnings[0])
        assert event["tags"] == ["_generic_adder_failure"]

    async def test_add_generic_fields_from_file_missing_and_existing_with_all_required(self):
        with pytest.raises(InvalidRuleDefinitionError, match=r"Could not load generic_adder URI"):
            config = deepcopy(self.CONFIG)
            config["rules"] = [RULES_DIR_MISSING]
            configuration = {"test_instance_name": config}
            instance = Factory.create(configuration)
            await instance.setup()

    async def test_add_generic_fields_from_file_invalid(self):
        config = deepcopy(self.CONFIG)
        config["rules"] = [RULES_DIR_INVALID]
        configuration = {"test processor": config}
        processor = Factory.create(configuration)
        await processor.setup()

        event = {"add_list_invalid_generic_test": True}
        result = await processor.process(LogEvent(event, original=b"", input_meta=InputMeta()))

        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], ProcessingWarning)
        assert "without target_field must contain a mapping" in str(result.warnings[0])

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
        await instance.setup()
        await instance.process(log_event)

        rule_add = await instance.rules[0].add({})

        assert event["some_list_field"] == ["some_value"]
        assert event["some_list_field"] is not rule_add["some_list_field"], "only copies in events"

        assert event["some_dict_field"] == {"some_key": "some_value"}
        assert event["some_dict_field"] is not rule_add["some_dict_field"], "only copies in events"

    async def test_adds_response_from_event_templated_url(self, aiohttp_server):
        response_content = {
            "user": {"name": "Alice"},
            "risk": {"score": 7},
        }

        async def handler(request: web.Request) -> web.Response:
            assert request.match_info["tenant_id"] == "acme"
            return web.json_response(response_content)

        app = web.Application()
        app.router.add_get("/{tenant_id}", handler)
        server = await aiohttp_server(app)

        base_url = str(server.make_url("/")).rstrip("/")
        uri = f"{base_url}/${{tenant.id}}"

        processor = self._create_test_instance(
            {
                "rules": [
                    {
                        "filter": "*",
                        "generic_adder": {
                            "add_from_uri": {
                                "uri": uri,
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

    async def test_shutdown_removes_dynamic_uri_callbacks(self, aiohttp_server):
        async def handler(_: web.Request) -> web.Response:
            return web.json_response({"value": 1})

        app = web.Application()
        app.router.add_get("/acme", handler)
        server = await aiohttp_server(app)

        base_url = str(server.make_url("/")).rstrip("/")
        url = f"{base_url}/acme"

        processor = self._create_test_instance(
            {
                "rules": [
                    {
                        "filter": "*",
                        "generic_adder": {
                            "add_from_uri": {
                                "uri": f"{base_url}/${{tenant}}",
                                "target_field": "enrichment",
                            }
                        },
                    }
                ]
            }
        )

        await processor.setup()

        event = {"tenant": "acme"}

        await processor.process(LogEvent(event, original=b"", input_meta=InputMeta()))

        shared = HttpGetter._target_to_data_caches[url]

        assert len(shared.callbacks) == 1
        assert len(shared.cleanup_callbacks) == 1

        await processor.shut_down()

        assert shared.callbacks == []
        assert shared.cleanup_callbacks == []

    async def test_dynamic_url_failure_is_event_scoped(self, aiohttp_server):
        async def handler(request: web.Request) -> web.Response:
            tenant = request.match_info["tenant"]

            if tenant == "acme":
                return web.Response(status=500)

            return web.json_response({"risk": {"score": 7}})

        app = web.Application()
        app.router.add_get("/{tenant}", handler)
        server = await aiohttp_server(app)

        base_url = str(server.make_url("/")).rstrip("/")
        failed_url = f"{base_url}/acme"
        successful_url = f"{base_url}/beta"

        processor = self._create_test_instance(
            {
                "rules": [
                    {
                        "filter": "*",
                        "generic_adder": {
                            "add_from_uri": {
                                "uri": f"{base_url}/${{tenant}}",
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
        assert rule.data_error is None
        assert len(HttpGetter._target_to_data_caches[successful_url].callbacks) == 1
        assert len(HttpGetter._target_to_data_caches[successful_url].cleanup_callbacks) == 1

    async def test_missing_dynamic_url_field_adds_warning_without_clearing_event(self):
        processor = self._create_test_instance(
            {
                "rules": [
                    {
                        "filter": "*",
                        "generic_adder": {
                            "add_from_uri": {
                                "uri": "https://values.example/${tenant.id}",
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

    async def test_has_async_io(self):
        assert await self.object.has_asyncio() is True
