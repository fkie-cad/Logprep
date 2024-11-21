# pylint: disable=line-too-long
"""
ConfluentkafkaInput
===================

Logprep uses `confluent-kafka` python client library to communicate with kafka-clusters.
Important documentation sources are:

- `the python client github page <https://github.com/confluentinc/confluent-kafka-python>`_
- `the python client api documentation <https://docs.confluent.io/current/clients/confluent-kafka-python/>`_
- `first steps documentation on confluent.io <https://docs.confluent.io/current/clients/python.html#>`_
- `underlying c-library documentation (librdkafka) <https://github.com/edenhill/librdkafka>`_

Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    input:
      mykafkainput:
        type: confluentkafka_input
        topic: consumer
        kafka_config:
            bootstrap.servers: "127.0.0.1:9092,127.0.0.1:9093"
            group.id: "cgroup"
            enable.auto.commit: "true"
            session.timeout.ms: "6000"
            auto.offset.reset: "earliest"
"""
# pylint: enable=line-too-long
import logging
import os
from functools import cached_property, partial
from socket import getfqdn
from types import MappingProxyType
from typing import Optional, Tuple, Union

import msgspec
from attrs import define, field, validators
from confluent_kafka import (
    OFFSET_BEGINNING,
    OFFSET_END,
    OFFSET_INVALID,
    OFFSET_STORED,
    Consumer,
    KafkaException,
    Message,
    TopicPartition,
)
from confluent_kafka.admin import AdminClient

from logprep.abc.connector import Connector
from logprep.abc.input import (
    CriticalInputError,
    CriticalInputParsingError,
    FatalInputError,
    Input,
    InputWarning,
)
from logprep.metrics.metrics import CounterMetric, GaugeMetric
from logprep.util.validators import keys_in_validator

DEFAULTS = {
    "enable.auto.offset.store": "false",
    "enable.auto.commit": "true",
    "client.id": "<<hostname>>",
    "auto.offset.reset": "earliest",
    "session.timeout.ms": "6000",
    "statistics.interval.ms": "30000",
}


SPECIAL_OFFSETS = {
    OFFSET_BEGINNING,
    OFFSET_END,
    OFFSET_INVALID,
    OFFSET_STORED,
}

DEFAULT_RETURN = 0

logger = logging.getLogger("KafkaInput")


