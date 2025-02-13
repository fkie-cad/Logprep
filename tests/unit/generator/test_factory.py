# pylint: disable=missing-docstring
import json
from unittest import mock

import pytest

from logprep.connector.confluent_kafka.output import ConfluentKafkaOutput
from logprep.connector.http.output import HttpOutput
from logprep.generator.confluent_kafka.controller import KafkaController
from logprep.generator.factory import ControllerFactory
from logprep.generator.http.controller import HttpController


class TestFactory:
    def test_controller_get_raises_if_no_type(self):
        with pytest.raises(TypeError, match="missing 1 required positional argument: 'target'"):
            _ = ControllerFactory.create()

    def test_controller_get_raises_if_invalid_type(self):
        with pytest.raises(ValueError, match="Controller type invalid not supported"):
            _ = ControllerFactory.create("invalid")

    @pytest.mark.parametrize(
        "target, expected_class",
        [
            ("http", HttpController),
            ("kafka", KafkaController),
        ],
    )
    def test_create_returns(self, target, expected_class):
        with mock.patch.object(ControllerFactory, "get_loghandler"):
            controller = ControllerFactory.create(target)
            assert controller
            assert isinstance(controller, expected_class)

    @mock.patch("logprep.factory.Factory.create")
    def test_create_creates_http_output(self, mock_factory_create):

        kwargs = {
            "user": "test_user",
            "password": "test_password",
            "target_url": "http://example.com",
            "timeout": 5,
        }

        expected_output_config = {
            "generator_output": {
                "type": "http_output",
                "user": "test_user",
                "password": "test_password",
                "target_url": "http://example.com",
                "timeout": 5,
            }
        }
        mock_http_output = mock.create_autospec(HttpOutput, instance=True)
        mock_factory_create.return_value = mock_http_output
        with mock.patch.object(ControllerFactory, "get_loghandler"):
            controller = ControllerFactory.create("http", **kwargs)
        mock_factory_create.assert_called_once_with(expected_output_config)

        assert controller.output == mock_factory_create.return_value

    @mock.patch("logprep.factory.Factory.create")
    def test_create_creates_kafka_output(self, mock_factory_create):

        kwargs = {
            "input_dir": "/some-path",
            "output_config": '{"bootstrap.servers": "localhost:9092"}',
        }

        expected_output_config = {
            "generator_output": {
                "type": "confluentkafka_output",
                "topic": "producer",
                "kafka_config": json.loads(kwargs.get("output_config")),
            },
        }

        mock_http_output = mock.create_autospec(ConfluentKafkaOutput, instance=True)
        mock_factory_create.return_value = mock_http_output

        with mock.patch.object(ControllerFactory, "get_loghandler"):
            controller = ControllerFactory.create(target="kafka", **kwargs)
        mock_factory_create.assert_called_once_with(expected_output_config)

        assert controller.output == mock_factory_create.return_value

    @mock.patch("logprep.factory.Factory.create")
    def test_create_calls_get_loghandler(self, mock_factory_create):
        kwargs = {
            "user": "test_user",
            "password": "test_password",
            "target_url": "http://example.com",
            "timeout": 5,
        }

        mock_http_output = mock.create_autospec(HttpOutput, instance=True)
        mock_factory_create.return_value = mock_http_output

        with mock.patch.object(ControllerFactory, "get_loghandler") as mock_get_loghandler:
            _ = ControllerFactory.create("http", **kwargs)
        mock_get_loghandler.assert_called_once_with("INFO")
