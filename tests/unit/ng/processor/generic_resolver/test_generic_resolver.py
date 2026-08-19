# pylint: disable=duplicate-code
# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=wrong-import-position
# pylint: disable=too-many-lines,too-many-arguments,too-many-positional-arguments
import json
from copy import deepcopy
from pathlib import Path

import pytest
from aiohttp import web

from logprep.factory import Factory
from logprep.factory_error import InvalidConfigurationError
from logprep.ng.abc.event import InputMeta, LogEvent
from logprep.ng.processor.generic_resolver.processor import GenericResolver
from logprep.ng.util.getter import HttpGetter
from logprep.processor.base.exceptions import FieldExistsWarning
from logprep.util.async_scheduler import AsyncScheduler
from logprep.util.defaults import ENV_NAME_LOGPREP_GETTER_CONFIG
from tests.conftest import FIELD_VALUE_TEST_CASES, mock_env
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.generic_resolver.test_generic_resolver import (
    failure_test_cases as non_ng_failure_testcases,
)
from tests.unit.processor.generic_resolver.test_generic_resolver import (
    test_cases as non_ng_testcases,
)

test_cases = deepcopy(non_ng_testcases)
failure_test_cases = deepcopy(non_ng_failure_testcases)


class TestGenericResolver(BaseProcessorTestCase[GenericResolver]):
    CONFIG = {
        "type": "generic_resolver",
        "rules": ["tests/testdata/unit/generic_resolver/rules"],
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }

    expected_metrics = [
        "logprep_generic_resolver_new_results",
        "logprep_generic_resolver_cached_results",
        "logprep_generic_resolver_num_cache_entries",
        "logprep_generic_resolver_cache_load",
    ]

    @pytest.mark.parametrize("rule, event, expected, context", test_cases)
    async def test_testcases(
        self,
        rule,
        event,
        expected,
        context,
        provision_context,
        aiohttp_server,
    ):
        config = deepcopy(self.CONFIG)
        rule = deepcopy(rule)

        if config.get("tree_config"):
            config["tree_config"] = str(Path(config["tree_config"]).resolve())

        http_context = {
            path: response
            for path, response in context.items()
            if path.startswith(("http://", "https://"))
        }
        file_context = {
            path: response
            for path, response in context.items()
            if not path.startswith(("http://", "https://"))
        }

        provision_context(file_context)

        if http_context:
            _, response = next(iter(http_context.items()))

            async def handler(_: web.Request) -> web.Response:
                return web.json_response(response["body"])

            app = web.Application()
            app.router.add_get("/resolve-mapping", handler)
            server = await aiohttp_server(app)

            rule["generic_resolver"]["resolve_from_file"]["path"] = str(
                server.make_url("/resolve-mapping")
            )

        config["rules"] = [rule]

        processor = Factory.create({"test instance": config})
        log_event = LogEvent(event, original=b"", input_meta=InputMeta())

        await processor.setup()
        await processor.process(log_event)

        assert log_event.data == expected

    @pytest.mark.parametrize("rule, context, error_message", failure_test_cases)
    async def test_testcases_failure_handling(
        self,
        rule,
        context,
        error_message,
        provision_context,
        aiohttp_server,
    ):
        rule = deepcopy(rule)

        http_context = {
            path: response
            for path, response in context.items()
            if path.startswith(("http://", "https://"))
        }
        file_context = {
            path: response
            for path, response in context.items()
            if not path.startswith(("http://", "https://"))
        }

        if file_context:
            provision_context(file_context)

        if http_context:
            _, response = next(iter(http_context.items()))

            async def handler(_: web.Request) -> web.Response:
                return web.json_response(response["body"])

            app = web.Application()
            app.router.add_get("/resolve-mapping", handler)
            server = await aiohttp_server(app)

            rule["generic_resolver"]["resolve_from_file"]["path"] = str(
                server.make_url("/resolve-mapping")
            )

        with pytest.raises(InvalidConfigurationError, match=error_message):
            await self._load_rule(rule)
            await self.object.setup()

    @pytest.mark.parametrize(["resolve_value"], FIELD_VALUE_TEST_CASES)
    async def test_resolve_not_dotted_field_no_conflict_different_values_match(self, resolve_value):
        await self._load_rule(
            {
                "filter": "to_resolve",
                "generic_resolver": {
                    "field_mapping": {"to_resolve": "resolved"},
                    "resolve_list": {".*HELLO\\d": resolve_value},
                },
            }
        )

        expected = {"to_resolve": "something HELLO1", "resolved": resolve_value}
        document = LogEvent(
            {"to_resolve": "something HELLO1"}, original=b"", input_meta=InputMeta()
        )

        await self.object.setup()
        await self.object.process(document)

        assert document.data == expected

    @pytest.mark.parametrize(["resolve_value"], FIELD_VALUE_TEST_CASES)
    async def test_resolve_not_dotted_field_no_conflict_different_values_match_from_file(
        self, resolve_value, tmp_path
    ):
        resolve_file_path = tmp_path / "rule.json"

        resolve_dict = {"abc": resolve_value}
        expected = {"to_resolve": "abc", "resolved": resolve_value}
        document = LogEvent({"to_resolve": "abc"}, original=b"", input_meta=InputMeta())

        with open(resolve_file_path, mode="w+", encoding="utf8") as stream:
            stream.write(json.dumps(resolve_dict))

        await self._load_rule(
            {
                "filter": "to_resolve",
                "generic_resolver": {
                    "field_mapping": {"to_resolve": "resolved"},
                    "resolve_from_file": {
                        "path": str(resolve_file_path),
                        "pattern": r"(?P<mapping>.+)",
                    },
                },
            }
        )
        await self.object.setup()
        await self.object.process(document)

        assert document.data == expected

    async def test_resolve_dotted_field_no_conflict_match_from_file_and_list_has_conflict(
        self,
    ):
        await self._load_rule(
            {
                "filter": "to_resolve",
                "generic_resolver": {
                    "field_mapping": {"to_resolve": "resolved"},
                    "resolve_from_file": {
                        "path": "tests/testdata/unit/generic_resolver/resolve_mapping.yml",
                        "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                    },
                    "merge_with_target": True,
                },
            }
        )

        expected = {"to_resolve": "12ab34", "resolved": ["ab_server_type"]}
        document = LogEvent({"to_resolve": "12ab34"}, original=b"", input_meta=InputMeta())

        await self.object.setup()
        await self.object.process(document)

        assert document.data == expected

    async def test_resolve_dotted_field_no_conflict_match_from_file_and_list_has_conflict_and_diff_inputs(
        self,
    ):
        await self._load_rule(
            {
                "filter": "to_resolve",
                "generic_resolver": {
                    "field_mapping": {
                        "to_resolve": "resolved",
                        "other_to_resolve": "resolved",
                    },
                    "resolve_from_file": {
                        "path": "tests/testdata/unit/generic_resolver/resolve_mapping.yml",
                        "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                    },
                    "merge_with_target": True,
                },
            }
        )
        document = LogEvent(
            {"to_resolve": "12ab34", "other_to_resolve": "00de11"},
            original=b"",
            input_meta=InputMeta(),
        )
        expected = {
            "to_resolve": "12ab34",
            "other_to_resolve": "00de11",
            "resolved": ["ab_server_type", "de_server_type"],
        }

        await self.object.setup()
        await self.object.process(document)

        assert document.data == expected

    async def test_resolve_from_http(self, tmp_path, aiohttp_server):
        response_contents = [
            {"ab": {"new1": "1"}},
            {"ab": {"new1": "1", "new2": "2"}},
        ]
        request_count = 0

        async def handler(_: web.Request) -> web.Response:
            nonlocal request_count

            content = response_contents[min(request_count, len(response_contents) - 1)]
            request_count += 1

            return web.json_response(content)

        app = web.Application()
        app.router.add_get("/resolve-mapping", handler)
        server = await aiohttp_server(app)

        url = str(server.make_url("/resolve-mapping"))

        getter_file_content = {url: {"refresh_interval": 10}}
        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))

        with mock_env({ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}):
            await self._load_rule(
                {
                    "filter": "to_resolve",
                    "generic_resolver": {
                        "field_mapping": {"to_resolve": "resolved"},
                        "resolve_from_file": {
                            "path": url,
                            "pattern": r"\d*(?P<mapping>[a-z]+)\d*",
                        },
                        "overwrite_target": True,
                    },
                }
            )

            await self.object.setup()

            http_getter = HttpGetter(protocol="http", target=url)
            assert isinstance(http_getter.scheduler, AsyncScheduler)

            expected_1 = {
                "to_resolve": "12ab34",
                "resolved": {"new1": "1"},
            }
            expected_2 = {
                "to_resolve": "12ab34",
                "resolved": {"new1": "1", "new2": "2"},
            }
            document = LogEvent(
                {"to_resolve": "12ab34"},
                original=b"",
                input_meta=InputMeta(),
            )

            await self.object.process(document)
            assert document.data == expected_1

            await HttpGetter.refresh()  # Try refresh, but no time to update yet
            await self.object.process(document)
            assert document.data == expected_1

            await http_getter.scheduler.run_all()  # Force update
            await self.object.process(document)
            assert document.data == expected_2

    async def test_resolve_dotted_src_and_dest_field_and_conflict_match(self):
        await self._load_rule(
            {
                "filter": "to.resolve",
                "generic_resolver": {
                    "field_mapping": {"to.resolve": "re.solved"},
                    "resolve_list": {".*HELLO\\d": "Greeting"},
                },
            }
        )
        document = LogEvent(
            {
                "to": {"resolve": "something HELLO1"},
                "re": {"solved": "I already exist!"},
            },
            original=b"",
            input_meta=InputMeta(),
        )
        expected = {
            "tags": ["_generic_resolver_failure"],
            "to": {"resolve": "something HELLO1"},
            "re": {"solved": "I already exist!"},
        }
        await self.object.setup()
        result = await self.object.process(document)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)
        assert document.data == expected

    async def test_resolve_from_cache_with_large_enough_cache(self):
        """The metrics are mocked and their values are the sum of previously added cache values,
        instead of being the current cache values."""
        config = deepcopy(self.CONFIG)
        config["max_cache_entries"] = 10
        self.object = Factory.create({"generic_resolver": config})

        event_1 = {"to_resolve": "foo"}
        event_2 = {"to_resolve": "bar"}

        await self._load_rule(
            {
                "filter": "to_resolve",
                "generic_resolver": {
                    "field_mapping": {"to_resolve": "resolved"},
                    "resolve_list": {".+ar": "res_bar", ".+oo": "res_foo"},
                },
            }
        )
        await self.object.setup()

        self.object.metrics.new_results = 0
        self.object.metrics.cached_results = 0
        self.object.metrics.num_cache_entries = 0

        await self.object.process(LogEvent(event_1, original=b"", input_meta=InputMeta()))

        assert self.object.metrics.new_results == 1
        assert self.object.metrics.cached_results == 0
        assert self.object.metrics.num_cache_entries == 1

        await self.object.process(LogEvent(event_1, original=b"", input_meta=InputMeta()))

        assert self.object.metrics.new_results == 2
        assert self.object.metrics.cached_results == 1
        assert self.object.metrics.num_cache_entries == 2

        await self.object.process(LogEvent(event_2, original=b"", input_meta=InputMeta()))

        assert self.object.metrics.new_results == 4
        assert self.object.metrics.cached_results == 2
        assert self.object.metrics.num_cache_entries == 4

    async def test_resolve_from_cache_with_cache_smaller_than_results(self):
        """The metrics are mocked and their values are the sum of previously added cache values,
        instead of being the current cache values."""
        config = deepcopy(self.CONFIG)
        config["max_cache_entries"] = 1
        self.object = Factory.create({"generic_resolver": config})

        event_1 = {"to_resolve": "foo"}
        event_2 = {"to_resolve": "bar"}

        await self._load_rule(
            {
                "filter": "to_resolve",
                "generic_resolver": {
                    "field_mapping": {"to_resolve": "resolved"},
                    "resolve_list": {".+ar": "res_bar", ".+oo": "res_foo"},
                },
            }
        )
        await self.object.setup()

        self.object.metrics.new_results = 0
        self.object.metrics.cached_results = 0
        self.object.metrics.num_cache_entries = 0

        await self.object.process(LogEvent(event_1, original=b"", input_meta=InputMeta()))

        assert self.object.metrics.new_results == 1
        assert self.object.metrics.cached_results == 0
        assert self.object.metrics.num_cache_entries == 1

        await self.object.process(LogEvent(event_1, original=b"", input_meta=InputMeta()))

        assert self.object.metrics.new_results == 2
        assert self.object.metrics.cached_results == 1
        assert self.object.metrics.num_cache_entries == 2

        await self.object.process(LogEvent(event_2, original=b"", input_meta=InputMeta()))

        assert self.object.metrics.new_results == 4
        assert self.object.metrics.cached_results == 2
        assert self.object.metrics.num_cache_entries == 3

    async def test_resolve_without_cache(self):
        config = deepcopy(self.CONFIG)
        config["max_cache_entries"] = 0
        self.object = Factory.create({"generic_resolver": config})

        event_1 = {"to_resolve": "foo"}
        event_2 = {"to_resolve": "bar"}

        await self._load_rule(
            {
                "filter": "to_resolve",
                "generic_resolver": {
                    "field_mapping": {"to_resolve": "resolved"},
                    "resolve_list": {".+ar": "res_bar", ".+oo": "res_foo"},
                },
            }
        )
        await self.object.setup()

        self.object.metrics.new_results = 0
        self.object.metrics.cached_results = 0
        self.object.metrics.num_cache_entries = 0

        await self.object.process(LogEvent(event_1, original=b"", input_meta=InputMeta()))

        assert self.object.metrics.new_results == 0
        assert self.object.metrics.cached_results == 0
        assert self.object.metrics.num_cache_entries == 0

        await self.object.process(LogEvent(event_1, original=b"", input_meta=InputMeta()))

        assert self.object.metrics.new_results == 0
        assert self.object.metrics.cached_results == 0
        assert self.object.metrics.num_cache_entries == 0

        await self.object.process(LogEvent(event_2, original=b"", input_meta=InputMeta()))

        assert self.object.metrics.new_results == 0
        assert self.object.metrics.cached_results == 0
        assert self.object.metrics.num_cache_entries == 0

    async def test_resolve_from_cache_with_update_interval(self):
        """The metrics are mocked and their values are the sum of previously added cache values,
        instead of being the current cache values."""
        config = deepcopy(self.CONFIG)
        config["cache_metrics_interval"] = 2
        config["max_cache_entries"] = 10
        self.object = Factory.create({"generic_resolver": config})

        event_1 = {"to_resolve": "foo"}
        event_2 = {"to_resolve": "bar"}

        await self._load_rule(
            {
                "filter": "to_resolve",
                "generic_resolver": {
                    "field_mapping": {"to_resolve": "resolved"},
                    "resolve_list": {".+ar": "res_bar", ".+oo": "res_foo"},
                },
            }
        )
        await self.object.setup()

        self.object.metrics.new_results = 0
        self.object.metrics.cached_results = 0
        self.object.metrics.num_cache_entries = 0

        await self.object.process(LogEvent(event_1, original=b"", input_meta=InputMeta()))

        assert self.object.metrics.new_results == 0
        assert self.object.metrics.cached_results == 0
        assert self.object.metrics.num_cache_entries == 0

        await self.object.process(LogEvent(event_1, original=b"", input_meta=InputMeta()))

        assert self.object.metrics.new_results == 1
        assert self.object.metrics.cached_results == 1
        assert self.object.metrics.num_cache_entries == 1

        await self.object.process(LogEvent(event_2, original=b"", input_meta=InputMeta()))

        assert self.object.metrics.new_results == 1
        assert self.object.metrics.cached_results == 1
        assert self.object.metrics.num_cache_entries == 1

        await self.object.process(LogEvent(event_2, original=b"", input_meta=InputMeta()))

        assert self.object.metrics.new_results == 3
        assert self.object.metrics.cached_results == 3
        assert self.object.metrics.num_cache_entries == 3