class ConfluentKafkaInput(Input):
    """A kafka input connector."""

    @define(kw_only=True, slots=False)
    class Metrics(Input.Metrics):
        """Metrics for ConfluentKafkaInput"""

        commit_failures: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="count of failed commits.",
                name="confluent_kafka_input_commit_failures",
            )
        )
        """count of failed commits. Is filled by `_commit_callback`"""
        commit_success: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="count of successful commits.",
                name="confluent_kafka_input_commit_success",
            )
        )
        """count of successful commits. Is filled by `_commit_callback`"""
        current_offsets: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="current offsets of the consumer.",
                name="confluent_kafka_input_current_offsets",
                inject_label_values=False,
            )
        )
        """current offsets of the consumer. Is filled by `_get_raw_event`"""
        committed_offsets: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="committed offsets of the consumer.",
                name="confluent_kafka_input_committed_offsets",
                inject_label_values=False,
            )
        )
        """committed offsets of the consumer. Is filled by `_commit_callback`"""

        librdkafka_age: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Time since this client instance was created (microseconds)",
                name="confluent_kafka_input_librdkafka_age",
            )
        )
        """Time since this client instance was created (microseconds)"""

        librdkafka_replyq: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Number of ops (callbacks, events, etc) waiting in queue for application to serve with rd_kafka_poll()",
                name="confluent_kafka_input_librdkafka_replyq",
            )
        )
        """Number of ops (callbacks, events, etc) waiting in queue for application to serve with rd_kafka_poll()"""
        librdkafka_tx: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Total number of requests sent to Kafka brokers",
                name="confluent_kafka_input_librdkafka_tx",
            )
        )
        """Total number of requests sent to Kafka brokers"""
        librdkafka_tx_bytes: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Total number of bytes transmitted to Kafka brokers",
                name="confluent_kafka_input_librdkafka_tx_bytes",
            )
        )
        """Total number of bytes transmitted to Kafka brokers"""

        librdkafka_rx: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Total number of responses received from Kafka brokers",
                name="confluent_kafka_input_librdkafka_rx",
            )
        )
        """Total number of responses received from Kafka brokers"""
        librdkafka_rx_bytes: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Total number of bytes received from Kafka brokers",
                name="confluent_kafka_input_librdkafka_rx_bytes",
            )
        )
        """Total number of bytes received from Kafka brokers"""
        librdkafka_rxmsgs: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Total number of messages consumed, not including ignored messages (due to offset, etc), from Kafka brokers.",
                name="confluent_kafka_input_librdkafka_rxmsgs",
            )
        )
        """Total number of messages consumed, not including ignored messages (due to offset, etc), from Kafka brokers."""
        librdkafka_rxmsg_bytes: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Total number of message bytes (including framing) received from Kafka brokers",
                name="confluent_kafka_input_librdkafka_rxmsg_bytes",
            )
        )
        """Total number of message bytes (including framing) received from Kafka brokers"""

        librdkafka_cgrp_stateage: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Time elapsed since last state change (milliseconds).",
                name="confluent_kafka_input_librdkafka_cgrp_stateage",
            )
        )
        """Time elapsed since last state change (milliseconds)."""
        librdkafka_cgrp_rebalance_age: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Time elapsed since last rebalance (assign or revoke) (milliseconds).",
                name="confluent_kafka_input_librdkafka_cgrp_rebalance_age",
            )
        )
        """Time elapsed since last rebalance (assign or revoke) (milliseconds)."""
        librdkafka_cgrp_rebalance_cnt: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Total number of rebalances (assign or revoke).",
                name="confluent_kafka_input_librdkafka_cgrp_rebalance_cnt",
            )
        )
        """Total number of rebalances (assign or revoke)."""
        librdkafka_cgrp_assignment_size: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Current assignment's partition count.",
                name="confluent_kafka_input_librdkafka_cgrp_assignment_size",
            )
        )
        """Current assignment's partition count."""

    @define(kw_only=True, slots=False)
    class Config(Input.Config):
        """Kafka input connector specific configurations"""

        topic: str = field(validator=validators.instance_of(str))
        """The topic from which new log messages will be fetched."""

        kafka_config: Optional[MappingProxyType] = field(
            validator=[
                validators.instance_of(MappingProxyType),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.instance_of(str),
                ),
                partial(keys_in_validator, expected_keys=["bootstrap.servers", "group.id"]),
            ],
            converter=MappingProxyType,
        )
        """ Kafka configuration for the kafka client.
        At minimum the following keys must be set:

        - bootstrap.servers (STRING): a comma separated list of kafka brokers
        - group.id (STRING): a unique identifier for the consumer group

        The following keys are injected by the connector and should not be set:

        - "enable.auto.offset.store" is set to "false",
        - "enable.auto.commit" is set to "true",

        For additional configuration options see the official:
        `librdkafka configuration <https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md>`_.

        .. datatemplate:import-module:: logprep.connector.confluent_kafka.input
            :template: defaults-renderer.tmpl

        """

    _last_valid_record: Message

    __slots__ = ["_last_valid_record"]

    def __init__(self, name: str, configuration: "Connector.Config") -> None:
        super().__init__(name, configuration)
        self._last_valid_record = None

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
            "enable.auto.offset.store": "false",
            "enable.auto.commit": "true",
            "on_commit": self._commit_callback,
            "stats_cb": self._stats_callback,
            "error_cb": self._error_callback,
        }
        DEFAULTS.update({"client.id": getfqdn()})
        DEFAULTS.update(
            {
                "group.instance.id": f"{getfqdn().strip('.')}-"
                f"Pipeline{self.pipeline_index}-pid{os.getpid()}"
            }
        )
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
    def _consumer(self) -> Consumer:
        """configures and returns the consumer

        Returns
        -------
        Consumer
            confluent_kafka consumer object
        """
        return Consumer(self._kafka_config)

    def _error_callback(self, error: KafkaException) -> None:
        """Callback for generic/global error events, these errors are typically
        to be considered informational since the client will automatically try to recover.
        This callback is served upon calling client.poll()

        Parameters
        ----------
        error : KafkaException
            the error that occurred
        """
        self.metrics.number_of_errors += 1
        logger.error(f"{self.describe()}: {error}")

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
        self.metrics.librdkafka_rx += stats.get("rx", DEFAULT_RETURN)
        self.metrics.librdkafka_tx += stats.get("tx", DEFAULT_RETURN)
        self.metrics.librdkafka_rx_bytes += stats.get("rx_bytes", DEFAULT_RETURN)
        self.metrics.librdkafka_tx_bytes += stats.get("tx_bytes", DEFAULT_RETURN)
        self.metrics.librdkafka_rxmsgs += stats.get("rxmsgs", DEFAULT_RETURN)
        self.metrics.librdkafka_rxmsg_bytes += stats.get("rxmsg_bytes", DEFAULT_RETURN)

        self.metrics.librdkafka_cgrp_stateage += stats.get("cgrp", {}).get(
            "stateage", DEFAULT_RETURN
        )
        self.metrics.librdkafka_cgrp_rebalance_age += stats.get("cgrp", {}).get(
            "rebalance_age", DEFAULT_RETURN
        )
        self.metrics.librdkafka_cgrp_rebalance_cnt += stats.get("cgrp", {}).get(
            "rebalance_cnt", DEFAULT_RETURN
        )
        self.metrics.librdkafka_cgrp_assignment_size += stats.get("cgrp", {}).get(
            "assignment_size", DEFAULT_RETURN
        )

    def _commit_callback(
        self, error: Union[KafkaException, None], topic_partitions: list[TopicPartition]
    ) -> None:
        """Callback used to indicate success or failure of asynchronous and
        automatic commit requests. This callback is served upon calling consumer.poll()

        Parameters
        ----------
        error : KafkaException | None
            the commit error, or None on success
        topic_partitions : list[TopicPartition]
            partitions with their committed offsets or per-partition errors

        Raises
        ------
        WarningInputError
            if `error` is not None
        """
        if error is not None:
            self.metrics.commit_failures += 1
            raise InputWarning(self, f"Could not commit offsets for {topic_partitions}: {error}")
        self.metrics.commit_success += 1
        for topic_partition in topic_partitions:
            offset = topic_partition.offset
            if offset in SPECIAL_OFFSETS:
                offset = 0
            labels = {
                "description": f"topic: {self._config.topic} - "
                f"partition: {topic_partition.partition}"
            }
            self.metrics.committed_offsets.add_with_labels(offset, labels)

    def describe(self) -> str:
        """Get name of Kafka endpoint and bootstrap servers.

        Returns
        -------
        kafka : str
            Description of the ConfluentKafkaInput connector.
        """
        base_description = super().describe()
        return f"{base_description} - Kafka Input: {self._config.kafka_config['bootstrap.servers']}"

    def _get_raw_event(self, timeout: float) -> bytearray:
        """Get next raw Message from Kafka.

        Parameters
        ----------
        timeout : float
           Timeout for obtaining a document from Kafka.

        Returns
        -------
        message_value : bytearray
            A raw document obtained from Kafka.

        Raises
        ------
        CriticalInputError
            Raises if an input is invalid or if it causes an error.
        """
        try:
            message = self._consumer.poll(timeout=timeout)
        except RuntimeError as error:
            raise FatalInputError(self, str(error)) from error
        if message is None:
            return None
        kafka_error = message.error()
        if kafka_error:
            raise CriticalInputError(
                self, "A confluent-kafka record contains an error code", str(kafka_error)
            )
        self._last_valid_record = message
        labels = {"description": f"topic: {self._config.topic} - partition: {message.partition()}"}
        self.metrics.current_offsets.add_with_labels(message.offset() + 1, labels)
        return message.value()

    def _get_event(self, timeout: float) -> Union[Tuple[None, None], Tuple[dict, dict]]:
        """Parse the raw document from Kafka into a json.

        Parameters
        ----------
        timeout : float
            Timeout for obtaining a raw document from Kafka.

        Returns
        -------
        event_dict : dict
            A parsed document obtained from Kafka.
        raw_event : bytearray
            A raw document obtained from Kafka.

        Raises
        ------
        CriticalInputError
            Raises if an input is invalid or if it causes an error.
        """
        raw_event = self._get_raw_event(timeout)
        if raw_event is None:
            return None, None
        try:
            event_dict = self._decoder.decode(raw_event.decode("utf-8"))
        except UnicodeDecodeError as error:
            raise CriticalInputParsingError(
                self, "Input record value is not 'utf-8' encoded", str(raw_event)
            ) from error
        except msgspec.DecodeError as error:
            raise CriticalInputParsingError(
                self, "Input record value is not a valid json string", raw_event
            ) from error
        return event_dict, raw_event

    @property
    def _enable_auto_offset_store(self) -> bool:
        return self._config.kafka_config.get("enable.auto.offset.store") == "true"

    @property
    def _enable_auto_commit(self) -> bool:
        return self._config.kafka_config.get("enable.auto.commit") == "true"

    def batch_finished_callback(self) -> None:
        """Store offsets for last message referenced by `self._last_valid_records`.
        Should be called after delivering the current message to the output or error queue.
        """
        if self._enable_auto_offset_store:
            return
        # in case the ConfluentKafkaInput._revoke_callback is triggered before the first message
        # was polled
        if not self._last_valid_record:
            return
        try:
            self._consumer.store_offsets(message=self._last_valid_record)
        except KafkaException as error:
            raise InputWarning(self, f"{error}, {self._last_valid_record}") from error

    def _assign_callback(self, consumer, topic_partitions):
        for topic_partition in topic_partitions:
            offset, partition = topic_partition.offset, topic_partition.partition
            logger.info(
                "%s was assigned to topic: %s | partition %s",
                consumer.memberid(),
                topic_partition.topic,
                partition,
            )
            if offset in SPECIAL_OFFSETS:
                offset = 0

            labels = {"description": f"topic: {self._config.topic} - partition: {partition}"}
            self.metrics.committed_offsets.add_with_labels(offset, labels)
            self.metrics.current_offsets.add_with_labels(offset, labels)

    def _revoke_callback(self, consumer, topic_partitions):
        for topic_partition in topic_partitions:
            self.metrics.number_of_warnings += 1
            logger.warning(
                "%s to be revoked from topic: %s | partition %s",
                consumer.memberid(),
                topic_partition.topic,
                topic_partition.partition,
            )
        self.batch_finished_callback()

    def _lost_callback(self, consumer, topic_partitions):
        for topic_partition in topic_partitions:
            self.metrics.number_of_warnings += 1
            logger.warning(
                "%s has lost topic: %s | partition %s - try to reassign",
                consumer.memberid(),
                topic_partition.topic,
                topic_partition.partition,
            )

    def shut_down(self) -> None:
        """Close consumer, which also commits kafka offsets."""
        self._consumer.close()
        super().shut_down()

    def health(self) -> bool:
        """Check the health of the component.

        Returns
        -------
        bool
            True if the component is healthy, False otherwise.
        """

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
            self._consumer.subscribe(
                [self._config.topic],
                on_assign=self._assign_callback,
                on_revoke=self._revoke_callback,
                on_lost=self._lost_callback,
            )
            super().setup()
        except KafkaException as error:
            raise FatalInputError(self, f"Could not setup kafka consumer: {error}") from error
