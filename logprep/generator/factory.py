"""
This module contains the ControllerFactory class, which is responsible for creating
instances of different types of controllers based on the specified target.
"""

import json

from logprep.abc.controller import Controller
from logprep.factory import Factory
from logprep.generator.confluent_kafka.controller import KafkaController
from logprep.generator.http.controller import HTTPController


class ControllerFactory:
    """Factory to create controllers."""

    @classmethod
    def create(cls, target: str, **kwargs) -> Controller | None:
        """Factory method to create a controller"""
        if target not in ["http", "kafka"]:
            raise ValueError(f"Controller type {target} not supported")
        match target:
            case "http":
                output_config = {
                    "generator_output": {
                        "type": "http_output",
                        "user": kwargs.get("user"),
                        "password": kwargs.get("password"),
                        "target_url": kwargs.get("target_url"),
                        "timeout": kwargs.get("timeout", 2),
                    }
                }
                output = Factory.create(output_config)
                return HTTPController(output, **kwargs)
            case "kafka":
                default_config = '{"bootstrap.servers": "localhost:9092"}'
                kafka_config = json.loads(kwargs.get("kafka_config", default_config))
                output_config = {
                    "generator_output": {
                        "type": "confluentkafka_output",
                        "topic": "producer",
                        "kafka_config": kafka_config,
                    },
                }
                output = Factory.create(output_config)
                return KafkaController(output, **kwargs)
            case _:
                return None
