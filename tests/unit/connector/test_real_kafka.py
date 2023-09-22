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

    def setup_method(self):
        self.admin = AdminClient(kafka_config)
        self.topic_name = str(uuid.uuid4())
        self.topic = NewTopic(self.topic_name, num_partitions=1, replication_factor=1)
        self.topic_partition = TopicPartition(self.topic_name, 0)
        self.error_topic_name = str(uuid.uuid4())
        self.error_topic = NewTopic(self.error_topic_name, num_partitions=1, replication_factor=1)
        self.error_topic_partition = TopicPartition(self.topic_name, 0)
        self.admin.create_topics([self.topic, self.error_topic])
        while (
            self.topic_name not in self.admin.list_topics().topics
            and self.error_topic_name not in self.admin.list_topics().topics
        ):
            time.sleep(2)

    def test_simple(self):
        ouput_config = {
            "type": "confluentkafka_output",
            "bootstrapservers": ["localhost:9092"],
            "topic": self.topic_name,
            "error_topic": self.error_topic_name,
            "flush_timeout": 0.1,
            "maximum_backlog": 1,
        }
        kafka_output = Factory.create({"test connector": ouput_config}, logger=logging.getLogger())
        kafka_output.store({"test": "test"})

        assert self.get_topic_partition_size(self.topic_partition) == 1
