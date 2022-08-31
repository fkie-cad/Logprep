# pylint: disable=missing-docstring
# pylint: disable=wrong-import-order
# pylint: disable=no-self-use
import json
from unittest.mock import patch

import arrow
import pytest

from logprep._version import get_versions
from logprep.util.json_handling import dump_config_as_file
from tests.acceptance.util import mock_kafka_and_run_pipeline, get_default_logprep_config


@pytest.fixture(name="config")
def fixture_config():
    pipeline = [
        {
            "normalizername": {
                "type": "normalizer",
                "specific_rules": ["tests/testdata/acceptance/normalizer/rules_static/specific"],
                "generic_rules": ["tests/testdata/acceptance/normalizer/rules_static/generic"],
                "regex_mapping": "tests/testdata/acceptance/normalizer/rules_static/"
                "regex_mapping.yml",
            }
        }
    ]
    return get_default_logprep_config(pipeline)


class TestFullHMACPass:
    def test_full_message_pass_with_hmac(self, tmp_path, config):
        config_path = str(tmp_path / "generated_config.yml")
        dump_config_as_file(config_path, config)

        with patch(
            "logprep.connector.connector_factory.ConnectorFactory.create"
        ) as mock_connector_factory:
            input_test_event = {"test": "message"}
            expected_output_event = {
                "test": "message",
                "hmac": {
                    "hmac": "5a77054b5f1d9ea60000520a4e2cf661e7a11de4205ca70c6977fc8040076a6e",
                    "compressed_base64": "eJyrVipJLS5RslLKTS0uTkxPVaoFADwCBmA=",
                },
            }

            kafka_output_file = mock_kafka_and_run_pipeline(
                config, input_test_event, mock_connector_factory, tmp_path
            )

            # read logprep kafka output from mocked kafka file producer
            with open(kafka_output_file, "r", encoding="utf-8") as output_file:
                outputs = output_file.readlines()
                assert len(outputs) == 1, "Expected only one default kafka output"

                target, event = outputs[0].split(" ", maxsplit=1)
                event = json.loads(event)
                assert target == "test_input_processed"
                assert event == expected_output_event

    def test_full_message_pass_with_new_hmac_config_position(self, tmp_path, config):
        config["connector"]["consumer"]["preprocessing"] = {
            "hmac": config["connector"]["consumer"]["hmac"]
        }
        del config["connector"]["consumer"]["hmac"]
        config_path = str(tmp_path / "generated_config.yml")
        dump_config_as_file(config_path, config)

        with patch(
            "logprep.connector.connector_factory.ConnectorFactory.create"
        ) as mock_connector_factory:
            input_test_event = {"test": "message"}
            expected_output_event = {
                "test": "message",
                "hmac": {
                    "hmac": "5a77054b5f1d9ea60000520a4e2cf661e7a11de4205ca70c6977fc8040076a6e",
                    "compressed_base64": "eJyrVipJLS5RslLKTS0uTkxPVaoFADwCBmA=",
                },
            }

            kafka_output_file = mock_kafka_and_run_pipeline(
                config, input_test_event, mock_connector_factory, tmp_path
            )

            # read logprep kafka output from mocked kafka file producer
            with open(kafka_output_file, "r", encoding="utf-8") as output_file:
                outputs = output_file.readlines()
                assert len(outputs) == 1, "Expected only one default kafka output"

                target, event = outputs[0].split(" ", maxsplit=1)
                event = json.loads(event)
                assert target == "test_input_processed"
                assert event == expected_output_event


