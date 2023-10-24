# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
# pylint: disable=unnecessary-dunder-call
import base64
import json
import os
import zlib
from copy import deepcopy
from logging import getLogger
from unittest import mock

from logprep.abc.connector import Connector
from logprep.abc.input import Input
from logprep.abc.output import Output
from logprep.factory import Factory
from logprep.util.time import TimeParser
from tests.unit.component.base import BaseComponentTestCase


class BaseConnectorTestCase(BaseComponentTestCase):
    CONFIG: dict = {}
    object: Connector = None
    logger = getLogger()

    expected_metrics = [
        "logprep_processing_time_per_event",
        "logprep_number_of_processed_events",
        "logprep_number_of_failed_events",
        "logprep_number_of_warnings",
        "logprep_number_of_errors",
    ]

    def test_is_a_connector_implementation(self):
        assert isinstance(self.object, Connector)


class BaseInputTestCase(BaseConnectorTestCase):
    def test_is_input_instance(self):
        assert isinstance(self.object, Input)

    def test_get_next_returns_event(self):
        return_value = ({"message": "test message"}, b'{"message": "test message"}')
        self.object._get_event = mock.MagicMock(return_value=return_value)
        event, _ = self.object.get_next(0.01)
        assert isinstance(event, dict)

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
        connector = Factory.create({"test connector": connector_config}, logger=self.logger)
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
        connector = Factory.create({"test connector": connector_config}, logger=self.logger)
        processed_event, non_critical_error_msg = connector._add_hmac_to(
            {"message": "test message"}, b"test message"
        )
        assert non_critical_error_msg is None
        assert processed_event.get("Hmac")
        assert (
            processed_event.get("Hmac").get("hmac")
            == "cc67047535dc9ac17775785b05fe8cdd245387e2d036b2475e82f37653c5bf3d"
        )
        assert (
            processed_event.get("Hmac").get("compressed_base64") == "eJwrSS0uUchNLS5OTE8FAB8fBMY="
        )

    def test_add_hmac_to_adds_hmac_even_if_no_raw_message_was_given(self):
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
        connector = Factory.create({"test connector": connector_config}, logger=self.logger)
        processed_event, non_critical_error_msg = connector._add_hmac_to(
            {"message": "test message"}, None
        )
        assert non_critical_error_msg is None
        assert processed_event.get("Hmac")
        calculated_hmac = processed_event.get("Hmac").get("hmac")
        assert (
            calculated_hmac == "8b2d75efcba66476e5551d44065128bacff2f090db5b08d7a0201c33e3f651f5"
        ), f"Wrong hmac: '{calculated_hmac}'"
        calculated_compression = processed_event.get("Hmac").get("compressed_base64")
        assert (
            calculated_compression == "eJyrVspNLS5OTE9VslIqSS0uUYBxawF+Fwll"
        ), f"Wrong compression: {calculated_compression}"

    def test_get_next_with_hmac_of_raw_message(self):
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
        connector = Factory.create({"test connector": connector_config}, logger=self.logger)
        test_event = {"message": "with_content"}
        raw_encoded_test_event = json.dumps(test_event, separators=(",", ":")).encode("utf-8")
        connector._get_event = mock.MagicMock(
            return_value=(test_event.copy(), raw_encoded_test_event)
        )
        expected_event = {
            "message": "with_content",
            "Hmac": {
                "compressed_base64": "eJyrVspNLS5OTE9VslIqzyzJiE/OzytJzStRqgUAgKkJtg==",
                "hmac": "dfe78753da634d7b76760488dbb2cf7bfe1b0e4e794930c36e98a984b6b6be63",
            },
        }
        connector_next_msg, _ = connector.get_next(1)
        assert connector_next_msg == expected_event, "Output event with hmac is not as expected"

        decoded = base64.b64decode(connector_next_msg["Hmac"]["compressed_base64"])
        decoded_message = zlib.decompress(decoded)
        assert test_event == json.loads(
            decoded_message.decode("utf-8")
        ), "The hmac base massage was not correctly encoded and compressed. "

    def test_get_next_with_hmac_of_subfield(self):
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(
            {
                "preprocessing": {
                    "hmac": {
                        "target": "message.with_subfield",
                        "key": "hmac-test-key",
                        "output_field": "Hmac",
                    }
                }
            }
        )
        connector = Factory.create({"test connector": connector_config}, logger=self.logger)
        test_event = {"message": {"with_subfield": "content"}}
        raw_encoded_test_event = json.dumps(test_event, separators=(",", ":")).encode("utf-8")
        connector._get_event = mock.MagicMock(
            return_value=(test_event.copy(), raw_encoded_test_event)
        )
        expected_event = {
            "message": {"with_subfield": "content"},
            "Hmac": {
                "compressed_base64": "eJxLzs8rSc0rAQALywL8",
                "hmac": "e01e02a09cb270eebf7ae846b96d7306681038bd279f85d44c77019e0c4f6316",
            },
        }

        connector_next_msg, _ = connector.get_next(1)
        assert connector_next_msg == expected_event

        decoded = base64.b64decode(connector_next_msg["Hmac"]["compressed_base64"])
        decoded_message = zlib.decompress(decoded)
        assert test_event["message"]["with_subfield"] == decoded_message.decode(
            "utf-8"
        ), "The hmac base massage was not correctly encoded and compressed. "

    def test_get_next_with_hmac_of_non_existing_subfield(self):
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(
            {
                "preprocessing": {
                    "hmac": {
                        "target": "non_existing_field",
                        "key": "hmac-test-key",
                        "output_field": "Hmac",
                    }
                }
            }
        )
        connector = Factory.create({"test connector": connector_config}, logger=self.logger)
        test_event = {"message": {"with_subfield": "content"}}
        raw_encoded_test_event = json.dumps(test_event, separators=(",", ":")).encode("utf-8")
        connector._get_event = mock.MagicMock(
            return_value=(test_event.copy(), raw_encoded_test_event)
        )
        expected_output_event = {
            "message": {"with_subfield": "content"},
            "Hmac": {
                "hmac": "error",
                "compressed_base64": "eJyzSa0oSE0uSU1RyMhNTFYoSSxKTy1RSMtMzUlRUM/Lz4tPrcgsLsnMS48Hi"
                "6kr5OUDpfNL81LsAJILFeQ=",
            },
        }
        connector_next_msg, non_critical_error_msg = connector.get_next(1)
        assert connector_next_msg == expected_output_event
        decoded = base64.b64decode(connector_next_msg["Hmac"]["compressed_base64"])
        decoded_message = zlib.decompress(decoded).decode("utf8")
        assert decoded_message == "<expected hmac target field 'non_existing_field' not found>"
        assert non_critical_error_msg == "Couldn't find the hmac target field 'non_existing_field'"

    def test_get_next_with_hmac_result_in_dotted_subfield(self):
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(
            {
                "preprocessing": {
                    "hmac": {
                        "target": "<RAW_MSG>",
                        "key": "hmac-test-key",
                        "output_field": "Hmac.dotted.subfield",
                    }
                }
            }
        )
        connector = Factory.create({"test connector": connector_config}, logger=self.logger)
        test_event = {"message": "with_content"}
        raw_encoded_test_event = json.dumps(test_event, separators=(",", ":")).encode("utf-8")
        connector._get_event = mock.MagicMock(
            return_value=(test_event.copy(), raw_encoded_test_event)
        )
        expected_event = {
            "message": "with_content",
            "Hmac": {
                "dotted": {
                    "subfield": {
                        "compressed_base64": "eJyrVspNLS5OTE9VslIqzyzJiE/OzytJzStRqgUAgKkJtg==",
                        "hmac": "dfe78753da634d7b76760488dbb2cf7bfe1b0e4e794930c36e98a984b6b6be63",
                    }
                }
            },
        }

        connector_next_msg, _ = connector.get_next(1)
        assert connector_next_msg == expected_event
        decoded = base64.b64decode(
            connector_next_msg["Hmac"]["dotted"]["subfield"]["compressed_base64"]
        )
        decoded_message = zlib.decompress(decoded)
        assert test_event == json.loads(
            decoded_message.decode("utf-8")
        ), "The hmac base massage was not correctly encoded and compressed. "

    def test_get_next_with_hmac_result_in_already_existing_subfield(self):
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(
            {
                "preprocessing": {
                    "hmac": {
                        "target": "<RAW_MSG>",
                        "key": "hmac-test-key",
                        "output_field": "message",
                    }
                }
            }
        )
        connector = Factory.create({"test connector": connector_config}, logger=self.logger)
        test_event = {"message": {"with_subfield": "content"}}
        raw_encoded_test_event = json.dumps(test_event, separators=(",", ":")).encode("utf-8")
        connector._get_event = mock.MagicMock(
            return_value=(test_event.copy(), raw_encoded_test_event)
        )
        _, non_critical_error_msg = connector.get_next(1)
        assert (
            non_critical_error_msg
            == "Couldn't add the hmac to the input event as the desired output field 'message' already exist."
        )

    def test_get_next_without_hmac(self):
        connector_config = deepcopy(self.CONFIG)
        assert not connector_config.get("preprocessing", {}).get("hmac")
        test_event = {"message": "with_content"}
        connector = Factory.create({"test connector": connector_config}, logger=self.logger)
        raw_encoded_test_event = json.dumps(test_event, separators=(",", ":")).encode("utf-8")
        connector._get_event = mock.MagicMock(
            return_value=(test_event.copy(), raw_encoded_test_event)
        )
        connector_next_msg, _ = connector.get_next(1)
        assert connector_next_msg == test_event

    def test_preprocessing_version_info_is_added_if_configured(self):
        preprocessing_config = {
            "preprocessing": {
                "version_info_target_field": "version_info",
                "hmac": {"target": "", "key": "", "output_field": ""},
            },
            "version_information": {"logprep": "3.3.0", "configuration": "unset"},
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config}, logger=self.logger)
        test_event = {"any": "content"}
        connector._get_event = mock.MagicMock(return_value=(test_event, None))
        result, _ = connector.get_next(0.01)
        assert result.get("version_info", {}).get("logprep") == "3.3.0"
        assert result.get("version_info", {}).get("configuration") == "unset"

    def test_pipeline_preprocessing_does_not_add_versions_if_target_field_exists_already(self):
        preprocessing_config = {
            "preprocessing": {
                "version_info_target_field": "version_info",
                "hmac": {"target": "", "key": "", "output_field": ""},
            }
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config}, logger=self.logger)
        test_event = {"any": "content", "version_info": "something random"}
        connector._get_event = mock.MagicMock(return_value=(test_event, None))
        result, _ = connector.get_next(0.01)
        assert result == {"any": "content", "version_info": "something random"}

    def test_pipeline_preprocessing_only_version_information(self):
        preprocessing_config = {
            "preprocessing": {
                "version_info_target_field": "version_info",
            }
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config}, logger=self.logger)
        test_event = {"any": "content", "version_info": "something random"}
        connector._get_event = mock.MagicMock(return_value=(test_event, None))
        result, _ = connector.get_next(0.01)
        assert result == {"any": "content", "version_info": "something random"}

    def test_get_raw_event_is_callable(self):
        # should be overwritten for special implementation
        result = self.object._get_raw_event(0.001)
        assert result is None

    def test_connector_metrics_counts_processed_events(self):
        self.object.metrics.number_of_processed_events = 0
        self.object._get_event = mock.MagicMock(return_value=({"message": "test"}, None))
        self.object.get_next(0.01)
        assert self.object.metrics.number_of_processed_events == 1

    def test_connector_metrics_does_not_count_if_no_event_was_retrieved(self):
        self.object.metrics.number_of_processed_events = 0
        self.object._get_event = mock.MagicMock(return_value=(None, None))
        self.object.get_next(0.01)
        assert self.object.metrics.number_of_processed_events == 0

    def test_get_next_adds_timestamp_if_configured(self):
        preprocessing_config = {
            "preprocessing": {
                "log_arrival_time_target_field": "arrival_time",
            }
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config}, logger=self.logger)
        connector._get_event = mock.MagicMock(return_value=({"any": "content"}, None))
        result, _ = connector.get_next(0.01)
        target_field = preprocessing_config.get("preprocessing", {}).get(
            "log_arrival_time_target_field"
        )
        assert target_field in result
        assert isinstance(result[target_field], str)
        assert (TimeParser.now() - TimeParser.from_string(result[target_field])).total_seconds() > 0

    def test_pipeline_preprocessing_does_not_add_log_arrival_time_if_target_field_exists_already(
        self,
    ):
        preprocessing_config = {
            "preprocessing": {
                "log_arrival_time_target_field": "arrival_time",
            }
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config}, logger=self.logger)
        test_event = {"any": "content", "arrival_time": "does not matter"}
        connector._get_event = mock.MagicMock(return_value=(test_event, None))
        result, _ = connector.get_next(0.01)
        assert result == {"any": "content", "arrival_time": "does not matter"}

    def test_pipeline_preprocessing_adds_timestamp_delta_if_configured(self):
        preprocessing_config = {
            "preprocessing": {
                "log_arrival_time_target_field": "arrival_time",
                "log_arrival_timedelta": {
                    "target_field": "log_arrival_timedelta",
                    "reference_field": "@timestamp",
                },
            }
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config}, logger=self.logger)
        test_event = {"any": "content", "@timestamp": "1999-09-09T09:09:09.448319+02:00"}
        connector._get_event = mock.MagicMock(return_value=(test_event, None))
        result, _ = connector.get_next(0.01)
        target_field = (
            preprocessing_config.get("preprocessing")
            .get("log_arrival_timedelta")
            .get("target_field")
        )
        assert target_field in result
        assert isinstance(result[target_field], float)

    def test_pipeline_preprocessing_does_not_add_timestamp_delta_if_configured_but_reference_field_not_found(
        self,
    ):
        preprocessing_config = {
            "preprocessing": {
                "log_arrival_time_target_field": "arrival_time",
                "log_arrival_timedelta": {
                    "target_field": "log_arrival_timedelta",
                    "reference_field": "@timestamp",
                },
            }
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config}, logger=self.logger)
        test_event = {"any": "content"}
        connector._get_event = mock.MagicMock(return_value=(test_event, None))
        result, _ = connector.get_next(0.01)
        assert "arrival_time" in result
        assert "log_arrival_timedelta" not in result

    def test_pipeline_preprocessing_does_not_add_timestamp_delta_if_not_configured(self):
        preprocessing_config = {
            "preprocessing": {
                "log_arrival_time_target_field": "arrival_time",
            }
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config}, logger=self.logger)
        test_event = {"any": "content"}
        connector._get_event = mock.MagicMock(return_value=(test_event, None))
        result, _ = connector.get_next(0.01)
        assert "arrival_time" in result

    def test_pipeline_preprocessing_does_not_add_timestamp_delta_if_configured_but_log_arrival_timestamp_not(
        self,
    ):
        preprocessing_config = {
            "preprocessing": {
                "log_arrival_timedelta": {
                    "target_field": "log_arrival_timedelta",
                    "reference_field": "@timestamp",
                },
            }
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config}, logger=self.logger)
        test_event = {"any": "content"}
        connector._get_event = mock.MagicMock(return_value=(test_event, None))
        result, _ = connector.get_next(0.01)
        assert result == {"any": "content"}

    def test_preprocessing_enriches_by_env_variable(self):
        preprocessing_config = {
            "preprocessing": {
                "enrich_by_env_variables": {
                    "enriched_field": "TEST_ENV_VARIABLE",
                },
            }
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config}, logger=self.logger)
        test_event = {"any": "content"}
        os.environ["TEST_ENV_VARIABLE"] = "test_value"
        connector._get_event = mock.MagicMock(return_value=(test_event, None))
        result, _ = connector.get_next(0.01)
        assert result == {"any": "content", "enriched_field": "test_value"}

    def test_preprocessing_enriches_by_multiple_env_variables(self):
        preprocessing_config = {
            "preprocessing": {
                "enrich_by_env_variables": {
                    "enriched_field1": "TEST_ENV_VARIABLE_FOO",
                    "enriched_field2": "TEST_ENV_VARIABLE_BAR",
                },
            }
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config}, logger=self.logger)
        test_event = {"any": "content"}
        os.environ["TEST_ENV_VARIABLE_FOO"] = "test_value_foo"
        os.environ["TEST_ENV_VARIABLE_BAR"] = "test_value_bar"
        connector._get_event = mock.MagicMock(return_value=(test_event, None))
        result, _ = connector.get_next(0.01)
        assert result == {
            "any": "content",
            "enriched_field1": "test_value_foo",
            "enriched_field2": "test_value_bar",
        }

    def test_get_next_counts_number_of_processed_events(self):
        self.object.metrics.number_of_processed_events = 0
        return_value = ({"message": "test message"}, b'{"message": "test message"}')
        self.object._get_event = mock.MagicMock(return_value=return_value)
        self.object.get_next(0.01)
        assert self.object.metrics.number_of_processed_events == 1

    def test_get_next_doesnt_count_numer_of_processed_events_if_event_is_none(self):
        self.object.metrics.number_of_processed_events = 0
        self.object._get_event = mock.MagicMock(return_value=(None, None))
        self.object.get_next(0.01)
        assert self.object.metrics.number_of_processed_events == 0

    def test_get_next_has_time_measurement(self):
        mock_metric = mock.MagicMock()
        self.object.metrics.processing_time_per_event = mock_metric
        return_value = ({"message": "test message"}, b'{"message": "test message"}')
        self.object._get_event = mock.MagicMock(return_value=return_value)
        self.object.get_next(0.01)
        assert isinstance(self.object.metrics.processing_time_per_event, mock.MagicMock)
        # asserts entering context manager in metrics.metrics.Metric.measure_time
        mock_metric.assert_has_calls([mock.call.tracker.labels().time().__enter__()])


class BaseOutputTestCase(BaseConnectorTestCase):
    def test_is_output_instance(self):
        assert isinstance(self.object, Output)

    def test_store_counts_processed_events(self):
        self.object.metrics.number_of_processed_events = 0
        self.object.store({"message": "my event message"})
        assert self.object.metrics.number_of_processed_events == 1

    def test_store_failed_counts_failed_events(self):
        self.object.metrics.number_of_failed_events = 0
        self.object.store_failed("error", {"message": "my event message"}, {})
        assert self.object.metrics.number_of_failed_events == 1

    def test_store_calls_batch_finished_callback(self):
        self.object.input_connector = mock.MagicMock()
        self.object.store({"message": "my event message"})
        self.object.input_connector.batch_finished_callback.assert_called()
