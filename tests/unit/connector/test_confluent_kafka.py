# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init
# pylint: disable=no-self-use
import json
import pytest
from base64 import b64decode
from copy import deepcopy
from datetime import datetime
from json import loads
from math import isclose
from socket import getfqdn
from unittest import mock
from zlib import decompress


from logprep.connector.connector_factory_error import InvalidConfigurationError
from logprep.connector.confluent_kafka.input import (
    ConfluentKafkaInput,
    ConfluentKafkaInputFactory,
)
from logprep.connector.confluent_kafka.confluent_kafka_output import (
    ConfluentKafkaOutput,
    UnknownOptionError,
    ConfluentKafkaOutputFactory,
)
from logprep.input.input import CriticalInputError
from logprep.output.output import CriticalOutputError


class TestConfluentKafkaFactory:
    valid_configuration = {
        "type": "confluentkafka",
        "bootstrapservers": ["testserver:9092"],
        "consumer": {
            "topic": "test_input_raw",
            "group": "test_consumergroup",
            "auto_commit": False,
            "session_timeout": 654321,
            "enable_auto_offset_store": True,
            "offset_reset_policy": "latest",
        },
        "producer": {
            "topic": "test_input_processed",
            "error_topic": "test_error_producer",
            "ack_policy": "1",
            "compression": "gzip",
            "maximum_backlog": 987654,
            "send_timeout": 2,
            "flush_timeout": 30,
            "linger_duration": 4321,
        },
        "ssl": {
            "cafile": "test_cafile",
            "certfile": "test_certfile",
            "keyfile": "test_keyfile",
            "password": "test_password",
        },
    }

    # pylint: disable=attribute-defined-outside-init
    def setup_method(self, _method_name):
        self.config = deepcopy(self.valid_configuration)

    # pylint: enable=attribute-defined-outside-init

    def test_fails_if_configuration_is_not_a_dictionary(self):
        _ = ConfluentKafkaInputFactory.create_from_configuration(self.config)
        for i in ["string", 123, 456.789, None, ConfluentKafkaInputFactory, ["list"], {"set"}]:
            with pytest.raises(InvalidConfigurationError):
                ConfluentKafkaInputFactory.create_from_configuration(i)
            with pytest.raises(InvalidConfigurationError):
                ConfluentKafkaOutputFactory.create_from_configuration(i)

    def test_fails_if_any_base_config_value_is_missing_for_input(self):
        configuration = deepcopy(self.valid_configuration)
        del configuration["bootstrapservers"]
        with pytest.raises(InvalidConfigurationError):
            ConfluentKafkaInputFactory.create_from_configuration(configuration)

        for i in ["topic", "group"]:
            configuration = deepcopy(self.valid_configuration)
            del configuration["consumer"][i]

            with pytest.raises(InvalidConfigurationError):
                ConfluentKafkaInputFactory.create_from_configuration(configuration)

    def test_fails_if_any_base_config_value_is_missing_for_output(self):
        configuration = deepcopy(self.valid_configuration)
        _ = ConfluentKafkaInputFactory.create_from_configuration(configuration)

        del configuration["bootstrapservers"]
        with pytest.raises(InvalidConfigurationError):
            ConfluentKafkaOutputFactory.create_from_configuration(configuration)

        configuration = deepcopy(self.valid_configuration)
        del configuration["producer"]["topic"]

        with pytest.raises(InvalidConfigurationError):
            ConfluentKafkaOutputFactory.create_from_configuration(configuration)

    def test_ssl_config_values_are_none_if_section_is_missing(self):
        del self.config["ssl"]
        kafka = ConfluentKafkaInputFactory.create_from_configuration(self.config)
        assert not all(kafka._config["ssl"][key] for key in kafka._config["ssl"])

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_create_consume_calls_subscribe(self, _):
        kafka = ConfluentKafkaInputFactory.create_from_configuration(self.config)
        kafka._create_consumer()
        kafka._consumer.subscribe.assert_called()

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_get_next_creates_consumer_if_consumer_is_none(self, mock_consumer):
        kafka = ConfluentKafkaInputFactory.create_from_configuration(self.config)
        assert kafka._consumer is None
        with pytest.raises(CriticalInputError):  # silence mock error
            kafka.get_next(1)
        assert kafka._consumer == mock_consumer.return_value

    def test_get_next_raises_critical_input_error_if_unvalid_json(self):
        kafka = ConfluentKafkaInputFactory.create_from_configuration(self.config)
        kafka._consumer = mock.MagicMock()
        mock_record = mock.MagicMock()
        mock_record.error = mock.MagicMock()
        mock_record.error.return_value = None
        kafka._consumer.poll = mock.MagicMock(return_value=mock_record)
        mock_record.value = mock.MagicMock()
        mock_record.value.return_value = "I'm not valid json".encode("utf8")
        with pytest.raises(CriticalInputError, match=r"not a valid json"):
            kafka.get_next(1)

    def test_get_next_raises_critical_input_error_if_not_a_dict(self):
        kafka = ConfluentKafkaInputFactory.create_from_configuration(self.config)
        kafka._consumer = mock.MagicMock()
        kafka._add_hmac = True
        mock_record = mock.MagicMock()
        mock_record.error = mock.MagicMock()
        mock_record.error.return_value = None
        kafka._consumer.poll = mock.MagicMock(return_value=mock_record)
        mock_record.value = mock.MagicMock()
        mock_record.value.return_value = '[{"element":"in list"}]'.encode("utf8")
        with pytest.raises(CriticalInputError, match=r"could not be parsed as dict"):
            kafka.get_next(1)

    def test_ssl_config_values_are_set_if_section_ssl_section_is_present(self):
        kafka = ConfluentKafkaInputFactory.create_from_configuration(self.config)

        assert kafka._config["ssl"]["cafile"] == self.config["ssl"]["cafile"]
        assert kafka._config["ssl"]["certfile"] == self.config["ssl"]["certfile"]
        assert kafka._config["ssl"]["keyfile"] == self.config["ssl"]["keyfile"]
        assert kafka._config["ssl"]["password"] == self.config["ssl"]["password"]

    def test_various_options_are_set_from_configuration(self):
        kafka_input = ConfluentKafkaInputFactory.create_from_configuration(self.config)
        kafka_output = ConfluentKafkaOutputFactory.create_from_configuration(self.config)

        assert kafka_input._config["consumer"]["auto_commit"] is False
        assert (
            kafka_input._config["consumer"]["session_timeout"]
            == self.config["consumer"]["session_timeout"]
        )
        assert (
            kafka_input._config["consumer"]["offset_reset_policy"]
            == self.config["consumer"]["offset_reset_policy"]
        )

        assert (
            kafka_output._config["producer"]["ack_policy"] == self.config["producer"]["ack_policy"]
        )
        assert (
            kafka_output._config["producer"]["compression"]
            == self.config["producer"]["compression"]
        )
        assert (
            kafka_output._config["producer"]["flush_timeout"]
            == self.config["producer"]["flush_timeout"]
        )
        assert (
            kafka_output._config["producer"]["linger_duration"]
            == self.config["producer"]["linger_duration"]
        )
        assert (
            kafka_output._config["producer"]["maximum_backlog"]
            == self.config["producer"]["maximum_backlog"]
        )
        assert (
            kafka_output._config["producer"]["send_timeout"]
            == self.config["producer"]["send_timeout"]
        )

    def test_config_has_hmac_settings(self):
        self.config["consumer"]["hmac"] = {
            "target": "<RAW_MSG>",
            "key": "hmac-test-key",
            "output_field": "Hmac",
        }

        kafka = ConfluentKafkaInputFactory.create_from_configuration(self.config)

        assert kafka._config["consumer"]["hmac"]["target"] == "<RAW_MSG>"
        assert kafka._config["consumer"]["hmac"]["key"] == "hmac-test-key"
        assert kafka._config["consumer"]["hmac"]["output_field"] == "Hmac"

    def test_raises_invalidconfigurationerror_for_unknown_option(self):
        self.config.get("producer").update({"unknown": "option"})
        with pytest.raises(InvalidConfigurationError, match=r"Unknown\sOption:\s+unknown"):
            _ = ConfluentKafkaOutputFactory.create_from_configuration(self.config)


