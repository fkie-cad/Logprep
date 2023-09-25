# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=subprocess-run-check
# pylint: disable=protected-access
import logging
import os
import re
import subprocess
import time
import uuid
from unittest import mock

import pytest
from confluent_kafka import Consumer, TopicPartition
from confluent_kafka.admin import AdminClient, NewTopic

from logprep.factory import Factory

in_ci = os.environ.get("GITHUB_ACTIONS") == "true"

kafka_config = {"bootstrap.servers": "localhost:9092"}


def setup_module():
    if not in_ci:
        subprocess.run(
            ["docker-compose", "-f", "quickstart/docker-compose.yml", "up", "-d", "kafka"]
        )


@pytest.mark.skipif(in_ci, reason="requires kafka")
class TestKafkaConnection:
    def get_topic_partition_size(self, topic_partition: TopicPartition) -> int:
        time.sleep(1)
        consumer = Consumer(kafka_config | {"group.id": str(uuid.uuid4())})
        lowwater, highwater = consumer.get_watermark_offsets(topic_partition)
        consumer.close()
        return highwater - lowwater

    def wait_for_topic_creation(self):
        while (
            self.topic_name not in self.admin.list_topics().topics
            and self.error_topic_name not in self.admin.list_topics().topics
        ):
            time.sleep(2)

    def setup_method(self):
        self.admin = AdminClient(kafka_config)
        self.topic_name = str(uuid.uuid4())
        self.topic = NewTopic(self.topic_name, num_partitions=1, replication_factor=1)
        self.topic_partition = TopicPartition(self.topic_name, 0)
        self.error_topic_name = str(uuid.uuid4())
        self.error_topic = NewTopic(self.error_topic_name, num_partitions=1, replication_factor=1)
        self.error_topic_partition = TopicPartition(self.topic_name, 0)
        self.admin.create_topics([self.topic, self.error_topic])
        self.wait_for_topic_creation()

        ouput_config = {
            "type": "confluentkafka_output",
            "topic": self.topic_name,
            "error_topic": self.error_topic_name,
            "flush_timeout": 1,
            "maximum_backlog": 10,
            "kafka_config": {
                "bootstrap.servers": "localhost:9092",
            },
        }
        self.kafka_output = Factory.create(
            {"test output": ouput_config}, logger=logging.getLogger()
        )

        input_config = {
            "type": "confluentkafka_input",
            "topic": self.topic_name,
            "kafka_config": {
                "bootstrap.servers": "localhost:9092",
                "group.id": "test_consumergroup",
            },
        }
        self.kafka_input = Factory.create({"test input": input_config}, logger=logging.getLogger())

    def teardown_method(self):
        self.kafka_input.shut_down()
        self.kafka_output.shut_down()

    def test_input_returns_by_output_produced_message(self):
        expected_event = {"test": "test"}
        self.kafka_output.store(expected_event)
        assert self.get_topic_partition_size(self.topic_partition) == 1

        returned_event = self.kafka_input.get_next(5)[0]
        assert returned_event == expected_event

    def test_input_returns_by_output_produced_messages(self):
        expected_event = {"test": "test"}
        for index in range(10):
            self.kafka_output.store(expected_event | {"index": index})
        assert self.get_topic_partition_size(self.topic_partition) == 10

        for index in range(10):
            event = self.kafka_input.get_next(5)[0]
            assert event
            assert event.get("index") == index

    def test_librdkafka_logs_forwarded_to_logprep_logger(self):
        input_config = {
            "type": "confluentkafka_input",
            "topic": self.topic_name,
            "kafka_config": {
                "bootstrap.servers": "notexisting:9092",
                "group.id": "test_consumergroup",
            },
        }
        kafka_input = Factory.create({"librdkafkatest": input_config}, logger=mock.MagicMock())
        kafka_input._logger.log = mock.MagicMock()
        kafka_input.get_next(5)
        kafka_input._logger.log.assert_called()
        assert re.search(
            r"Failed to resolve 'notexisting:9092'", kafka_input._logger.log.mock_calls[0][1][4]
        )

    def test_debugging_consumer(self):
        input_config = {
            "type": "confluentkafka_input",
            "topic": self.topic_name,
            "kafka_config": {
                "bootstrap.servers": "localhost:9092",
                "group.id": "test_consumergroup",
                "debug": "consumer,cgrp,topic,fetch",
            },
        }
        logger = logging.getLogger()
        kafka_input = Factory.create({"librdkafkatest": input_config}, logger=logger)
        kafka_input.get_next(5)

    def test_reconnect_consumer_after_failure(self):
        expected_event = {"test": "test"}
        for index in range(10):
            self.kafka_output.store(expected_event | {"index": index})
        assert self.get_topic_partition_size(self.topic_partition) == 10

        for index in range(5):
            event = self.kafka_input.get_next(10)[0]
            assert event
            assert event.get("index") == index
        # simulate delivery by output_connector
        self.kafka_input.batch_finished_callback()
        # simulate pipeline restart
        self.kafka_input.shut_down()
        self.kafka_input.setup()

        for index in range(5, 10):
            event = self.kafka_input.get_next(10)[0]
            assert event
            assert event.get("index") == index, "should start after commited offsets"
