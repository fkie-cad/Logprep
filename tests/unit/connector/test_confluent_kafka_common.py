# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=no-member
from copy import deepcopy
from socket import getfqdn

import pytest

from logprep.factory import Factory


class CommonConfluentKafkaTestCase:
    def test_client_id_is_set_to_hostname(self):
        self.object.setup()
        assert self.object._config.kafka_config.get("client.id") == getfqdn()

    def test_create_fails_for_unknown_option(self):
        kafka_config = deepcopy(self.CONFIG)
        kafka_config.update({"unknown_option": "bad value"})
        with pytest.raises(TypeError, match=r"unexpected keyword argument"):
            _ = Factory.create({"test connector": kafka_config}, logger=self.logger)
