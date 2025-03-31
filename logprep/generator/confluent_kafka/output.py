"""
KafkaConfluentGeneratorOutput
==========

The logprep confluent kafka generator inheriting from the confluent kafka connector output.
Sends the documents written by the generator to a topic endpoint.
"""

import json
import logging

from attr import evolve, field
from attrs import define

from logprep.abc.output import Output
from logprep.connector.confluent_kafka.output import ConfluentKafkaOutput
from logprep.metrics.metrics import CounterMetric

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

    def __init__(self, name, configuration) -> None:
        super().__init__(name, configuration)
        self.target: None | str = None

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

    def store(self, document: str) -> None:  # type: ignore

        self.metrics.processed_batches += 1
        topic, _, payload = document.partition(",")
        _, _, topic = topic.rpartition("/")
        self._config = evolve(self._config, topic=topic)
        documents = list(payload.split(";"))
        for item in documents:
            self.store_custom(item, topic)
