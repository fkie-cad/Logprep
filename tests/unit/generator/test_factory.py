# pylint: disable=missing-docstring
import json
import logging
from unittest import mock

import pytest

from logprep.generator.confluent_kafka.output import ConfluentKafkaGeneratorOutput
from logprep.generator.controller import Controller
from logprep.generator.factory import ControllerFactory
from logprep.generator.http.output import HttpGeneratorOutput
from logprep.util.defaults import DEFAULT_LOG_CONFIG
from logprep.util.logging import LogprepMPQueueListener


class TestFactory:
    def test_controller_get_raises_if_no_type(self):
        # pylint: disable=no-value-for-parameter
        with pytest.raises(TypeError, match="missing 1 required positional argument: 'target'"):
            _ = ControllerFactory.create()

    def test_controller_get_raises_if_invalid_type(self):
        with pytest.raises(ValueError, match="Controller type invalid not supported"):
            _ = ControllerFactory.create("invalid")

    @pytest.mark.parametrize(
        "target, expected_class",
        [
            ("http", Controller),
            ("kafka", Controller),
        ],
    )
    def test_create_returns(self, target, expected_class):
        kwargs = {
            "user": "test_user",
            "input_dir": "test_dir/",
            "password": "test_password",
            "target_url": "http://example.com",
            "timeout": 5,
        }
        with (mock.patch.object(ControllerFactory, "get_loghandler"),):
            controller = ControllerFactory.create(target, **kwargs)
            assert controller
            assert isinstance(controller, expected_class)

    @mock.patch("logprep.factory.Factory.create")
    def test_create_creates_http_output(self, mock_factory_create):

        kwargs = {
            "user": "test_user",
            "input_dir": "test_dir/",
            "password": "test_password",
            "target_url": "http://example.com",
            "timeout": 5,
            "verify": False,
        }

        expected_output_config = {
            "generator_output": {
                "type": "http_generator_output",
                "user": "test_user",
                "password": "test_password",
                "target_url": "http://example.com",
                "timeout": 5,
                "verify": False,
            }
        }
        mock_http_output = mock.create_autospec(HttpGeneratorOutput, instance=True)
        mock_factory_create.return_value = mock_http_output
        with mock.patch.object(ControllerFactory, "get_loghandler"):
            controller = ControllerFactory.create("http", **kwargs)
        mock_factory_create.assert_called_once_with(expected_output_config)

        assert controller.output == mock_factory_create.return_value

    @mock.patch("logprep.factory.Factory.create")
    def test_create_creates_kafka_output(self, mock_factory_create):

        kwargs = {
            "input_dir": "/some-path",
            "send_timeout": 0,
            "output_config": '{"bootstrap.servers": "localhost:9092"}',
        }

        expected_output_config = {
            "generator_output": {
                "type": "confluentkafka_generator_output",
                "topic": "producer",
                "send_timeout": 0,
                "kafka_config": json.loads(kwargs.get("output_config")),
            },
        }

        mock_http_output = mock.create_autospec(ConfluentKafkaGeneratorOutput, instance=True)
        mock_factory_create.return_value = mock_http_output

        with mock.patch.object(ControllerFactory, "get_loghandler"):
            controller = ControllerFactory.create(target="kafka", **kwargs)
        mock_factory_create.assert_called_once_with(expected_output_config)

        assert controller.output == mock_factory_create.return_value

    @mock.patch("logprep.factory.Factory.create")
    def test_create_calls_get_loghandler(self, mock_factory_create):
        kwargs = {
            "user": "test_user",
            "input_dir": "test_dir/",
            "password": "test_password",
            "target_url": "http://example.com",
            "timeout": 5,
        }

        mock_http_output = mock.create_autospec(HttpGeneratorOutput, instance=True)
        mock_factory_create.return_value = mock_http_output

        with mock.patch.object(ControllerFactory, "get_loghandler") as mock_get_loghandler:
            _ = ControllerFactory.create("http", **kwargs)
        mock_get_loghandler.assert_called_once_with("INFO")

    def test_get_loghandler_returns_loghandler(self):
        logging.config.dictConfig(DEFAULT_LOG_CONFIG)
        with mock.patch("logprep.generator.factory.logger"):
            loghandler = ControllerFactory.get_loghandler("INFO")
        assert loghandler
        assert isinstance(loghandler, LogprepMPQueueListener)

    def test_get_loghandler_raises_on_invalid_level(self):
        with pytest.raises(ValueError, match="Unknown level"):
            _ = ControllerFactory.get_loghandler("INVALID")

    def test_level_passed_to_set_level(self):
        logging.config.dictConfig(DEFAULT_LOG_CONFIG)
        with mock.patch("logprep.generator.factory.logger") as mock_logger:
            _ = ControllerFactory.get_loghandler("DEBUG")
        mock_logger.root.setLevel.assert_called_once_with("DEBUG")

    def test_get_loghandler_raises_if_no_handler(self):
        logging.config.dictConfig(DEFAULT_LOG_CONFIG)
        with mock.patch("logging.getLogger") as mock_get_logger:
            mock_console_logger = mock.MagicMock()
            mock_get_logger.return_value = mock_console_logger
            mock_console_logger.handlers = []
            with pytest.raises(ValueError, match="No console handler found"):
                _ = ControllerFactory.get_loghandler("DEBUG")

    def test_invalid_output_type(self):
        kwargs = {
            "user": "test_user",
            "input_dir": "test_dir/",
            "password": "test_password",
            "target_url": "http://example.com",
            "timeout": 5,
        }
        with mock.patch("logprep.factory.Factory.create", return_value=mock.MagicMock()):
            with pytest.raises(ValueError, match="Output is not a valid output type"):
                with mock.patch.object(ControllerFactory, "get_loghandler"):
                    ControllerFactory.create("http", **kwargs)
