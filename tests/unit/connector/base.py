# pylint: disable=missing-docstring
# pylint: disable=protected-access
from abc import ABC
from copy import deepcopy
from logging import getLogger
from typing import Iterable
from unittest import mock
from logprep.abc.connector import Connector
from logprep.connector.connector_factory import ConnectorFactory
from logprep.util.helper import camel_to_snake


class BaseConnectorTestCase(ABC):
    CONFIG: dict = {}
    object: Connector = None
    logger = getLogger()

    def setup_method(self) -> None:
        config = {"Test Instance Name": self.CONFIG}
        self.object = ConnectorFactory.create(configuration=config, logger=self.logger)

    def test_is_a_connector_implementation(self):
        assert isinstance(self.object, Connector)

    def test_uses_python_slots(self):
        assert isinstance(self.object.__slots__, Iterable)

    def test_describe(self):
        describe_string = self.object.describe()
        assert f"{self.object.__class__.__name__} (Test Instance Name)" == describe_string

    def test_snake_type(self):
        assert str(self.object) == camel_to_snake(self.object.__class__.__name__)


class BaseInputTestCase(BaseConnectorTestCase):
    def test_add_hmac_returns_true_if_hmac_options(self):
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(
            {
                "preprocessing": {
                    "hmac": {
                        "target": "<RAW_MSG>",
                        "key": "hmac-test-key",
                        "output_field": "Hmac",
                    }
                }
            }
        )
        connector = ConnectorFactory.create(
            {"test connector": connector_config}, logger=self.logger
        )
        assert connector._add_hmac is True

    def test_add_hmac_to_adds_hmac(self):
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(
            {
                "preprocessing": {
                    "hmac": {
                        "target": "<RAW_MSG>",
                        "key": "hmac-test-key",
                        "output_field": "Hmac",
                    }
                }
            }
        )
        connector = ConnectorFactory.create(
            {"test connector": connector_config}, logger=self.logger
        )
        processed_event = connector._add_hmac_to({"message": "test message"}, b"test message")
        assert processed_event.get("Hmac")
        assert (
            processed_event.get("Hmac").get("hmac")
            == "cc67047535dc9ac17775785b05fe8cdd245387e2d036b2475e82f37653c5bf3d"
        )
        assert (
            processed_event.get("Hmac").get("compressed_base64") == "eJwrSS0uUchNLS5OTE8FAB8fBMY="
        )

    def test_get_next_returns_event(self):
        return_value = ({"message": "test message"}, b'{"message": "test message"}')
        self.object._get_event = mock.MagicMock(return_value=return_value)
        event = self.object.get_next(0.01)
        assert isinstance(event, dict)
