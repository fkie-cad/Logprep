# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access

import json
from unittest.mock import MagicMock, patch

import pytest

from logprep.connector.confluent_kafka.output import ConfluentKafkaOutput
from logprep.factory import Factory


class TestConfluentKafkaGeneratorOutput:

    def setup_method(self):

        default_config = '{"bootstrap.servers": "localhost:9092"}'
        kafka_config = json.loads(default_config)
        output_config = {
            "generator_output": {
                "type": "confluentkafka_generator_output",
                "topic": kafka_config.get("topic", "producer"),
                "kafka_config": kafka_config,
                "send_timeout": 0,
            },
        }

        self.output = Factory.create(output_config)

        self.output.metrics = MagicMock()
        self.output.metrics.processed_batches = 0
        self.output.store_custom = MagicMock()

    def test_store_calls_store_custom(self):
        self.output.store("test_topic,test_payload")
        self.output.store_custom.assert_called_once_with("test_payload", "test_topic")

    def test_store_updates_topic(self):
        assert self.output._config.topic == "producer"
        self.output.store("test_topic,test_payload")
        assert self.output._config.topic == "test_topic"

    def test_store_counting_batches(self):
        self.output.store("test_topic,test_payload")
        assert self.output.metrics.processed_batches == 1
        self.output.store("test_topic,test_payload")
        assert self.output.metrics.processed_batches == 2

    def test_store_handles_empty_payload(self):
        self.output.store("test_topic,")
        self.output.store_custom.assert_called_once_with("", "test_topic")

    def test_store_handles_missing_comma(self):
        self.output.store("test_topic_only")
        self.output.store_custom.assert_called_once_with("", "test_topic_only")

    def test_store_calles_super_store(self):
        with patch.object(ConfluentKafkaOutput, "store", MagicMock()) as mock_store:
            self.output.store({"test_field": "test_value"})
            mock_store.assert_called_once_with({"test_field": "test_value"})

    @pytest.mark.parametrize(
        "topic, expected",
        [
            ("valid_topic", True),
            ("valid-topic-123", True),
            ("valid.topic_123", True),
            ("", False),
            ("..", False),
            (".", False),
            (
                "this_is_a_very_long_topic_name_that_exceeds_the_maximum_length_limit_of_249_characters_"
                + "a" * 200,
                False,
            ),
            ("invalid topic", False),
            ("invalid#topic", False),
            ("invalid@topic", False),
        ],
    )
    def test_is_valid_kafka_topic(self, topic, expected):
        assert self.output._is_valid_kafka_topic(topic) == expected

    @pytest.mark.parametrize(
        "targets, should_raise, expected_faulty",
        [
            (["valid", "another_valid"], False, []),
            (["/invalid", "valid"], True, ["/invalid"]),
            (["/invalid", "invalid#"], True, ["/invalid", "invalid#"]),
        ],
    )
    def test_validate(self, targets, should_raise, expected_faulty):
        if should_raise:
            with pytest.raises(ValueError) as exc_info:
                self.output.validate(targets)
            assert str(exc_info.value) == f"Invalid Kafka topic names: {expected_faulty}"
        else:
            self.output.validate(targets)
