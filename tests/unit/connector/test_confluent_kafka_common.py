# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=no-member
from copy import deepcopy
from socket import getfqdn

import pytest

from logprep.factory import Factory
from logprep.factory_error import InvalidConfigurationError


class CommonConfluentKafkaTestCase:
    def test_client_id_is_set_to_hostname(self):
        assert self.object._client_id == getfqdn()

    def test_create_fails_for_unknown_option(self):
        kafka_config = deepcopy(self.CONFIG)
        kafka_config.update({"unknown_option": "bad value"})
        with pytest.raises(TypeError, match=r"unexpected keyword argument"):
            _ = Factory.create({"test connector": kafka_config}, logger=self.logger)

    def test_create_fails_for_wrong_type_in_ssl_option(self):
        kafka_config = deepcopy(self.CONFIG)
        kafka_config.update({"ssl": "this should not be a string"})
        with pytest.raises(TypeError, match=r"'ssl' must be <class 'dict'>"):
            _ = Factory.create({"test connector": kafka_config}, logger=self.logger)

    def test_create_fails_for_incomplete_ssl_options(self):
        kafka_config = deepcopy(self.CONFIG)
        kafka_config.get("ssl", {}).pop("password")
        with pytest.raises(
            InvalidConfigurationError, match=r"following keys are missing: {'password'}"
        ):
            _ = Factory.create({"test connector": kafka_config}, logger=self.logger)

    def test_create_fails_for_extra_key_in_ssl_options(self):
        kafka_config = deepcopy(self.CONFIG)
        kafka_config.get("ssl", {}).update({"extra_key": "value"})
        with pytest.raises(
            InvalidConfigurationError, match=r"following keys are unknown: {'extra_key'}"
        ):
            _ = Factory.create({"test connector": kafka_config}, logger=self.logger)

    def test_create_without_ssl_options_and_set_defaults(self):
        kafka_config = deepcopy(self.CONFIG)
        kafka_config.pop("ssl")
        kafka_input = Factory.create({"test connector": kafka_config}, logger=self.logger)
        assert kafka_input._config.ssl == {
            "cafile": None,
            "certfile": None,
            "keyfile": None,
            "password": None,
        }
