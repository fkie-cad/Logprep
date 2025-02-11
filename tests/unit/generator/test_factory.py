# pylint: disable=missing-docstring
import json
from unittest import mock

import pytest

from logprep.generator.confluent_kafka.controller import KafkaController
from logprep.generator.factory import ControllerFactory
from logprep.generator.http.controller import HTTPController


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
            ("http", HTTPController),
            ("kafka", KafkaController),
        ],
    )
    def test_controller_get_http(self, target, expected_class):
        controller = ControllerFactory.create(target)
        assert controller
        assert isinstance(controller, expected_class)

    @mock.patch("logprep.factory.Factory.create")
    def test_http_controller_create_output(self, mock_factory_create):

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
        controller = ControllerFactory.create("http", **kwargs)
        mock_factory_create.assert_called_once_with(expected_output_config)

        assert controller.output == mock_factory_create.return_value

    @mock.patch("logprep.factory.Factory.create")
    def test_kafka_controller_create_output(self, mock_factory_create):

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
        controller = ControllerFactory.create(target="kafka", **kwargs)
        mock_factory_create.assert_called_once_with(expected_output_config)

        assert controller.output == mock_factory_create.return_value

    def test_create_instantiates_loghandler(self):
        assert False