class TestVersionInfoTargetField:
    def test_version_info_target_field_will_be_added_if_configured(self, tmp_path, config):
        config["connector"]["consumer"]["preprocessing"] = {
            "version_info_target_field": "version_info"
        }
        config_path = str(tmp_path / "generated_config.yml")
        dump_config_as_file(config_path, config)

        with patch(
            "logprep.connector.connector_factory.ConnectorFactory.create"
        ) as mock_connector_factory:
            input_test_event = {"test": "message"}
            expected_output_event = {
                "test": "message",
                "hmac": {
                    "hmac": "5a77054b5f1d9ea60000520a4e2cf661e7a11de4205ca70c6977fc8040076a6e",
                    "compressed_base64": "eJyrVipJLS5RslLKTS0uTkxPVaoFADwCBmA=",
                },
                "version_info": {
                    "logprep": get_versions().get("version"),
                    "configuration": "unset",
                },
            }

            kafka_output_file = mock_kafka_and_run_pipeline(
                config, input_test_event, mock_connector_factory, tmp_path
            )

            # read logprep kafka output from mocked kafka file producer
            with open(kafka_output_file, "r", encoding="utf-8") as output_file:
                outputs = output_file.readlines()
                assert len(outputs) == 1, "Expected only one default kafka output"

                target, event = outputs[0].split(" ", maxsplit=1)
                event = json.loads(event)
                assert target == "test_input_processed"
                assert event == expected_output_event

    def test_version_info_target_field_will_not_be_added_if_not_configured(self, tmp_path, config):
        consumer_config = config.get("connector", {}).get("consumer", {})
        preprocessing_config = consumer_config.get("preprocessing", {})
        assert preprocessing_config.get("version_info_target_field") is None
        config_path = str(tmp_path / "generated_config.yml")
        dump_config_as_file(config_path, config)

        with patch(
            "logprep.connector.connector_factory.ConnectorFactory.create"
        ) as mock_connector_factory:
            input_test_event = {"test": "message"}
            expected_output_event = {
                "test": "message",
                "hmac": {
                    "hmac": "5a77054b5f1d9ea60000520a4e2cf661e7a11de4205ca70c6977fc8040076a6e",
                    "compressed_base64": "eJyrVipJLS5RslLKTS0uTkxPVaoFADwCBmA=",
                },
            }

            kafka_output_file = mock_kafka_and_run_pipeline(
                config, input_test_event, mock_connector_factory, tmp_path
            )

            # read logprep kafka output from mocked kafka file producer
            with open(kafka_output_file, "r", encoding="utf-8") as output_file:
                outputs = output_file.readlines()
                assert len(outputs) == 1, "Expected only one default kafka output"

                target, event = outputs[0].split(" ", maxsplit=1)
                event = json.loads(event)
                assert target == "test_input_processed"
                assert event == expected_output_event


