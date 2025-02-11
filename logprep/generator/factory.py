"""
This module contains the ControllerFactory class, which is responsible for creating
instances of different types of controllers based on the specified target.
"""

import json
import logging

from logprep.abc.controller import Controller
from logprep.abc.output import Output
from logprep.factory import Factory
from logprep.generator.confluent_kafka.controller import KafkaController
from logprep.generator.http.controller import HTTPController
from logprep.util.logging import LogprepMPQueueListener, logqueue

logger = logging.getLogger("Generator")


class ControllerFactory:
    """Factory to create controllers."""

    @classmethod
    def create(cls, target: str, **kwargs) -> Controller | None:
        """Factory method to create a controller"""
        if target not in ["http", "kafka"]:
            raise ValueError(f"Controller type {target} not supported")
        loghandler = cls.get_loghandler(kwargs.get("level", "INFO"))
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
                if not isinstance(output, Output):
                    raise ValueError("Output is not a valid output type")
                return HTTPController(output, loghandler, **kwargs)
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
                if not isinstance(output, Output):
                    raise ValueError("Output is not a valid output type")
                return KafkaController(output, loghandler, **kwargs)
            case _:
                return None

    def get_loghandler(self, level: str) -> LogprepMPQueueListener:
        """Returns a log handler for the controller"""
        console_handler = None
        if level:
            logger.setLevel(level)
        if logger.handlers:
            console_handler = logger.handlers.pop()  # last handler is console
        if console_handler is None:
            raise ValueError("No console handler found")
        return LogprepMPQueueListener(logqueue, console_handler)
