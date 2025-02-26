"""
This module contains the ControllerFactory class, which is responsible for creating
instances of different types of controllers based on the specified target.
"""

import json
import logging

from logprep.connector.confluent_kafka.output import ConfluentKafkaOutput
from logprep.connector.http.output import HttpOutput
from logprep.factory import Factory
from logprep.generator.controller import Controller
from logprep.generator.http.input import Input
from logprep.util.logging import LogprepMPQueueListener, logqueue

logger = logging.getLogger("Generator")


class ControllerFactory:
    """Factory to create controllers."""

    @classmethod
    def create(cls, target: str, **kwargs) -> Controller | None:
        """Factory method to create a controller"""
        if target not in ["http", "kafka"]:
            raise ValueError(f"Controller type {target} not supported")
        loghandler = cls.get_loghandler(kwargs.get("loglevel", "INFO"))
        input_connector = Input(kwargs)
        output_connector = None
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
                output_connector = Factory.create(output_config)
                if not isinstance(output_connector, HttpOutput):
                    raise ValueError("Output is not a valid output type")
                return Controller(output_connector, input_connector, loghandler, **kwargs)
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
                output_connector = Factory.create(output_config)
                if not isinstance(output_connector, ConfluentKafkaOutput):
                    raise ValueError("Output is not a valid output type")
                return Controller(output_connector, input_connector, loghandler, **kwargs)
            case _:
                return None

    @staticmethod
    def get_loghandler(level: str | int) -> LogprepMPQueueListener:
        """Returns a log handler for the controller"""
        console_handler = None
        if level:
            logger.root.setLevel(level)
        console_logger = logging.getLogger("console")
        if console_logger.handlers:
            console_handler = console_logger.handlers.pop()  # last handler is console
        if console_handler is None:
            raise ValueError("No console handler found")
        return LogprepMPQueueListener(logqueue, console_handler)
