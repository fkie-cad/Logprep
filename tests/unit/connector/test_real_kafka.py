# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=subprocess-run-check
import logging
import os
import subprocess
import time
import uuid

import pytest
from confluent_kafka import Consumer, TopicPartition
from confluent_kafka.admin import AdminClient, NewTopic

from logprep.factory import Factory

in_ci = os.environ.get("GITHUB_ACTIONS") == "true"

kafka_config = {"bootstrap.servers": "localhost:9092"}


def setup_module():
    if not in_ci:
        subprocess.run(["docker-compose", "-f", "quickstart/docker-compose.yml", "up", "-d"])


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
            "bootstrapservers": ["localhost:9092"],
            "topic": self.topic_name,
            "error_topic": self.error_topic_name,
            "flush_timeout": 0.1,
            "maximum_backlog": 1,
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
                "enable.auto.commit": "false",
                "session.timeout.ms": "6000",
                "enable.auto.offset.store": "true",
                "auto.offset.reset": "smallest",
            },
        }
        self.kafka_input = Factory.create({"test input": input_config}, logger=logging.getLogger())

    def test_input_returns_by_output_produced_message(self):
        expected_event = {"test": "test"}
        self.kafka_output.store(expected_event)

        assert self.get_topic_partition_size(self.topic_partition) == 1

        returned_event = self.kafka_input.get_next(1)[0]
        assert returned_event == expected_event
