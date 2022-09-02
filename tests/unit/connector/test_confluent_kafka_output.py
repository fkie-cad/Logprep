# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init
# pylint: disable=no-self-use

from tests.unit.connector.base import BaseConnectorTestCase


class TestConfluentKafkaOutput(BaseConnectorTestCase):
    CONFIG = {
        "type": "confluentkafka_input",
        "bootstrapservers": ["testserver:9092"],
        "topic": "test_input_raw",
        "group": "test_consumergroup",
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

    # def test_store_sends_event_to_expected_topic(self):
    #     producer_topic = "producer_topic"
    #     event = {"field": "content"}
    #     expected = (producer_topic, event)
    #
    #     kafka_input = ConfluentKafkaInput(
    #         ["bootstrap1", "bootstrap2"], "consumer_topic", "consumer_group", True
    #     )
    #     kafka_output = ConfluentKafkaOutputForTest(
    #         ["bootstrap1", "bootstrap2"], producer_topic, "producer_error_topic"
    #     )
    #     kafka_output.connect_input(kafka_input)
    #     kafka_output.store(event)
    #
    #     assert len(kafka_output._producer.produced) == 1
    #     assert kafka_output._producer.produced[0] == expected

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