class NotJsonSerializableMock:
    pass


class ProducerMock:
    def __init__(self):
        self.produced = []

    def produce(self, topic, value):
        self.produced.append((topic, loads(value.decode())))

    def poll(self, timeout):
        pass

    def flush(self, timeout):
        pass


class ConfluentKafkaOutputForTest(ConfluentKafkaOutput):
    def _create_producer(self):
        self._producer = ProducerMock()


class RecordMock:
    def __init__(self, record_value, record_error):
        self.record_value = record_value
        self.record_error = record_error

    @staticmethod
    def partition():
        return 0

    def value(self):
        if self.record_value is None:
            return None
        return self.record_value.encode("utf-8")

    def error(self):
        if self.record_error is None:
            return None
        return self.record_error

    @staticmethod
    def offset():
        return -1


class ConsumerJsonMock:
    def __init__(self, record):
        self.record = json.dumps(record, separators=(",", ":"))

    def poll(self, timeout):  # pylint: disable=unused-argument
        return RecordMock(self.record, None)


class ConsumerInvalidJsonMock:
    def poll(self, timeout):  # pylint: disable=unused-argument
        return RecordMock("This is not a valid JSON string!", None)


class ConsumerRecordWithKafkaErrorMock:
    def poll(self, timeout):  # pylint: disable=unused-argument
        return RecordMock('{"test_variable" : "test value" }', "An arbitrary confluent-kafka error")


