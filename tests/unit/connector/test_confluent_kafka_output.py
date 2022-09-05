# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init
# pylint: disable=no-self-use

import json
from unittest import mock
from logprep.connector.connector_factory import ConnectorFactory
from tests.unit.connector.base import BaseConnectorTestCase


class TestConfluentKafkaOutput(BaseConnectorTestCase):
    CONFIG = {
        "type": "confluentkafka_output",
        "bootstrapservers": ["testserver:9092"],
        "topic": "test_input_raw",
        "group": "test_producergroup",
        "auto_commit": False,
        "session_timeout": 654321,
        "enable_auto_offset_store": True,
        "offset_reset_policy": "latest",
        "ssl": {
            "cafile": "test_cafile",
            "certfile": "test_certfile",
            "keyfile": "test_keyfile",
            "password": "test_password",
        },
    }

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

    @mock.patch("logprep.connector.confluent_kafka.output.Producer", return_value="The Producer")
    def test_producer_property_instanciates_kafka_producer(self, _):
        kafka_output = ConnectorFactory.create({"test connector": self.CONFIG}, logger=self.logger)
        assert kafka_output._producer == "The Producer"

    @mock.patch("logprep.connector.confluent_kafka.output.Producer")
    def test_store_sends_event_to_expected_topic(self, _):
        kafka_producer = self.object._producer
        event = {"field": "content"}
        event_raw = json.dumps(event, separators=(",", ":")).encode("utf-8")
        expected_call = mock.call(self.CONFIG.get("topic"), value=event_raw)
        self.object.store(event)
        kafka_producer.produce.assert_called()
        assert expected_call in kafka_producer.produce.mock_calls

    # def test_store_custom_sends_event_to_expected_topic(self):
    #     custom_topic = "custom_topic"
    #     event = {"field": "content"}
    #     expected = (custom_topic, event)

    #     kafka_input = ConfluentKafkaInput(
    #         ["bootstrap1", "bootstrap2"], "consumer_topic", "consumer_group", True
    #     )
    #     kafka_output = ConfluentKafkaOutputForTest(
    #         ["bootstrap1", "bootstrap2"], "default_topic", "producer_error_topic"
    #     )
    #     kafka_output.connect_input(kafka_input)
    #     kafka_output.store_custom(event, custom_topic)

    #     assert len(kafka_output._producer.produced) == 1
    #     assert kafka_output._producer.produced[0] == expected

    # def test_store_failed(self):
    #     producer_error_topic = "producer_error_topic"
    #     event_received = {"field": "received"}
    #     event = {"field": "content"}
    #     error_message = "error message"

    #     expected = (
    #         producer_error_topic,
    #         {
    #             "error": error_message,
    #             "original": event_received,
    #             "processed": event,
    #             "timestamp": str(datetime.now()),
    #         },
    #     )

    #     kafka_input = ConfluentKafkaInput(
    #         ["bootstrap1", "bootstrap2"], "consumer_topic", "consumer_group", True
    #     )
    #     kafka_output = ConfluentKafkaOutputForTest(
    #         ["bootstrap1", "bootstrap2"], "producer_topic", producer_error_topic
    #     )
    #     kafka_output.connect_input(kafka_input)
    #     kafka_output.store_failed(error_message, event_received, event)

    #     assert len(kafka_output._producer.produced) == 1

    #     error_topic = kafka_output._producer.produced[0]

    #     # timestamp is compared to be approximately the same,
    #     # since it is variable and then removed to compare the rest
    #     date_format = "%Y-%m-%d %H:%M:%S.%f"
    #     error_time = datetime.timestamp(datetime.strptime(error_topic[1]["timestamp"], date_format))
    #     expected_time = datetime.timestamp(datetime.strptime(expected[1]["timestamp"], date_format))
    #     assert isclose(error_time, expected_time)
    #     del error_topic[1]["timestamp"]
    #     del expected[1]["timestamp"]

    #     assert error_topic == expected

    # def test_create_confluent_settings_contains_expected_values2(self):
    #     with pytest.raises(
    #         CriticalOutputError,
    #         match=r"Error storing output document\: \(TypeError: Object of type "
    #         r"\'?NotJsonSerializableMock\'? is not JSON serializable\)",
    #     ):
    #         self.kafka_output.store(
    #             {"invalid_json": NotJsonSerializableMock(), "something_valid": "im_valid!"}
    #         )

    # @mock.patch("logprep.connector.confluent_kafka.output.Producer")
    # def test_store_custom_calls_producer_flush_on_buffererror(self, mock_producer):
    #     config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
    #     kafka = ConfluentKafkaOutputFactory.create_from_configuration(config)
    #     kafka._producer = mock_producer
    #     kafka._producer.produce = mock.MagicMock()
    #     kafka._producer.produce.side_effect = BufferError
    #     kafka._producer.flush = mock.MagicMock()
    #     kafka.store_custom({"message": "does not matter"}, "doesnotcare")
    #     kafka._producer.flush.assert_called()

    # @mock.patch("logprep.connector.confluent_kafka.output.Producer")
    # def test_store_failed_calls_producer_flush_on_buffererror(self, mock_producer):
    #     config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
    #     kafka = ConfluentKafkaOutputFactory.create_from_configuration(config)
    #     kafka._producer = mock_producer
    #     kafka._producer.produce = mock.MagicMock()
    #     kafka._producer.produce.side_effect = BufferError
    #     kafka._producer.flush = mock.MagicMock()
    #     kafka.store_failed(
    #         "doesnotcare", {"message": "does not matter"}, {"message": "does not matter"}
    #     )
    #     kafka._producer.flush.assert_called()

    # @mock.patch("logprep.connector.confluent_kafka.output.Producer")
    # def test_shut_down_calls_producer_flush(self, mock_producer):
    #     config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
    #     kafka = ConfluentKafkaOutputFactory.create_from_configuration(config)
    #     kafka._producer = mock_producer
    #     kafka.shut_down()
    #     mock_producer.flush.assert_called()

    # @mock.patch("logprep.connector.confluent_kafka.output.Producer")
    # def test_shut_down_sets_producer_to_none(self, mock_producer):
    #     config = deepcopy(TestConfluentKafkaFactory.valid_configuration)
    #     kafka = ConfluentKafkaOutputFactory.create_from_configuration(config)
    #     kafka._producer = mock_producer
    #     kafka.shut_down()
    #     assert kafka._producer is None
