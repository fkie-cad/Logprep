"""
KafkaConfluentGeneratorOutput
==========

The logprep confluent kafka generator inheriting from the confluent kafka connector output.
Sends the documents written by the generator to a topic endpoint.
"""

import json
import logging
import re

from attr import evolve
from confluent_kafka import KafkaException  # type: ignore

from logprep.abc.output import Output
from logprep.connector.confluent_kafka.output import ConfluentKafkaOutput

logger = logging.getLogger("KafkaOutput")


class ConfluentKafkaGeneratorOutput(ConfluentKafkaOutput):
    """Output class inheriting from the connector output class"""

    _config: Output.Config

    def __init__(self, name, configuration) -> None:
        super().__init__(name, configuration)
        self.target: None | str = None

    @property
    def statistics(self) -> str:
        """Return the statistics of this connector as a formatted string."""
        stats: dict = {}
        metrics = filter(lambda x: not x.name.startswith("_"), self.metrics.__attrs_attrs__)
        if self._config.send_timeout > 0:
            self.stats_event.clear()
            self._producer.flush(self._config.send_timeout)
            self._producer.poll(self._config.send_timeout)
            if not self.stats_event.wait(timeout=self._config.send_timeout):
                logger.warning(
                    "Warning: No stats callback triggered within %s!", self._config.send_timeout
                )
            else:
                logger.info("Stats received, continuing...")

        for metric in metrics:
            samples = filter(
                lambda x: x.name.endswith("_total")
                and "number_of_warnings" not in x.name  # blocklisted metric
                and "number_of_errors" not in x.name,  # blocklisted metric
                getattr(self.metrics, metric.name).tracker.collect()[0].samples,
            )
            for sample in samples:
                key = (
                    getattr(self.metrics, metric.name).description
                    if metric.name != "status_codes"
                    else sample.labels.get("description")
                )
                stats[key] = int(sample.value)
        stats["Is the producer healthy"] = self.health()
        return json.dumps(stats, sort_keys=True, indent=4, separators=(",", ": "))

    def validate(self, topics) -> None:
        """Validates the given Kafka topics and raises an error for invalid ones."""
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