class TestAddTimestamps:
    def test_timestamp_field_will_be_added_if_configured(self, tmp_path, config):
        config["connector"]["consumer"]["preprocessing"] = {"add_timestamp": "arrival_time"}
        config_path = str(tmp_path / "generated_config.yml")
        dump_config_as_file(config_path, config)

        with patch(
            "logprep.connector.connector_factory.ConnectorFactory.create"
        ) as mock_connector_factory:
            input_test_event = {"test": "message"}
            expected_output_event = {
                "test": "message",
                "hmac": {
                    "hmac": "5a77054b5f1d9ea60000520a4e2cf661e7a11de4205ca70c6977fc8040076a6e",
                    "compressed_base64": "eJyrVipJLS5RslLKTS0uTkxPVaoFADwCBmA=",
                },
            }

            kafka_output_file = mock_kafka_and_run_pipeline(
                config, input_test_event, mock_connector_factory, tmp_path
            )

            # read logprep kafka output from mocked kafka file producer
            with open(kafka_output_file, "r", encoding="utf-8") as output_file:
                outputs = output_file.readlines()
                assert len(outputs) == 1, "Expected only one default kafka output"

                target, event = outputs[0].split(" ", maxsplit=1)
                event = json.loads(event)
                assert target == "test_input_processed"

                arrival_time = event.pop("arrival_time")
                assert arrival_time
                assert isinstance(arrival_time, str)
                assert (arrow.now() - arrow.get(arrival_time)).total_seconds() < 0.1
                assert event == expected_output_event

    def test_timestamp_field_will_not_be_added_if_not_configured(self, tmp_path, config):
        consumer_config = config.get("connector", {}).get("consumer", {})
        preprocessing_config = consumer_config.get("preprocessing", {})
        assert preprocessing_config.get("add_timestamp") is None
        config_path = str(tmp_path / "generated_config.yml")
        dump_config_as_file(config_path, config)

        with patch(
            "logprep.connector.connector_factory.ConnectorFactory.create"
        ) as mock_connector_factory:
            input_test_event = {"test": "message"}
            expected_output_event = {
                "test": "message",
                "hmac": {
                    "hmac": "5a77054b5f1d9ea60000520a4e2cf661e7a11de4205ca70c6977fc8040076a6e",
                    "compressed_base64": "eJyrVipJLS5RslLKTS0uTkxPVaoFADwCBmA=",
                },
            }

            kafka_output_file = mock_kafka_and_run_pipeline(
                config, input_test_event, mock_connector_factory, tmp_path
            )

            # read logprep kafka output from mocked kafka file producer
            with open(kafka_output_file, "r", encoding="utf-8") as output_file:
                outputs = output_file.readlines()
                assert len(outputs) == 1, "Expected only one default kafka output"

                target, event = outputs[0].split(" ", maxsplit=1)
                event = json.loads(event)
                assert target == "test_input_processed"
                assert event == expected_output_event

    def test_times_delta_field_will_be_added_if_configured_and_if_arrival_and_timestamp(
        self, tmp_path, config
    ):
        config["connector"]["consumer"]["preprocessing"] = {
            "add_timestamp": "arrival_time",
            "add_timestamp_delta": "delta_time",
        }
        config_path = str(tmp_path / "generated_config.yml")
        dump_config_as_file(config_path, config)

        with patch(
            "logprep.connector.connector_factory.ConnectorFactory.create"
        ) as mock_connector_factory:
            input_test_event = {"test": "message", "@timestamp": "1999-01-01T01:01+01"}
            expected_output_event = {
                "test": "message",
                "hmac": {
                    "hmac": "19e0ae4d27cfa6dcf3adb738f8938d67768a8279d21eb92495e255a1b966ddc7",
                    "compressed_base64": "eJyrVipJLS5RslLKTS0uTkxPVdJRcijJBHJKEnMLgMKGlpaWugaGQBRiYGhlYKhtYKhUCwDGgA82",
                },
            }

            kafka_output_file = mock_kafka_and_run_pipeline(
                config, input_test_event, mock_connector_factory, tmp_path
            )

            # read logprep kafka output from mocked kafka file producer
            with open(kafka_output_file, "r", encoding="utf-8") as output_file:
                outputs = output_file.readlines()
                assert len(outputs) == 1, "Expected only one default kafka output"

                target, event = outputs[0].split(" ", maxsplit=1)
                event = json.loads(event)
                assert target == "test_input_processed"

                assert event.pop("@timestamp")
                assert event.pop("arrival_time")
                delta_time = event.pop("delta_time")
                assert delta_time
                assert isinstance(delta_time, float)
                assert event == expected_output_event

    def test_times_delta_field_will_not_be_added_if_configured_and_if_arrival_and_no_timestamp(
        self, tmp_path, config
    ):
        config["connector"]["consumer"]["preprocessing"] = {
            "add_timestamp": "arrival_time",
            "add_timestamp_delta": "delta_time",
        }
        config_path = str(tmp_path / "generated_config.yml")
        dump_config_as_file(config_path, config)

        with patch(
            "logprep.connector.connector_factory.ConnectorFactory.create"
        ) as mock_connector_factory:
            input_test_event = {"test": "message"}
            expected_output_event = {
                "test": "message",
                "hmac": {
                    "hmac": "5a77054b5f1d9ea60000520a4e2cf661e7a11de4205ca70c6977fc8040076a6e",
                    "compressed_base64": "eJyrVipJLS5RslLKTS0uTkxPVaoFADwCBmA=",
                },
            }

            kafka_output_file = mock_kafka_and_run_pipeline(
                config, input_test_event, mock_connector_factory, tmp_path
            )

            # read logprep kafka output from mocked kafka file producer
            with open(kafka_output_file, "r", encoding="utf-8") as output_file:
                outputs = output_file.readlines()
                assert len(outputs) == 1, "Expected only one default kafka output"

                target, event = outputs[0].split(" ", maxsplit=1)
                event = json.loads(event)
                assert target == "test_input_processed"

                assert event.pop("arrival_time")
                assert event == expected_output_event

    def test_times_delta_field_will_be_added_if_configured_and_if_timestamp_but_no_arrival(
        self, tmp_path, config
    ):
        config["connector"]["consumer"]["preprocessing"] = {
            "add_timestamp_delta": "delta_time",
        }
        config_path = str(tmp_path / "generated_config.yml")
        dump_config_as_file(config_path, config)

        with patch(
            "logprep.connector.connector_factory.ConnectorFactory.create"
        ) as mock_connector_factory:
            input_test_event = {"test": "message", "@timestamp": "1999-01-01T01:01+01"}
            expected_output_event = {
                "test": "message",
                "hmac": {
                    "hmac": "19e0ae4d27cfa6dcf3adb738f8938d67768a8279d21eb92495e255a1b966ddc7",
                    "compressed_base64": "eJyrVipJLS5RslLKTS0uTkxPVdJRcijJBHJKEnMLgMKGlpaWugaGQBRiYGhlYKhtYKhUCwDGgA82",
                },
            }

            kafka_output_file = mock_kafka_and_run_pipeline(
                config, input_test_event, mock_connector_factory, tmp_path
            )

            # read logprep kafka output from mocked kafka file producer
            with open(kafka_output_file, "r", encoding="utf-8") as output_file:
                outputs = output_file.readlines()
                assert len(outputs) == 1, "Expected only one default kafka output"

                target, event = outputs[0].split(" ", maxsplit=1)
                event = json.loads(event)
                assert target == "test_input_processed"

                assert event.pop("@timestamp")
                assert event == expected_output_event
