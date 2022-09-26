"""
ConfluentKafkaOutput
----------------------

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
        bootstrapservers: [127.0.0.1:9200]
        topic: my_default_topic
        error_topic: my_error_topic
        flush_timeout: 0.2
        send_timeout: 0
        compression: gzip
        maximum_backlog: 100000
        ack_policy: -1
        linger_duration: 0.5
        ssl: {"cafile": None, "certfile": None, "keyfile": None, "password": None}
"""

import json
import sys
from datetime import datetime
from functools import partial
from socket import getfqdn
from typing import List, Optional

from attrs import define, field, validators
from confluent_kafka import Producer

from logprep.abc.output import Output, CriticalOutputError
from logprep.util.validators import dict_with_keys_validator

if sys.version_info.minor < 8:  # pragma: no cover
    from backports.cached_property import cached_property  # pylint: disable=import-error
else:
    from functools import cached_property


class ConfluentKafkaOutput(Output):
    """A kafka connector that serves as output connector."""

    @define(kw_only=True, slots=False)
    class Config(Output.Config):
        """Confluent Kafka Output Config"""

        bootstrapservers: List[str]
        topic: str = field(validator=validators.instance_of(str))
        error_topic: str
        flush_timeout: float
        send_timeout: int = field(validator=validators.instance_of(int), default=0)
        compression: str = field(
            validator=[
                validators.instance_of(str),
                validators.in_(["snappy", "gzip", "lz4", "zstd", "none"]),
            ],
            default="none",
        )
        maximum_backlog: int = field(
            validator=[validators.instance_of(int), validators.gt(0)], default=100000
        )
        ack_policy: int = field(
            validator=[validators.instance_of(int), validators.in_([0, 1, -1])],
            converter=lambda x: -1 if x == "all" else x,
            default=-1,
        )
        linger_duration: float = field(
            validator=[validators.instance_of(float)], converter=float, default=0.5
        )
        ssl: dict = field(
            validator=[
                validators.instance_of(dict),
                partial(
                    dict_with_keys_validator,
                    expected_keys=["cafile", "certfile", "keyfile", "password"],
                ),
            ],
            default={"cafile": None, "certfile": None, "keyfile": None, "password": None},
        )

    @cached_property
    def _client_id(self):
        return getfqdn()

    @cached_property
    def _producer(self):
        return Producer(self._confluent_settings)

    @cached_property
    def _confluent_settings(self) -> dict:
        """generate confluence settings mapping

        Returns
        -------
        dict
            the translated confluence settings
        """
        configuration = {
            "bootstrap.servers": ",".join(self._config.bootstrapservers),
            "queue.buffering.max.messages": self._config.maximum_backlog,
            "compression.type": self._config.compression,
            "acks": self._config.ack_policy,
            "linger.ms": self._config.linger_duration,
        }
        ssl_settings_are_setted = any(self._config.ssl[key] for key in self._config.ssl)
        if ssl_settings_are_setted:
            configuration.update(
                {
                    "security.protocol": "SSL",
                    "ssl.ca.location": self._config.ssl["cafile"],
                    "ssl.certificate.location": self._config.ssl["certfile"],
                    "ssl.key.location": self._config.ssl["keyfile"],
                    "ssl.key.password": self._config.ssl["password"],
                }
            )
        return configuration

    def describe(self) -> str:
        """Get name of Kafka endpoint with the bootstrap server.

        Returns
        -------
        kafka : ConfluentKafka
            Acts as input and output connector.

        """
        base_description = super().describe()
        return f"{base_description} - Kafka Output: {self._config.bootstrapservers[0]}"

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
            self._producer.produce(
                target, value=json.dumps(document, separators=(",", ":")).encode("utf-8")
            )
            self._producer.poll(self._config.send_timeout)
        except BufferError:
            # block program until buffer is empty
            self._producer.flush(timeout=self._config.flush_timeout)
        except BaseException as error:
            raise CriticalOutputError(
                f"Error storing output document: ({error})", document
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

    def shut_down(self) -> None:
        """ensures that all messages are flushed"""
        if self._producer is not None:
            self._producer.flush(self._config.flush_timeout)
