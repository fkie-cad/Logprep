# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=no-member
import json
from copy import deepcopy
from pathlib import Path
from socket import getfqdn
from unittest import mock

import pytest

from logprep.factory import Factory

KAFKA_STATS_JSON_PATH = "tests/testdata/kafka_stats_return_value.json"


class CommonConfluentKafkaTestCase:
    def test_client_id_is_set_to_hostname(self):
        self.object.setup()
        assert self.object._config.kafka_config.get("client.id") == getfqdn()

    def test_create_fails_for_unknown_option(self):
        kafka_config = deepcopy(self.CONFIG)
        kafka_config.update({"unknown_option": "bad value"})
        with pytest.raises(TypeError, match=r"unexpected keyword argument"):
            _ = Factory.create({"test connector": kafka_config}, logger=self.logger)

    def test_error_callback_logs_warnings(self):
        with mock.patch("logging.Logger.warning") as mock_warning:
            test_error = BaseException("test error")
            self.object._error_callback(test_error)
            mock_warning.assert_called()
            mock_warning.assert_called_with(f"{self.object.describe()}: {test_error}")

    def test_stats_callback_sets_stats_in_metric_object(self):
        json_string = Path(KAFKA_STATS_JSON_PATH).read_text("utf8")
        self.object._stats_callback(json_string)
        assert self.object.metrics._stats == json.loads(json_string)
