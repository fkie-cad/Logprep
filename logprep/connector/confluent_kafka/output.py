"""
ConfluentKafkaOutput
====================

This section contains the connection settings for ConfluentKafka, the default
index, the error index and a buffer size.

Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    output:
      my_confluent_kafka_output:
        type: confluentkafka_output
        topic: my_default_topic
        flush_timeout: 0.2
        send_timeout: 0
        kafka_config:
            bootstrap.servers: "127.0.0.1:9200,127.0.0.1:9200"
            compression.type: gzip
            request.required.acks: -1
            queue.buffering.max.ms: 0.5
"""

import logging
from functools import cached_property, partial
from socket import getfqdn
from types import MappingProxyType
from typing import Optional

from attrs import define, field, validators
from confluent_kafka import KafkaException, Producer
from confluent_kafka.admin import AdminClient

from logprep.abc.output import CriticalOutputError, FatalOutputError, Output
from logprep.metrics.metrics import GaugeMetric, Metric
from logprep.util.validators import keys_in_validator

DEFAULTS = {
    "request.required.acks": "-1",
    "linger.ms": "0.5",
    "compression.codec": "none",
    "client.id": "<<hostname>>",
    "queue.buffering.max.messages": "100000",
    "statistics.interval.ms": "1000",
}

DEFAULT_RETURN = 0

logger = logging.getLogger("KafkaOutput")


