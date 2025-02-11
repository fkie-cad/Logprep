import pytest

from logprep.generator.confluent_kafka.controller import KafkaController
from logprep.generator.factory import ControllerFactory
from logprep.generator.http.controller import HTTPController


class TestController:
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
