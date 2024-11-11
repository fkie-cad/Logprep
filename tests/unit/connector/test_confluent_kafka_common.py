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
from logprep.util.helper import get_dotted_field_value

KAFKA_STATS_JSON_PATH = "tests/testdata/kafka_stats_return_value.json"


class CommonConfluentKafkaTestCase:
    expected_metrics = []

    def test_client_id_is_set_to_hostname(self):
        self.object.setup()
        assert self.object._kafka_config.get("client.id") == getfqdn()

    def test_create_fails_for_unknown_option(self):
        kafka_config = deepcopy(self.CONFIG)
        kafka_config.update({"unknown_option": "bad value"})
        with pytest.raises(TypeError, match=r"unexpected keyword argument"):
            _ = Factory.create({"test connector": kafka_config})

    def test_error_callback_logs_error(self):
        self.object.metrics.number_of_errors = 0
        with mock.patch("logging.Logger.error") as mock_error:
            test_error = Exception("test error")
            self.object._error_callback(test_error)
            mock_error.assert_called()
            mock_error.assert_called_with(f"{self.object.describe()}: {test_error}")
        assert self.object.metrics.number_of_errors == 1

    def test_stats_callback_sets_metric_objetc_attributes(self):
        librdkafka_metrics = tuple(
            filter(lambda x: x.startswith("librdkafka"), self.expected_metrics)
        )
        for metric in librdkafka_metrics:
            setattr(self.object.metrics, metric, 0)
        json_string = Path(KAFKA_STATS_JSON_PATH).read_text("utf8")
        self.object._stats_callback(json_string)
        stats_dict = json.loads(json_string)
        for metric in librdkafka_metrics:
            metric_name = metric.replace("librdkafka_", "").replace("cgrp_", "cgrp.")
            metric_value = get_dotted_field_value(stats_dict, metric_name)
            assert getattr(self.object.metrics, metric) == metric_value, metric

    def test_stats_set_age_metric_explicitly(self):
        self.object.metrics.librdkafka_age = 0
        json_string = Path(KAFKA_STATS_JSON_PATH).read_text("utf8")
        self.object._stats_callback(json_string)
        assert self.object.metrics.librdkafka_age == 1337

    def test_kafka_config_is_immutable(self):
        self.object.setup()
        with pytest.raises(TypeError):
            self.object._config.kafka_config["client.id"] = "test"
