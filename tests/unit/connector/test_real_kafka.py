# pylint: disable=missing-docstring
import os
import subprocess
import time

import pytest

from confluent_kafka.admin import AdminClient, NewTopic, NewPartitions


in_ci = os.environ.get("GITHUB_ACTIONS") == "true"


def setup_module():
    subprocess.run(["docker-compose", "-f", "quickstart/docker-compose.yml", "up", "-d"])


def teardown_module():
    subprocess.run(["docker-compose", "-f", "quickstart/docker-compose.yml", "down", "-v"])


@pytest.mark.skipif(in_ci, reason="requires kafka")
class TestKafkaConnection:
    def setup_method(self):
        kafka_admin = AdminClient({"bootstrap.servers": "localhost:9092"})
        response = kafka_admin.list_topics()
        while "consumer" not in response.topics:
            time.sleep(2)
            response = kafka_admin.list_topics()

    def test_simple(self):
        assert False
