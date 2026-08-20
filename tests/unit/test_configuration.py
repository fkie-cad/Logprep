# pylint: disable=missing-docstring
from typing import Optional
from unittest import mock

import pytest
from aiohttp import web
from attrs import define, field, validators

from logprep.abc.processor import Processor
from logprep.configuration import Configuration
from logprep.factory_error import NoTypeSpecifiedError, UnknownComponentTypeError
from logprep.ng.util.configuration import (
    ConfigGetterException,
)
from logprep.ng.util.configuration import Configuration as NgConfiguration
from logprep.ng.util.configuration import (
    InvalidConfigurationErrors,
)
from logprep.registry import Registry


class MockProcessor(Processor):
    @define(kw_only=True)
    class Config(Processor.Config):
        mandatory_attribute: str = field(validator=validators.instance_of(str))
        optional_attribute: Optional[str] = field(
            default=None, validator=validators.optional(validator=validators.instance_of(str))
        )

    def _apply_rules(self, event, rule):
        pass


class TestConfiguration:
    @pytest.fixture(autouse=True)
    def mock_registry(self):
        with mock.patch.object(
            Registry,
            "_mapping",
            new={"mock_processor": "tests.unit.test_configuration.MockProcessor"},
        ):
            yield

    def test_reads_test_config(self):
        test_config = {
            "type": "mock_processor",
            "rules": ["tests/testdata/unit/dissector/rules"],
            "mandatory_attribute": "I am mandatory",
            "optional_attribute": "I am optional",
        }
        config = Configuration.create("dummy name", test_config)
        assert config.type == "mock_processor"
        assert config.mandatory_attribute == "I am mandatory"
        assert config.rules == ["tests/testdata/unit/dissector/rules"]

    def test_raises_on_missing_type(self):
        test_config = {
            "rules": ["tests/testdata/unit/dissector/rules"],
            "mandatory_attribute": "I am mandatory",
            "optional_attribute": "I am optional",
        }
        with pytest.raises(NoTypeSpecifiedError):
            Configuration.create("dummy name", test_config)

    def test_raises_on_unknown_processor(self):
        test_config = {
            "type": "unknown_processor",
            "rules": ["tests/testdata/unit/dissector/rules"],
            "mandatory_attribute": "I am mandatory",
            "optional_attribute": "I am optional",
        }
        with pytest.raises(UnknownComponentTypeError):
            Configuration.create("dummy name", test_config)

    def test_raises_if_one_mandatory_field_is_missing(self):
        test_config = {
            "type": "mock_processor",
            "rules": ["tests/testdata/unit/dissector/rules"],
            "optional_attribute": "I am optional",
        }
        with pytest.raises(
            TypeError, match=r"missing 1 required .* argument: 'mandatory_attribute'"
        ):
            Configuration.create("dummy name", test_config)

    def test_raises_if_mandatory_attribute_from_base_is_missing(self):
        test_config = {
            "type": "mock_processor",
            "mandatory_attribute": "does not matter",
        }
        with pytest.raises(
            TypeError,
            match=r"missing 1 required .* argument: 'rules'",
        ):
            Configuration.create("dummy name", test_config)

    def test_raises_if_multiple_mandatory_field_are_missing(self):
        test_config = {"type": "mock_processor"}
        with pytest.raises(
            TypeError,
            match=r"missing 2 required .* arguments: .*'rules' and 'mandatory_attribute'",
        ):
            Configuration.create("dummy name", test_config)

    def test_raises_on_unknown_field(self):
        test_config = {
            "type": "mock_processor",
            "rules": ["tests/testdata/unit/dissector/rules"],
            "mandatory_attribute": "I am mandatory",
            "optional_attribute": "I am optional",
            "i_shoul_not_be_here": "does not matter",
        }
        with pytest.raises(TypeError, match=r"unexpected keyword argument 'i_shoul_not_be_here'"):
            Configuration.create("dummy name", test_config)

    def test_init_non_mandatory_fields_with_default(self):
        test_config = {
            "type": "mock_processor",
            "rules": ["tests/testdata/unit/dissector/rules"],
            "mandatory_attribute": "I am mandatory",
        }
        config = Configuration.create("dummy name", test_config)
        assert config.tree_config is None
        assert config.optional_attribute is None

    def test_init_optional_field_in_sub_class(self):
        test_config = {
            "type": "mock_processor",
            "rules": ["tests/testdata/unit/dissector/rules"],
            "mandatory_attribute": "I am mandatory",
            "optional_attribute": "I am optional",
        }
        config = Configuration.create("dummy name", test_config)
        assert config.optional_attribute == "I am optional"

    def test_init_optional_field_in_base_class(self):
        test_config = {
            "type": "mock_processor",
            "rules": ["tests/testdata/unit/dissector/rules"],
            "mandatory_attribute": "I am mandatory",
            "tree_config": "tests/testdata/unit/tree_config.json",
        }
        config = Configuration.create("dummy name", test_config)
        assert config.tree_config == "tests/testdata/unit/tree_config.json"


class TestNgConfiguration:
    async def test_from_sources_wraps_http_getter_error(self, aiohttp_server):
        async def handler(_: web.Request) -> web.Response:
            return web.Response(status=404)

        app = web.Application()
        app.router.add_get("/config.yml", handler)
        server = await aiohttp_server(app)

        config_url = str(server.make_url("/config.yml"))

        with pytest.raises(ConfigGetterException, match="404"):
            await NgConfiguration.from_sources([config_url])

    async def test_verify_shuts_down_temporary_processor(self):
        configuration = NgConfiguration()
        configuration.input = {"input": {"type": "input"}}
        configuration.output = {"output": {"type": "output"}}
        configuration.pipeline = [{"processor": {"type": "processor"}}]

        processor = mock.Mock()
        processor.setup = mock.AsyncMock()
        processor.shut_down = mock.AsyncMock()

        with (
            mock.patch(
                "logprep.ng.util.configuration.Factory.create",
                side_effect=[
                    mock.Mock(),
                    mock.Mock(),
                    processor,
                ],
            ),
            mock.patch.object(
                NgConfiguration,
                "_verify_environment",
            ),
            mock.patch.object(
                NgConfiguration,
                "_verify_rules",
            ),
            mock.patch.object(
                NgConfiguration,
                "_verify_processor_outputs",
            ),
        ):
            await configuration._verify()

        processor.setup.assert_awaited_once()
        processor.shut_down.assert_awaited_once()

    async def test_verify_shuts_down_temporary_processor_if_setup_fails(self):
        configuration = NgConfiguration()
        configuration.input = {"input": {"type": "input"}}
        configuration.output = {"output": {"type": "output"}}
        configuration.pipeline = [{"processor": {"type": "processor"}}]

        processor = mock.Mock()
        processor.setup = mock.AsyncMock(side_effect=ValueError("setup failed"))
        processor.shut_down = mock.AsyncMock()

        with (
            mock.patch(
                "logprep.ng.util.configuration.Factory.create",
                side_effect=[
                    mock.Mock(),
                    mock.Mock(),
                    processor,
                ],
            ),
            mock.patch.object(
                NgConfiguration,
                "_verify_environment",
            ),
            mock.patch.object(
                NgConfiguration,
                "_verify_processor_outputs",
            ),
        ):
            with pytest.raises(
                InvalidConfigurationErrors,
                match="setup failed",
            ):
                await configuration._verify()

        processor.shut_down.assert_awaited_once()