class ConfluentKafkaOutput(Output):
    """A kafka connector that serves as output connector."""

    @define(kw_only=True, slots=False)
    class Metrics(Output.Metrics):
        """Metrics for ConfluentKafkaOutput"""

        librdkafka_age: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Time since this client instance was created (microseconds)",
                name="confluent_kafka_output_librdkafka_age",
            )
        )
        """Time since this client instance was created (microseconds)"""
        librdkafka_msg_cnt: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Current number of messages in producer queues",
                name="confluent_kafka_output_librdkafka_msg_cnt",
            )
        )
        """Current number of messages in producer queues"""
        librdkafka_msg_size: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Current total size of messages in producer queues",
                name="confluent_kafka_output_librdkafka_msg_size",
            )
        )
        """Current total size of messages in producer queues"""
        librdkafka_msg_max: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Threshold: maximum number of messages allowed allowed on the "
                "producer queues",
                name="confluent_kafka_output_librdkafka_msg_max",
            )
        )
        """Threshold - maximum number of messages allowed allowed on the producer queues"""
        librdkafka_msg_size_max: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Threshold: maximum total size of messages allowed on the "
                "producer queues",
                name="confluent_kafka_output_librdkafka_msg_size_max",
            )
        )
        """Threshold - maximum total size of messages allowed on the producer queues"""
        librdkafka_tx: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Total number of requests sent to Kafka brokers",
                name="confluent_kafka_output_librdkafka_tx",
            )
        )
        """Total number of requests sent to Kafka brokers"""
        librdkafka_tx_bytes: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Total number of bytes transmitted to Kafka brokers",
                name="confluent_kafka_output_librdkafka_tx_bytes",
            )
        )
        """Total number of bytes transmitted to Kafka brokers"""
        librdkafka_rx: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Total number of responses received from Kafka brokers",
                name="confluent_kafka_output_librdkafka_rx",
            )
        )
        """Total number of responses received from Kafka brokers"""
        librdkafka_rx_bytes: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Total number of bytes received from Kafka brokers",
                name="confluent_kafka_output_librdkafka_rx_bytes",
            )
        )
        """Total number of bytes received from Kafka brokers"""
        librdkafka_txmsgs: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Total number of messages transmitted (produced) to Kafka brokers",
                name="confluent_kafka_output_librdkafka_txmsgs",
            )
        )
        """Total number of messages transmitted (produced) to Kafka brokers"""
        librdkafka_txmsg_bytes: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Total number of message bytes (including framing, such as per-Message "
                "framing and MessageSet/batch framing) transmitted to Kafka brokers",
                name="confluent_kafka_output_librdkafka_txmsg_bytes",
            )
        )
        """Total number of message bytes (including framing, such as per-Message framing and
        MessageSet/batch framing) transmitted to Kafka brokers"""

    @define(kw_only=True, slots=False)
    class Config(Output.Config):
        """Confluent Kafka Output Config"""

        topic: str = field(validator=validators.instance_of(str))
        """The topic into which the processed events should be written to."""
        flush_timeout: float = field(
            validator=validators.instance_of(float), converter=float, default=0
        )
        """The maximum time in seconds to wait for the producer to flush the messages
        to kafka broker. If the buffer is full, the producer will block until the buffer
        is empty or the timeout is reached. This implies that the producer does not
        wait for all messages to be send to the broker, if the timeout is reached
        before the buffer is empty. Default is :code:`0`.
        """
        send_timeout: float = field(
            validator=validators.instance_of(float), converter=float, default=0
        )
        """The maximum time in seconds to wait for an answer from the broker on polling.
        Default is :code:`0`."""
        kafka_config: Optional[MappingProxyType] = field(
            validator=[
                validators.instance_of(MappingProxyType),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.instance_of((str, dict)),
                ),
                partial(keys_in_validator, expected_keys=["bootstrap.servers"]),
            ],
            factory=MappingProxyType,
            converter=MappingProxyType,
        )
        """ Kafka configuration for the kafka client.
        At minimum the following keys must be set:

        - bootstrap.servers (STRING): a comma separated list of kafka brokers

        For additional configuration options and their description see:
        <https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md>

        .. datatemplate:import-module:: logprep.connector.confluent_kafka.output
            :template: defaults-renderer.tmpl

        """

    @property
    def _kafka_config(self) -> dict:
        """Get the kafka configuration.

        Returns
        -------
        dict
            The kafka configuration.
        """
        injected_config = {
            "logger": logger,
            "stats_cb": self._stats_callback,
            "error_cb": self._error_callback,
        }
        DEFAULTS.update({"client.id": getfqdn()})
        return DEFAULTS | self._config.kafka_config | injected_config

    @cached_property
    def _admin(self) -> AdminClient:
        """configures and returns the admin client

        Returns
        -------
        AdminClient
            confluent_kafka admin client object
        """
        admin_config = {"bootstrap.servers": self._config.kafka_config["bootstrap.servers"]}
        for key, value in self._config.kafka_config.items():
            if key.startswith(("security.", "ssl.")):
                admin_config[key] = value
        return AdminClient(admin_config)

    @cached_property
    def _producer(self) -> Producer:
        return Producer(self._kafka_config)

    def _error_callback(self, error: KafkaException):
        """Callback for generic/global error events, these errors are typically
        to be considered informational since the client will automatically try to recover.
        This callback is served upon calling client.poll()

        Parameters
        ----------
        error : KafkaException
            the error that occurred
        """
        self.metrics.number_of_errors += 1
        logger.error(f"{self.describe()}: {error}")  # pylint: disable=logging-fstring-interpolation

    def _stats_callback(self, stats: str) -> None:
        """Callback for statistics data. This callback is triggered by poll()
        or flush every `statistics.interval.ms` (needs to be configured separately)

        Parameters
        ----------
        stats : str
            statistics from the underlying librdkafka library
            details about the data can be found here:
            https://github.com/confluentinc/librdkafka/blob/master/STATISTICS.md
        """

        stats = self._decoder.decode(stats)
        self.metrics.librdkafka_age += stats.get("age", DEFAULT_RETURN)
        self.metrics.librdkafka_msg_cnt += stats.get("msg_cnt", DEFAULT_RETURN)
        self.metrics.librdkafka_msg_size += stats.get("msg_size", DEFAULT_RETURN)
        self.metrics.librdkafka_msg_max += stats.get("msg_max", DEFAULT_RETURN)
        self.metrics.librdkafka_msg_size_max += stats.get("msg_size_max", DEFAULT_RETURN)
        self.metrics.librdkafka_tx += stats.get("tx", DEFAULT_RETURN)
        self.metrics.librdkafka_tx_bytes += stats.get("tx_bytes", DEFAULT_RETURN)
        self.metrics.librdkafka_rx += stats.get("rx", DEFAULT_RETURN)
        self.metrics.librdkafka_rx_bytes += stats.get("rx_bytes", DEFAULT_RETURN)
        self.metrics.librdkafka_txmsgs += stats.get("txmsgs", DEFAULT_RETURN)
        self.metrics.librdkafka_txmsg_bytes += stats.get("txmsg_bytes", DEFAULT_RETURN)

    def describe(self) -> str:
        """Get name of Kafka endpoint with the bootstrap server.

        Returns
        -------
        kafka : ConfluentKafka
            Acts as input and output connector.

        """
        base_description = super().describe()
        return (
            f"{base_description} - Kafka Output: "
            f"{self._config.kafka_config.get('bootstrap.servers')}"
        )

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

    @Metric.measure_time()
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
            logger.debug("Produced message %s to topic %s", str(document), target)
            self._producer.poll(self._config.send_timeout)
            self.metrics.number_of_processed_events += 1
        except BufferError:
            # block program until buffer is empty or timeout is reached
            self._producer.flush(timeout=self._config.flush_timeout)
            logger.debug("Buffer full, flushing")
        except Exception as error:
            raise CriticalOutputError(self, str(error), document) from error

    def shut_down(self) -> None:
        """ensures that all messages are flushed. According to
        https://confluent-kafka-python.readthedocs.io/en/latest/#confluent_kafka.Producer.flush
        flush without the timeout parameter will block until all messages are delivered.
        This ensures no messages will get lost on shutdown.
        """
        if self._producer is None:
            return
        remaining_messages = self._producer.flush()
        if remaining_messages:
            self.metrics.number_of_errors += 1
            logger.error(
                "Flushing producer timed out. %s messages are still in the buffer.",
                remaining_messages,
            )
        else:
            logger.info("Producer flushed successfully. %s messages remaining.", remaining_messages)

    def health(self) -> bool:
        """Check the health of kafka producer."""
        try:
            metadata = self._admin.list_topics(timeout=self._config.health_timeout)
            if not self._config.topic in metadata.topics:
                logger.error("Topic  '%s' does not exit", self._config.topic)
                return False
        except KafkaException as error:
            logger.error("Health check failed: %s", error)
            self.metrics.number_of_errors += 1
            return False
        return super().health()

    def setup(self) -> None:
        """Set the component up."""
        try:
            super().setup()
        except KafkaException as error:
            raise FatalOutputError(self, f"Could not setup kafka producer: {error}") from error
