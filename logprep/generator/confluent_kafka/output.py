"""
KafkaConfluentGeneratorOutput
==========

The logprep confluent kafka generator inheriting from the confluent kafka connector output.
Sends the documents writen by the generator to a topic endpoint.
"""

import re
from venv import logger

from attr import evolve
from confluent_kafka import KafkaException
from isort import Config

from logprep.connector.confluent_kafka.output import ConfluentKafkaOutput


class ConfluentKafkaGeneratorOutput(ConfluentKafkaOutput):
    """Output class inheriting from the connector output class"""

    _config: Config

    def __init__(self, name, configuration) -> None:
        super().__init__(name, configuration)
        self.target: None | str = None

    def validate(self, topics) -> None:
        """validates the given topics"""
        faulty_topics = [topic for topic in topics if not self._is_valid_kafka_topic(topic)]

        if faulty_topics:
            raise ValueError(f"Invalid Kafka topic names: {faulty_topics}")

    def store(self, document: dict | str) -> None:
        if isinstance(document, str):

            self.metrics.processed_batches += 1
            topic, _, payload = document.partition(",")
            self._config = evolve(self._config, topic=topic)
            self._producer.produce(topic, value=self._encoder.encode(document))
            self.target = topic
            documents = list(payload.split(";"))
            for item in documents:
                self.store_custom(item, topic)

        else:
            super().store(document)

    def health(self) -> bool:
        try:
            metadata = self._admin.list_topics(timeout=self._config.health_timeout)
            if not self.target in metadata.topics:
                logger.error("Topic  '%s' does not exit", self.target)
                return False
        except KafkaException as error:
            logger.error("Health check failed: %s", error)
            self.metrics.number_of_errors += 1
            return False
        return True

    def _is_valid_kafka_topic(self, topic: str) -> bool:
        """Checks if the given Kafka topic name is valid according to Kafka's rules."""
        if not isinstance(topic, str) or not topic:
            return False
        if len(topic) > 249:
            return False
        if topic in {".", ".."}:
            return False
        if not re.match(r"^[a-zA-Z0-9._-]+$", topic):
            return False
        return True
