"""
ConfluentKafkaOutput
====================

This section contains the connection settings for ConfluentKafka, the default
index, the error index and a buffer size. Documents are sent in batches to Elasticsearch to reduce
the amount of times connections are created.

Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    output:
      my_confluent_kafka_output:
        type: confluentkafka_output
        topic: my_default_topic
        error_topic: my_error_topic
        flush_timeout: 0.2
        send_timeout: 0
        maximum_backlog: 100000
        kafka_config:
            bootstrap.servers: "127.0.0.1:9200,127.0.0.1:9200"
            compression.type: gzip
            request.required.acks: -1
            queue.buffering.max.ms: 0.5
"""

import json
from datetime import datetime
from functools import cached_property
from socket import getfqdn
from typing import Optional

from attrs import define, field, validators
from confluent_kafka import KafkaException, Producer

from logprep.abc.output import CriticalOutputError, FatalOutputError, Output

logprep_kafka_defaults = {
    "acks": "-1",
    "linger.ms": "0.5",
    "compression.type": "none",
    "client.id": getfqdn(),
    "queue.buffering.max.messages": "100000",
}


class ConfluentKafkaOutput(Output):
    """A kafka connector that serves as output connector."""

    @define(kw_only=True, slots=False)
    class Config(Output.Config):
        """Confluent Kafka Output Config"""

        topic: str = field(validator=validators.instance_of(str))
        error_topic: str
        flush_timeout: float
        send_timeout: int = field(validator=validators.instance_of(int), default=0)
        kafka_config: Optional[dict] = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.instance_of((str, dict)),
                ),
            ],
            factory=dict,
        )
        """ Kafka configuration for the kafka client.
        At minimum the following keys must be set:
        - bootstrap.servers
        For possible configuration options see: 
        <https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md>
        """

    @cached_property
    def _producer(self):
        injected_config = {
            "logger": self._logger,
        }
        self._config.kafka_config = logprep_kafka_defaults | self._config.kafka_config
        return Producer(self._config.kafka_config | injected_config)

    def describe(self) -> str:
        """Get name of Kafka endpoint with the bootstrap server.

        Returns
        -------
        kafka : ConfluentKafka
            Acts as input and output connector.

        """
        base_description = super().describe()
        return f"{base_description} - Kafka Output: {self._config.kafka_config.get('bootstrap.servers')}"

    def store(self, document: dict) -> Optional[bool]:
        """Store a document in the producer topic.

        Parameters
        ----------
        document : dict
           Document to store.

        Returns
        -------
        Returns True to inform the pipeline to call the batch_finished_callback method in the
        configured input
        """
        self.store_custom(document, self._config.topic)
        self.metrics.number_of_processed_events += 1
        if self.input_connector:
            self.input_connector.batch_finished_callback()

    def store_custom(self, document: dict, target: str) -> None:
        """Write document to Kafka into target topic.

        Parameters
        ----------
        document : dict
            Document to be stored in target topic.
        target : str
            Topic to store document in.
        Raises
        ------
        CriticalOutputError
            Raises if any error except a BufferError occurs while writing into Kafka.

        """
        try:
            self._producer.produce(target, value=self._encoder.encode(document))
            self._producer.poll(self._config.send_timeout)
        except BufferError:
            # block program until buffer is empty
            self._producer.flush(timeout=self._config.flush_timeout)
        except BaseException as error:
            raise CriticalOutputError(
                self, f"Error storing output document -> {error}", document
            ) from error

    def store_failed(
        self, error_message: str, document_received: dict, document_processed: dict
    ) -> None:
        """Write errors into error topic for documents that failed processing.

        Parameters
        ----------
        error_message : str
           Error message to write into Kafka document.
        document_received : dict
            Document as it was before processing.
        document_processed : dict
            Document after processing until an error occurred.

        """
        value = {
            "error": error_message,
            "original": document_received,
            "processed": document_processed,
            "timestamp": str(datetime.now()),
        }
        try:
            self._producer.produce(
                self._config.error_topic,
                value=json.dumps(value, separators=(",", ":")).encode("utf-8"),
            )
            self._producer.poll(self._config.send_timeout)
        except BufferError:
            # block program until buffer is empty
            self._producer.flush(timeout=self._config.flush_timeout)

    def setup(self):
        super().setup()
        try:
            _ = self._producer
        except (KafkaException, ValueError) as error:
            raise FatalOutputError(self, str(error)) from error

    def shut_down(self) -> None:
        """ensures that all messages are flushed"""
        if self._producer is not None:
            self._producer.flush(self._config.flush_timeout)