class ConsumerNoRecordMock:
    def poll(self, timeout):  # pylint: disable=unused-argument
        return None


def decode_b64_and_decompress(message):
    decoded = b64decode(message)
    return decompress(decoded)


class TestConfluentKafka:
    default_configuration = {
        "bootstrap.servers": "bootstrap1,bootstrap2",
        "group.id": "consumer_group",
        "enable.auto.commit": True,
        "enable.auto.offset.store": True,
        "session.timeout.ms": 6000,
        "default.topic.config": {"auto.offset.reset": "smallest"},
        "acks": "all",
        "compression.type": "none",
        "queue.buffering.max.messages": 31337,
        "linger.ms": 0,
    }

    # pylint: disable=attribute-defined-outside-init
    def setup_method(self, _):
        self.config = deepcopy(self.default_configuration)
        self.kafka_input = ConfluentKafkaInput(
            ["bootstrap1", "bootstrap2"], "consumer_topic", "consumer_group", True
        )
        self.kafka_output = ConfluentKafkaOutput(
            ["bootstrap1", "bootstrap2"], "producer_topic", "producer_error_topic"
        )

    # pylint: enable=attribute-defined-outside-init

    def remove_options(self, *args):
        for key in args:
            del self.config[key]

    def test_implements_abstract_methods(self):
        try:
            ConfluentKafkaOutput(["127.0.0.1:27001"], "producertopic", "producer_error_topic")
        except TypeError as err:
            pytest.fail(f"Must implement abstract methods: {str(err)}")

    def test_describe_endpoint_returns_kafka_with_first_boostrap_config(self):
        assert self.kafka_input.describe_endpoint() == "Kafka Input: bootstrap1"
        assert self.kafka_output.describe_endpoint() == "Kafka Output: bootstrap1"

    def test_client_id_is_set_to_hostname(self):
        assert self.kafka_input._client_id == getfqdn()
        assert self.kafka_output._client_id == getfqdn()

    def test_set_option_fails_for_unknown_and_construction_options(self):
        for i in [
            "unknown",
            "no_such_option",
            "consumer_no_such_option",
            "consumer_group",
            "consumer_topic",
        ]:
            with pytest.raises(UnknownOptionError):
                self.kafka_input.set_option({"consumer": {i: True}}, "consumer")
        for i in [
            "unknown",
            "no_such_option",
            "producer_option",
            "producer_topic",
            "producer_error_topic",
        ]:
            with pytest.raises(UnknownOptionError):
                self.kafka_output.set_option({"producer": {i: True}}, "producer")

    def test_set_option_accepts_known_non_constructor_non_ssl_options(self):
        consumer_options = [
            {"consumer": {"auto_commit": True}},
            {"consumer": {"session_timeout": 0}},
            {"consumer": {"offset_reset_policy": "smallest"}},
        ]
        producer_options = [
            {"producer": {"send_timeout": 0}},
            {"producer": {"flush_timeout": 30}},
            {"producer": {"linger_duration": 0}},
            {"producer": {"maximum_backlog": 10 * 1000}},
            {"producer": {"compression": "none"}},
            {"producer": {"ack_policy": "all"}},
        ]
        try:
            for i in consumer_options:
                self.kafka_input.set_option(i, "consumer")
            for i in producer_options:
                self.kafka_output.set_option(i, "producer")
        except UnknownOptionError:
            pytest.fail("set_option should allow setting non-constructor and non-ssl options.")

    def test_create_confluent_settings_returns_expected_dict_without_ssl(self):
        self.kafka_output.set_option({"producer": {"maximum_backlog": 31337}}, "producer")
        expected_config = deepcopy(self.config)
        self._delete_consumer_settings(expected_config)
        assert self.kafka_output._create_confluent_settings() == expected_config

    def test_create_confluent_settings_returns_expected_dict_with_ssl(self):
        self.kafka_output.set_option({"producer": {"maximum_backlog": 42}}, "producer")
        self.kafka_input.set_ssl_config("cafile", "certificatefile", "keyfile", "password")
        self.kafka_output.set_ssl_config("cafile", "certificatefile", "keyfile", "password")

        self.config.update(
            {
                "queue.buffering.max.messages": 42,
                "security.protocol": "SSL",
                "ssl.ca.location": "cafile",
                "ssl.certificate.location": "certificatefile",
                "ssl.key.location": "keyfile",
                "ssl.key.password": "password",
            }
        )

        kafka_input_cfg = self.kafka_input._create_confluent_settings()
        expected_config = deepcopy(self.config)
        self._delete_producer_settings(expected_config)
        assert kafka_input_cfg == expected_config

        kafka_output_cfg = self.kafka_output._create_confluent_settings()
        expected_config = deepcopy(self.config)
        self._delete_consumer_settings(expected_config)
        assert kafka_output_cfg == expected_config

    def test_create_confluent_settings_contains_expected_values(self):
        options = {
            "consumer": {
                "auto_commit": False,
                "session_timeout": 23456,
                "offset_reset_policy": "latest",
            },
            "producer": {
                "ack_policy": "1",
                "compression": "gzip",
                "maximum_backlog": 4711,
                "linger_duration": 12345,
            },
        }

        self.kafka_input.set_option(options, "consumer")
        self.config["enable.auto.commit"] = False
        self.config["session.timeout.ms"] = 23456
        self.config["default.topic.config"]["auto.offset.reset"] = "latest"
        expected_config = deepcopy(self.config)
        self._delete_producer_settings(expected_config)
        assert self.kafka_input._create_confluent_settings() == expected_config

        self.kafka_output.set_option(options, "producer")
        self.config["acks"] = "1"
        self.config["compression.type"] = "gzip"
        self.config["queue.buffering.max.messages"] = 4711
        self.config["linger.ms"] = 12345
        expected_config = deepcopy(self.config)
        self._delete_consumer_settings(expected_config)
        assert self.kafka_output._create_confluent_settings() == expected_config

    @staticmethod
    def _delete_producer_settings(expected_config):
        del expected_config["acks"]
        del expected_config["compression.type"]
        del expected_config["linger.ms"]
        del expected_config["queue.buffering.max.messages"]

    @staticmethod
    def _delete_consumer_settings(expected_config):
        del expected_config["default.topic.config"]
        del expected_config["enable.auto.commit"]
        del expected_config["enable.auto.offset.store"]
        del expected_config["group.id"]
        del expected_config["session.timeout.ms"]

    def test_store_sends_event_to_expected_topic(self):
        producer_topic = "producer_topic"
        event = {"field": "content"}
        expected = (producer_topic, event)

        kafka_input = ConfluentKafkaInput(
            ["bootstrap1", "bootstrap2"], "consumer_topic", "consumer_group", True
        )
        kafka_output = ConfluentKafkaOutputForTest(
            ["bootstrap1", "bootstrap2"], producer_topic, "producer_error_topic"
        )
        kafka_output.connect_input(kafka_input)
        kafka_output.store(event)

        assert len(kafka_output._producer.produced) == 1
        assert kafka_output._producer.produced[0] == expected

    def test_store_custom_sends_event_to_expected_topic(self):
        custom_topic = "custom_topic"
        event = {"field": "content"}
        expected = (custom_topic, event)

        kafka_input = ConfluentKafkaInput(
            ["bootstrap1", "bootstrap2"], "consumer_topic", "consumer_group", True
        )
        kafka_output = ConfluentKafkaOutputForTest(
            ["bootstrap1", "bootstrap2"], "default_topic", "producer_error_topic"
        )
        kafka_output.connect_input(kafka_input)
        kafka_output.store_custom(event, custom_topic)

        assert len(kafka_output._producer.produced) == 1
        assert kafka_output._producer.produced[0] == expected

    def test_store_failed(self):
        producer_error_topic = "producer_error_topic"
        event_received = {"field": "received"}
        event = {"field": "content"}
        error_message = "error message"

        expected = (
            producer_error_topic,
            {
                "error": error_message,
                "original": event_received,
                "processed": event,
                "timestamp": str(datetime.now()),
            },
        )

        kafka_input = ConfluentKafkaInput(
            ["bootstrap1", "bootstrap2"], "consumer_topic", "consumer_group", True
        )
        kafka_output = ConfluentKafkaOutputForTest(
            ["bootstrap1", "bootstrap2"], "producer_topic", producer_error_topic
        )
        kafka_output.connect_input(kafka_input)
        kafka_output.store_failed(error_message, event_received, event)

        assert len(kafka_output._producer.produced) == 1

        error_topic = kafka_output._producer.produced[0]

        # timestamp is compared to be approximately the same,
        # since it is variable and then removed to compare the rest
        date_format = "%Y-%m-%d %H:%M:%S.%f"
        error_time = datetime.timestamp(datetime.strptime(error_topic[1]["timestamp"], date_format))
        expected_time = datetime.timestamp(datetime.strptime(expected[1]["timestamp"], date_format))
        assert isclose(error_time, expected_time)
        del error_topic[1]["timestamp"]
        del expected[1]["timestamp"]

        assert error_topic == expected

    def test_get_next_returns_none_if_no_records(self):
        kafka_input = ConfluentKafkaInput(
            ["bootstrap1", "bootstrap2"], "consumer_topic", "consumer_group", True
        )

        kafka_input._consumer = ConsumerNoRecordMock()

        assert kafka_input.get_next(1) is None

    def test_get_next_raises_critical_input_exception_for_invalid_confluent_kafka_record(self):
        kafka_input = ConfluentKafkaInput(
            ["bootstrap1", "bootstrap2"], "consumer_topic", "consumer_group", True
        )

        kafka_input._consumer = ConsumerRecordWithKafkaErrorMock()

        with pytest.raises(
            CriticalInputError,
            match=r"A confluent-kafka record contains an error code: "
            r"\(An arbitrary confluent-kafka error\)",
        ):
            kafka_input.get_next(1)

    def test_create_confluent_settings_contains_expected_values2(self):
        with pytest.raises(
            CriticalOutputError,
            match=r"Error storing output document\: \(TypeError: Object of type "
            r"\'?NotJsonSerializableMock\'? is not JSON serializable\)",
        ):
            self.kafka_output.store(
                {"invalid_json": NotJsonSerializableMock(), "something_valid": "im_valid!"}
            )

    def test_get_next_with_hmac_of_raw_message(self):
        config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
        config["consumer"]["hmac"] = {
            "target": "<RAW_MSG>",
            "key": "hmac-test-key",
            "output_field": "Hmac",
        }

        kafka = ConfluentKafkaInputFactory.create_from_configuration(config)

        test_event = {"message": "with_content"}
        expected_event = {
            "message": "with_content",
            "Hmac": {
                "compressed_base64": "eJyrVspNLS5OTE9VslIqzyzJiE/OzytJzStRqgUAgKkJtg==",
                "hmac": "dfe78753da634d7b76760488dbb2cf7bfe1b0e4e794930c36e98a984b6b6be63",
            },
        }

        kafka._consumer = ConsumerJsonMock(test_event)

        kafka_next_msg = kafka.get_next(1)

        assert kafka_next_msg == expected_event, "Output event with hmac is not as expected"

        decoded_message = decode_b64_and_decompress(kafka_next_msg["Hmac"]["compressed_base64"])
        assert test_event == json.loads(
            decoded_message.decode("utf-8")
        ), "The hmac base massage was not correctly encoded and compressed. "

    def test_get_next_with_hmac_of_subfield(self):
        config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
        config["consumer"]["hmac"] = {
            "target": "message.with_subfield",
            "key": "hmac-test-key",
            "output_field": "Hmac",
        }

        kafka = ConfluentKafkaInputFactory.create_from_configuration(config)

        test_event = {"message": {"with_subfield": "content"}}
        expected_event = {
            "message": {"with_subfield": "content"},
            "Hmac": {
                "compressed_base64": "eJxLzs8rSc0rAQALywL8",
                "hmac": "e01e02a09cb270eebf7ae846b96d7306681038bd279f85d44c77019e0c4f6316",
            },
        }

        kafka._consumer = ConsumerJsonMock(test_event)

        kafka_next_msg = kafka.get_next(1)
        assert kafka_next_msg == expected_event

        decoded_message = decode_b64_and_decompress(kafka_next_msg["Hmac"]["compressed_base64"])
        assert test_event["message"]["with_subfield"] == decoded_message.decode(
            "utf-8"
        ), "The hmac base massage was not correctly encoded and compressed. "

    def test_get_next_with_hmac_of_non_existing_subfield(self):
        config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
        config["consumer"]["hmac"] = {
            "target": "non_existing_field",
            "key": "hmac-test-key",
            "output_field": "Hmac",
        }

        kafka_input = ConfluentKafkaInputFactory.create_from_configuration(config)
        kafka_output = ConfluentKafkaOutputFactory.create_from_configuration(config)
        kafka_input.connect_output(kafka_output)

        test_event = {"message": {"with_subfield": "content"}}
        expected_output_event = {
            "message": {"with_subfield": "content"},
            "Hmac": {
                "hmac": "error",
                "compressed_base64": "eJyzSa0oSE0uSU1RyMhNTFYoSSxKTy1RSMtMzUlRUM/Lz4tPrcgsLsnMS48Hi"
                "6kr5OUDpfNL81LsAJILFeQ=",
            },
        }
        kafka_input._consumer = ConsumerJsonMock(test_event)
        kafka_output._producer = ProducerMock()

        kafka_next_msg = kafka_input.get_next(1)
        assert kafka_next_msg == expected_output_event

        decoded_message = decode_b64_and_decompress(
            kafka_next_msg["Hmac"]["compressed_base64"]
        ).decode()
        assert decoded_message == "<expected hmac target field 'non_existing_field' not found>"

        assert len(kafka_output._producer.produced) == 1
        assert (
            kafka_output._producer.produced[0][1]["error"]
            == "Couldn't find the hmac target field 'non_existing_field'"
        )
        assert kafka_output._producer.produced[0][1]["original"] == test_event

    def test_get_next_with_hmac_result_in_dotted_subfield(self):
        config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
        config["consumer"]["hmac"] = {
            "target": "<RAW_MSG>",
            "key": "hmac-test-key",
            "output_field": "Hmac.dotted.subfield",
        }

        kafka = ConfluentKafkaInputFactory.create_from_configuration(config)

        test_event = {"message": "with_content"}
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

        kafka._consumer = ConsumerJsonMock(test_event)

        kafka_next_msg = kafka.get_next(1)
        assert kafka_next_msg == expected_event

        decoded_message = decode_b64_and_decompress(
            kafka_next_msg["Hmac"]["dotted"]["subfield"]["compressed_base64"]
        )
        assert test_event == json.loads(
            decoded_message.decode("utf-8")
        ), "The hmac base massage was not correctly encoded and compressed. "

    def test_get_next_with_hmac_result_in_already_existing_subfield(self):
        config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
        config["consumer"]["hmac"] = {
            "target": "<RAW_MSG>",
            "key": "hmac-test-key",
            "output_field": "message",
        }

        kafka_input = ConfluentKafkaInputFactory.create_from_configuration(config)
        kafka_output = ConfluentKafkaOutputFactory.create_from_configuration(config)
        kafka_input.connect_output(kafka_output)

        test_event = {"message": {"with_subfield": "content"}}
        kafka_input._consumer = ConsumerJsonMock(test_event)
        kafka_output._producer = ProducerMock()

        _ = kafka_input.get_next(1)

        assert len(kafka_output._producer.produced) == 1
        assert (
            kafka_output._producer.produced[0][1]["error"]
            == "Couldn't add the hmac to the input event as the desired output field 'message' "
            "already exist."
        )
        assert kafka_output._producer.produced[0][1]["original"] == test_event

    def test_get_next_with_wrong_or_missing_hmac_config(self):
        for key in ["target", "key", "output_field"]:
            # set default config
            config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
            config["consumer"]["hmac"] = {
                "target": "<RAW_MSG>",
                "key": "hmac-test-key",
                "output_field": "Hmac",
            }

            # drop option to test for missing option error message
            del config["consumer"]["hmac"][key]
            with pytest.raises(
                InvalidConfigurationError, match=rf"Hmac option\(s\) missing: {{'{key}'}}"
            ):
                _ = ConfluentKafkaInputFactory.create_from_configuration(config)

        # set default config
        config = deepcopy(TestConfluentKafkaFactory.valid_configuration)

        # add additional unknown option and test for error message
        config["consumer"]["hmac"] = {"unknown": "option"}
        with pytest.raises(
            InvalidConfigurationError, match=r"Confluent Kafka Input: Unknown Option: unknown"
        ):
            _ = ConfluentKafkaInputFactory.create_from_configuration(config)

    def test_get_next_with_broken_hmac_config(self):
        for key in ["target", "key", "output_field"]:
            # set default config
            config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
            config["consumer"]["hmac"] = {
                "target": "<RAW_MSG>",
                "key": "hmac-test-key",
                "output_field": "Hmac",
            }

            # empty one option and test for error message
            config["consumer"]["hmac"][key] = ""
            with pytest.raises(
                InvalidConfigurationError, match=rf"Hmac option '{key}' is empty: ''"
            ):
                _ = ConfluentKafkaInputFactory.create_from_configuration(config)

    def test_get_next_without_hmac(self):
        config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
        kafka = ConfluentKafkaInputFactory.create_from_configuration(config)

        # configuration is not set
        assert kafka._config["consumer"]["hmac"]["target"] == ""
        assert kafka._config["consumer"]["hmac"]["key"] == ""
        assert kafka._config["consumer"]["hmac"]["output_field"] == ""

        test_event = {"message": "with_content"}
        expected_event = {"message": "with_content"}

        kafka._consumer = ConsumerJsonMock(test_event)

        # output message is the same as the input message
        kafka_next_msg = kafka.get_next(1)
        assert kafka_next_msg == expected_event

    def test_update_default_configuration_overwrites_default_options_in_nested_field(self):
        default_config = {
            "option": {"with": {"multiple": "layers", "foo": "bar"}},
            "another": "option",
        }
        user_config = {"option": {"with": {"foo": "bi"}}}
        expected_config = {
            "option": {"with": {"multiple": "layers", "foo": "bi"}},
            "another": "option",
        }
        config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
        kafka = ConfluentKafkaInputFactory.create_from_configuration(config)
        new_config = kafka._set_connector_type_options(user_config, default_config)
        assert new_config == expected_config

    def test_update_default_configuration_overwrites_default_options_in_first_level(self):
        default_config = {
            "option": {"with": {"multiple": "layers", "foo": "bar"}},
            "another": "option",
        }
        user_config = {"another": "test option"}
        expected_config = {
            "option": {"with": {"multiple": "layers", "foo": "bar"}},
            "another": "test option",
        }
        config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
        kafka = ConfluentKafkaInputFactory.create_from_configuration(config)
        new_config = kafka._set_connector_type_options(user_config, default_config)
        assert new_config == expected_config

    def test_update_default_configuration_raises_error_on_unknown_option_in_first_level(self):
        default_config = {
            "option": {"with": {"multiple": "layers", "foo": "bar"}},
            "another": "option",
        }
        user_config = {"unknown": "option"}
        config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
        kafka = ConfluentKafkaInputFactory.create_from_configuration(config)
        with pytest.raises(UnknownOptionError, match="Unknown Option: unknown"):
            _ = kafka._set_connector_type_options(user_config, default_config)

    def test_update_default_configuration_does_nothing_on_empty_user_configs(self):
        default_config = {
            "option": {"with": {"multiple": "layers", "foo": "bar"}},
            "another": "option",
        }
        user_config = {}
        config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
        kafka = ConfluentKafkaInputFactory.create_from_configuration(config)
        new_config = kafka._set_connector_type_options(user_config, default_config)
        assert new_config == default_config

    def test_update_default_configuration_raises_error_on_wrong_type(self):
        default_config = {
            "option": 12.2,
            "another": "option",
        }
        user_config = {"option": "string and not float"}
        config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
        kafka = ConfluentKafkaInputFactory.create_from_configuration(config)
        with pytest.raises(
            UnknownOptionError,
            match="Wrong Option type for 'string and not float'. "
            "Got <class 'str'>, expected <class 'float'>.",
        ):
            _ = kafka._set_connector_type_options(user_config, default_config)

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_shut_down_calls_consumer_close(self, _):
        config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
        kafka = ConfluentKafkaInputFactory.create_from_configuration(config)
        kafka._create_consumer()
        kafka_consumer = kafka._consumer
        kafka.shut_down()
        kafka_consumer.close.assert_called()

    @mock.patch("logprep.connector.confluent_kafka.input.Consumer")
    def test_shut_down_sets_consumer_to_none(self, _):
        config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
        kafka = ConfluentKafkaInputFactory.create_from_configuration(config)
        kafka._create_consumer()
        kafka.shut_down()
        assert kafka._consumer is None

    @mock.patch("logprep.connector.confluent_kafka.confluent_kafka_output.Producer")
    def test_store_custom_calls_producer_flush_on_buffererror(self, mock_producer):
        config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
        kafka = ConfluentKafkaOutputFactory.create_from_configuration(config)
        kafka._producer = mock_producer
        kafka._producer.produce = mock.MagicMock()
        kafka._producer.produce.side_effect = BufferError
        kafka._producer.flush = mock.MagicMock()
        kafka.store_custom({"message": "does not matter"}, "doesnotcare")
        kafka._producer.flush.assert_called()

    @mock.patch("logprep.connector.confluent_kafka.confluent_kafka_output.Producer")
    def test_store_failed_calls_producer_flush_on_buffererror(self, mock_producer):
        config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
        kafka = ConfluentKafkaOutputFactory.create_from_configuration(config)
        kafka._producer = mock_producer
        kafka._producer.produce = mock.MagicMock()
        kafka._producer.produce.side_effect = BufferError
        kafka._producer.flush = mock.MagicMock()
        kafka.store_failed(
            "doesnotcare", {"message": "does not matter"}, {"message": "does not matter"}
        )
        kafka._producer.flush.assert_called()

    @mock.patch("logprep.connector.confluent_kafka.confluent_kafka_output.Producer")
    def test_shut_down_calls_producer_flush(self, mock_producer):
        config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
        kafka = ConfluentKafkaOutputFactory.create_from_configuration(config)
        kafka._producer = mock_producer
        kafka.shut_down()
        mock_producer.flush.assert_called()

    @mock.patch("logprep.connector.confluent_kafka.confluent_kafka_output.Producer")
    def test_shut_down_sets_producer_to_none(self, mock_producer):
        config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
        kafka = ConfluentKafkaOutputFactory.create_from_configuration(config)
        kafka._producer = mock_producer
        kafka.shut_down()
        assert kafka._producer is None
