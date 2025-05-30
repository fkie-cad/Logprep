"""
ConfluentKafkaGeneratorOutput
=============================

The logprep ConfluentKafka generator inherits from the ConfluentKafka connector output.
Sends the documents written by the generator to a Kafka topic.
"""

import json
import logging
from typing import overload

from attr import evolve, field
from attrs import define

from logprep.abc.output import CriticalOutputError, Output
from logprep.connector.confluent_kafka.output import ConfluentKafkaOutput
from logprep.metrics.metrics import CounterMetric, Metric

logger = logging.getLogger("KafkaOutput")


class ConfluentKafkaGeneratorOutput(ConfluentKafkaOutput):
    """Output class inheriting from the connector output class"""

    @define(kw_only=True, slots=False)
    class Metrics(ConfluentKafkaOutput.Metrics):
        """Metrics for ConfluentKafkaOutput"""

        processed_batches: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Number of processed batches",
                name="processed_batches",
            ),
        )
        """Total number of batches send to brokers"""

    _config: Output.Config

    @property
    def statistics(self) -> str:
        """Return the statistics of this connector as a formatted string."""
        stats: dict = {}
        metrics = filter(lambda x: not x.name.startswith("_"), self.metrics.__attrs_attrs__)
        if self._config.send_timeout > 0:
            self._producer.flush(self._config.send_timeout)  ##Need test
            self._producer.poll(self._config.send_timeout)  ##Need test

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

    @overload
    def store(self, document: str) -> None: ...

    @overload
    def store(self, document: dict) -> None: ...

    def store(self, document) -> None:

        with self.lock:
            self.metrics.processed_batches += 1
            topic, _, payload = document.partition(",")
            _, _, topic = topic.rpartition("/")
            self._config = evolve(self._config, topic=topic)
            documents = list(payload.split(";"))
            for item in documents:
                self.store_custom(item, topic)

    @Metric.measure_time()
    def store_custom(self, document: str, target: str) -> None:
        """Write document to Kafka into target topic.

        Parameters
        ----------
        document : str
            Document to be stored in target topic.
        target : str
            Topic to store document in.
        Raises
        ------
        CriticalOutputError
            Raises if any error except a BufferError occurs while writing into Kafka.

        """
        try:
            self._producer.produce(target, value=document)
            logger.debug("Produced message %s to topic %s", str(document), target)
            self._producer.poll(self._config.send_timeout)
            self.metrics.number_of_processed_events += 1
        except BufferError:
            self._producer.flush(timeout=self._config.flush_timeout)
            logger.debug("Buffer full, flushing")
        except Exception as error:
            raise CriticalOutputError(self, str(error), document) from error
