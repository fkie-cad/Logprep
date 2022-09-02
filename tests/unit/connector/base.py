# pylint: disable=missing-docstring
# pylint: disable=protected-access
import base64
import json
import zlib
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

    def test_get_next_with_hmac_of_raw_message(self):
        kafka_config = deepcopy(self.CONFIG)
        kafka_config.update(
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
        kafka = ConnectorFactory.create({"test connector": kafka_config}, logger=self.logger)
        test_event = {"message": "with_content"}
        raw_encoded_test_event = json.dumps(test_event, separators=(",", ":")).encode("utf-8")
        kafka._get_event = mock.MagicMock(return_value=(test_event.copy(), raw_encoded_test_event))
        expected_event = {
            "message": "with_content",
            "Hmac": {
                "compressed_base64": "eJyrVspNLS5OTE9VslIqzyzJiE/OzytJzStRqgUAgKkJtg==",
                "hmac": "dfe78753da634d7b76760488dbb2cf7bfe1b0e4e794930c36e98a984b6b6be63",
            },
        }
        kafka_next_msg, _ = kafka.get_next(1)
        assert kafka_next_msg == expected_event, "Output event with hmac is not as expected"

        decoded = base64.b64decode(kafka_next_msg["Hmac"]["compressed_base64"])
        decoded_message = zlib.decompress(decoded)
        assert test_event == json.loads(
            decoded_message.decode("utf-8")
        ), "The hmac base massage was not correctly encoded and compressed. "

    def test_get_next_with_hmac_of_subfield(self):
        kafka_config = deepcopy(self.CONFIG)
        kafka_config.update(
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
        kafka = ConnectorFactory.create({"test connector": kafka_config}, logger=self.logger)
        test_event = {"message": {"with_subfield": "content"}}
        raw_encoded_test_event = json.dumps(test_event, separators=(",", ":")).encode("utf-8")
        kafka._get_event = mock.MagicMock(return_value=(test_event.copy(), raw_encoded_test_event))
        expected_event = {
            "message": {"with_subfield": "content"},
            "Hmac": {
                "compressed_base64": "eJxLzs8rSc0rAQALywL8",
                "hmac": "e01e02a09cb270eebf7ae846b96d7306681038bd279f85d44c77019e0c4f6316",
            },
        }

        kafka_next_msg, _ = kafka.get_next(1)
        assert kafka_next_msg == expected_event

        decoded = base64.b64decode(kafka_next_msg["Hmac"]["compressed_base64"])
        decoded_message = zlib.decompress(decoded)
        assert test_event["message"]["with_subfield"] == decoded_message.decode(
            "utf-8"
        ), "The hmac base massage was not correctly encoded and compressed. "

    def test_get_next_with_hmac_of_non_existing_subfield(self):
        kafka_config = deepcopy(self.CONFIG)
        kafka_config.update(
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
        kafka = ConnectorFactory.create({"test connector": kafka_config}, logger=self.logger)
        test_event = {"message": {"with_subfield": "content"}}
        raw_encoded_test_event = json.dumps(test_event, separators=(",", ":")).encode("utf-8")
        kafka._get_event = mock.MagicMock(return_value=(test_event.copy(), raw_encoded_test_event))
        expected_output_event = {
            "message": {"with_subfield": "content"},
            "Hmac": {
                "hmac": "error",
                "compressed_base64": "eJyzSa0oSE0uSU1RyMhNTFYoSSxKTy1RSMtMzUlRUM/Lz4tPrcgsLsnMS48Hi"
                                     "6kr5OUDpfNL81LsAJILFeQ=",
            },
        }
        kafka_next_msg, non_critical_error_msg = kafka.get_next(1)
        assert kafka_next_msg == expected_output_event
        decoded = base64.b64decode(kafka_next_msg["Hmac"]["compressed_base64"])
        decoded_message = zlib.decompress(decoded).decode("utf8")
        assert decoded_message == "<expected hmac target field 'non_existing_field' not found>"
        assert non_critical_error_msg == "Couldn't find the hmac target field 'non_existing_field'"

    def test_get_next_with_hmac_result_in_dotted_subfield(self):
        kafka_config = deepcopy(self.CONFIG)
        kafka_config.update(
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
        kafka = ConnectorFactory.create({"test connector": kafka_config}, logger=self.logger)
        test_event = {"message": "with_content"}
        raw_encoded_test_event = json.dumps(test_event, separators=(",", ":")).encode("utf-8")
        kafka._get_event = mock.MagicMock(return_value=(test_event.copy(), raw_encoded_test_event))
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

        kafka_next_msg, _ = kafka.get_next(1)
        assert kafka_next_msg == expected_event
        decoded = base64.b64decode(
            kafka_next_msg["Hmac"]["dotted"]["subfield"]["compressed_base64"]
        )
        decoded_message = zlib.decompress(decoded)
        assert test_event == json.loads(
            decoded_message.decode("utf-8")
        ), "The hmac base massage was not correctly encoded and compressed. "

    def test_get_next_with_hmac_result_in_already_existing_subfield(self):
        kafka_config = deepcopy(self.CONFIG)
        kafka_config.update(
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
        kafka = ConnectorFactory.create({"test connector": kafka_config}, logger=self.logger)
        test_event = {"message": {"with_subfield": "content"}}
        raw_encoded_test_event = json.dumps(test_event, separators=(",", ":")).encode("utf-8")
        kafka._get_event = mock.MagicMock(return_value=(test_event.copy(), raw_encoded_test_event))
        _, non_critical_error_msg = kafka.get_next(1)
        assert (
                non_critical_error_msg
                == "Couldn't add the hmac to the input event as the desired output field 'message' already exist."
        )

    def test_get_next_with_wrong_or_missing_hmac_config(self):
        # TODO: write hmac config validator -> see logprep.abc.input.Input.Config
        kafka_config = deepcopy(self.CONFIG)
        kafka_config.update(
            {
                "preprocessing": {
                    "hmac": {
                        "key": "hmac-test-key",
                        "output_field": "message",
                    }
                }
            }
        )
        _ = ConnectorFactory.create({"test connector": kafka_config}, logger=self.logger)
        assert False, (
            "This test should fail because of missing hmac target option -> validator is "
            "missing yet though"
        )

        # for key in ["target", "key", "output_field"]:
        #     config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
        #     config["consumer"]["hmac"] = {
        #         "target": "<RAW_MSG>",
        #         "key": "hmac-test-key",
        #         "output_field": "Hmac",
        #     }
        #
        #     # drop option to test for missing option error message
        #     del config["consumer"]["hmac"][key]
        #     with pytest.raises(
        #         InvalidConfigurationError, match=rf"Hmac option\(s\) missing: {{'{key}'}}"
        #     ):
        #         _ = ConfluentKafkaInputFactory.create_from_configuration(config)
        #
        # # set default config
        # config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
        #
        # # add additional unknown option and test for error message
        # config["consumer"]["hmac"] = {"unknown": "option"}
        # with pytest.raises(
        #     InvalidConfigurationError, match=r"Confluent Kafka Input: Unknown Option: unknown"
        # ):
        #     _ = ConfluentKafkaInputFactory.create_from_configuration(config)

    # def test_get_next_with_broken_hmac_config(self):
    #     for key in ["target", "key", "output_field"]:
    #         # set default config
    #         config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
    #         config["consumer"]["hmac"] = {
    #             "target": "<RAW_MSG>",
    #             "key": "hmac-test-key",
    #             "output_field": "Hmac",
    #         }

    #         # empty one option and test for error message
    #         config["consumer"]["hmac"][key] = ""
    #         with pytest.raises(
    #             InvalidConfigurationError, match=rf"Hmac option '{key}' is empty: ''"
    #         ):
    #             _ = ConfluentKafkaInputFactory.create_from_configuration(config)

    # def test_get_next_without_hmac(self):
    #     config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
    #     kafka = ConfluentKafkaInputFactory.create_from_configuration(config)

    #     # configuration is not set
    #     assert kafka._config["consumer"]["hmac"]["target"] == ""
    #     assert kafka._config["consumer"]["hmac"]["key"] == ""
    #     assert kafka._config["consumer"]["hmac"]["output_field"] == ""

    #     test_event = {"message": "with_content"}
    #     expected_event = {"message": "with_content"}

    #     kafka._consumer = ConsumerJsonMock(test_event)

    #     # output message is the same as the input message
    #     kafka_next_msg = kafka.get_next(1)
    #     assert kafka_next_msg == expected_event
