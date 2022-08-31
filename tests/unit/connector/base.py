# pylint: disable=missing-docstring
from abc import ABC
from logging import getLogger
from typing import Iterable
from logprep.abc.connector import Connector
from logprep.connector.connector_factory import ConnectorFactory
from logprep.util.helper import camel_to_snake


class BaseConnectorTestCase(ABC):
    CONFIG: dict = {}
    object: Connector = None
    logger = getLogger()

    def setup_method(self) -> None:
        self.patchers = []
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
