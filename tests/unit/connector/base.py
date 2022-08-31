# pylint: disable=missing-docstring
from abc import ABC
from logging import getLogger
from logprep.abc.connector import Connector
from logprep.connector.connector_factory import ConnectorFactory


class BaseConnectorTestCase(ABC):
    CONFIG: dict = {}
    object: Connector = None
    logger = getLogger()

    def setup_method(self) -> None:
        pass

    def test_create_works(self):
        config = {"Test Instance Name": self.CONFIG}
        self.object = ConnectorFactory.create(configuration=config, logger=self.logger)
        assert self.object
