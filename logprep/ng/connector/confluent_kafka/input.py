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
            session.timeout.ms: "6000"
            auto.offset.reset: "earliest"
            # some entries are disallowed and will be overwritten:
            # enable.auto.offset.store
            # enable.auto.commit
            # enable.partition.eof
"""

import concurrent
import functools
import logging
import os
import typing
from collections.abc import Iterator, Sequence
from functools import partial
from socket import getfqdn
from types import MappingProxyType  # pylint: disable=no-name-in-module

import msgspec
from attrs import define, field, validators
from confluent_kafka import (
    OFFSET_BEGINNING,
    OFFSET_END,
    OFFSET_INVALID,
    OFFSET_STORED,
    KafkaException,
    Message,
    TopicPartition,
)
from confluent_kafka.aio import AIOConsumer

from logprep.metrics.metrics import CounterMetric, GaugeMetric
from logprep.ng.abc.event import AcknowledgableEvent, ErrorEvent, LogEvent
from logprep.ng.abc.input import (
    CriticalInputError,
    CriticalInputParsingError,
    FatalInputError,
    Input,
    InputWarning,
)
from logprep.ng.connector.confluent_kafka.metadata import ConfluentKafkaInputMeta
from logprep.ng.connector.confluent_kafka.offset_commit_tracker import (
    OffsetCommitTracker,
)
from logprep.util.validators import keys_in_validator

DEFAULTS = {
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
                description=(
                    "Number of ops (callbacks, events, etc) waiting in "
                    "queue for application to serve with rd_kafka_consume()"
                ),
                name="confluent_kafka_input_librdkafka_replyq",
            )
        )
        """Number of ops (callbacks, events, etc) waiting in queue for application
           to serve with rd_kafka_consume()
        """
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
                description=(
                    "Total number of messages consumed, not including ignored messages"
                    "(due to offset, etc), from Kafka brokers."
                ),
                name="confluent_kafka_input_librdkafka_rxmsgs",
            )
        )
        """Total number of messages consumed, not including ignored messages
           (due to offset, etc), from Kafka brokers.
        """
        librdkafka_rxmsg_bytes: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description=(
                    "Total number of message bytes (including framing)"
                    "received from Kafka brokers"
                ),
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
                description="Total number of rebalance (assign or revoke).",
                name="confluent_kafka_input_librdkafka_cgrp_rebalance_cnt",
            )
        )
        """Total number of rebalance (assign or revoke)."""
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

        kafka_config: MappingProxyType = field(
            validator=(
                validators.instance_of(MappingProxyType),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.instance_of(str),
                ),
                partial(keys_in_validator, expected_keys=["bootstrap.servers", "group.id"]),
            ),
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

        .. security-best-practice::
           :title: Kafka Input Consumer Authentication and Encryption

           Kafka authentication is a critical aspect of securing your data pipeline.
           Ensure that you have the following configurations in place:

           - Use SSL/mTLS encryption for data in transit.
           - Configure SASL or mTLS authentication for your Kafka clients.
           - Regularly rotate your Kafka credentials and secrets.
        """

        max_workers: int = field(
            validator=validators.instance_of(int),
            default=2,
        )
        """
        The maximum number of concurrent worker tasks for message processing.
        Should generally not exceed the number of topic partitions.
        Defaults to 2.
        """

        consume_num_message: int = field(
            validator=validators.instance_of(int),
            default=200,
        )
        """
        Number of messages to consume once and then yield step by step.
        Defaults to 200.
        """

    __slots__ = ["_commit_tracker", "_consumer", "_executor", "_message_iter"]

    @property
    def config(self) -> Config:
        """Provides the properly typed rule configuration object"""
        return typing.cast(ConfluentKafkaInput.Config, self._config)

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
            "enable.partition.eof": "false",
            "on_commit": self._commit_callback,
            "stats_cb": self._stats_callback,
            "error_cb": self._error_callback,
        }
        fqdn = getfqdn()
        DEFAULTS.update({"client.id": fqdn})
        DEFAULTS.update(
            {
                "group.instance.id": f"{fqdn.strip('.')}-"
                f"Pipeline{self.pipeline_index}-pid{os.getpid()}"
            }
        )
        return DEFAULTS | self.config.kafka_config | injected_config

    async def setup(self) -> None:
        """Set the confluent kafka input connector."""

        try:
            self._executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=self.config.max_workers
            )

            self._consumer = AIOConsumer(self._kafka_config, executor=self._executor)
            self._message_iter: Iterator[Message] = iter([])

            await self._consumer.subscribe(
                [self.config.topic],
                on_assign=self._assign_callback,
                on_revoke=self._revoke_callback,
                on_lost=self._lost_callback,
            )

            self._commit_tracker = OffsetCommitTracker(topic=self.config.topic)
        except KafkaException as error:
            raise FatalInputError.from_error(
                self, error, "could not setup kafka consumer"
            ) from error

        await super().setup()

    async def _error_callback(self, error: KafkaException) -> None:
        """Callback for generic/global error events, these errors are typically
        to be considered informational since the client will automatically try to recover.
        This callback is served upon calling client.consume()

        Parameters
        ----------
        error : KafkaException
            the error that occurred
        """
        self.metrics.number_of_errors += 1
        logger.error("%s: %s", self.description, error)

    async def _stats_callback(self, stats_raw: str) -> None:
        """Callback for statistics data. This callback is triggered by consume()
        or flush every `statistics.interval.ms` (needs to be configured separately)

        Parameters
        ----------
        stats_raw : str
            statistics from the underlying librdkafka library
            details about the data can be found here:
            https://github.com/confluentinc/librdkafka/blob/master/STATISTICS.md
        """

        stats = self._decoder.decode(stats_raw)
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

    def _describe(self) -> str:
        """Get name of Kafka endpoint and bootstrap servers"""
        return (
            f"{super()._describe()} - Kafka Input: {self.config.kafka_config['bootstrap.servers']}"
        )

    async def _get_next_message(self, timeout: float) -> Message | None:
        try:
            return next(self._message_iter)
        except StopIteration:
            pass

        try:
            self._message_iter = iter(
                await self._consumer.consume(
                    num_messages=self.config.consume_num_message, timeout=timeout
                )
            )
        except RuntimeError as error:
            raise FatalInputError.from_error(self, error) from error

        return next(self._message_iter, None)

    async def _get_raw_event(self, timeout: float) -> tuple[bytes, ConfluentKafkaInputMeta] | None:
        """Get next raw Message from Kafka"""

        message = await self._get_next_message(timeout)

        if message is None:
            return None

        if message_error := message.error():
            raise CriticalInputError.from_message(
                self, f"encountered kafka error: {str(message_error)}"
            )

        message_value = message.value()
        partition = message.partition()
        offset = message.offset()

        if message_value is None or partition is None or offset is None:
            logger.warning("Unexpected empty input message or empty metadata. Skipping")
            return None

        self.metrics.current_offsets.add_with_labels(
            offset + 1, ConfluentKafkaInput._message_labels(self.config.topic, partition)
        )

        return message_value, ConfluentKafkaInputMeta(partition=partition, offset=offset)

    @staticmethod
    @functools.lru_cache(maxsize=64)
    def _message_labels(topic: str, partition: int) -> dict[str, str]:
        return {"description": f"topic: {topic} - partition: {partition}"}

    async def _get_event(self, timeout: float) -> LogEvent | ErrorEvent | None:
        """Parse the raw document from Kafka into a json"""

        data = await self._get_raw_event(timeout)

        if data is None:
            return None

        raw_event, metadata = data

        try:
            return LogEvent(
                self._decode_raw_event(raw_event),
                original=raw_event,
                input_meta=metadata,
            )
        except CriticalInputParsingError as error:
            return ErrorEvent.from_input_failure(
                original=raw_event, input_meta=metadata, cause=error
            )

    def _decode_raw_event(self, raw_event: bytes) -> dict:
        """Parse the raw document from Kafka into a json."""
        try:
            return self._decoder.decode(raw_event)
        except msgspec.DecodeError as error:
            raise CriticalInputParsingError.from_message(
                self, "Input record value is not a valid json string representing an object"
            ) from error

    async def _assign_callback(
        self, _: AIOConsumer, topic_partitions: list[TopicPartition]
    ) -> None:
        try:
            committed_offsets: list[TopicPartition] = await self._consumer.committed(
                topic_partitions
            )
        except KafkaException as error:
            raise FatalInputError.from_error(self, error, "failed to get committed offsets")

        for tp in topic_partitions:
            try:
                offset = next(p.offset for p in committed_offsets if p.partition == tp.partition)
            except StopIteration as error:
                raise FatalInputError.from_message(
                    self, f"failed to get committed offset for partition {tp.partition}"
                ) from error

            if offset in SPECIAL_OFFSETS:
                # for an empty partition, committed offset is -1001 (OFFSET_INVALID)
                # hence we reset to 0 as the first
                offset = 0

            logger.info(
                "%s was assigned to topic: %s | partition %s | offset %d",
                await self._get_memberid(),
                tp.topic,
                tp.partition,
                offset,
            )

            labels = ConfluentKafkaInput._message_labels(self.config.topic, tp.partition)
            self.metrics.committed_offsets.add_with_labels(offset, labels)
            self.metrics.current_offsets.add_with_labels(offset, labels)

            self._commit_tracker.register_partition(tp.partition, offset)

    async def _revoke_callback(
        self, _: AIOConsumer, topic_partitions: list[TopicPartition]
    ) -> None:
        for tp in topic_partitions:
            self.metrics.number_of_warnings += 1
            member_id = await self._get_memberid()
            logger.warning(
                "%s to be revoked from topic: %s | partition %s", member_id, tp.topic, tp.partition
            )
            self._commit_tracker.unregister_partition(tp.partition)

    async def _lost_callback(self, _: AIOConsumer, topic_partitions: list[TopicPartition]) -> None:
        for tp in topic_partitions:
            self.metrics.number_of_warnings += 1
            member_id = await self._get_memberid()
            logger.warning(
                "%s has lost topic: %s | partition %s", member_id, tp.topic, tp.partition
            )
            self._commit_tracker.unregister_partition(tp.partition)

    async def _commit_callback(
        self, error: KafkaException | None, topic_partitions: list[TopicPartition]
    ) -> None:
        """Callback used to indicate success or failure of asynchronous and
        automatic commit requests. This callback is served upon calling consumer.consume()

        Parameters
        ----------
        error : KafkaException | None
            the commit error, or None on success
        topic_partitions : list[TopicPartition]
            partitions with their committed offsets or per-partition errors
        """

        if error is not None:
            self.metrics.commit_failures += 1
            raise InputWarning.from_error(self, error, "Could not commit offsets")
        self.metrics.commit_success += 1
        for tp in topic_partitions:
            offset = tp.offset
            if offset in SPECIAL_OFFSETS:
                offset = 0
            labels = ConfluentKafkaInput._message_labels(self.config.topic, tp.partition)
            self.metrics.committed_offsets.add_with_labels(offset, labels)

    async def _get_memberid(self) -> str | None:
        try:
            if self._consumer is not None:
                return self._consumer._consumer.memberid()  # pylint: disable=protected-access
        except RuntimeError as error:
            logger.error("Failed to retrieve member ID: %s", error)
        return None

    async def health(self) -> bool:  # type: ignore[override]
        """Check the health of the component.

        Returns
        -------
        bool
            True if the component is healthy, False otherwise.
        """

        if not await super().health():
            return False

        try:
            metadata = await self._consumer.list_topics(timeout=self.config.health_timeout)
            if self.config.topic not in metadata.topics:
                logger.error("Topic  '%s' does not exit", self.config.topic)
                return False
        except KafkaException as error:
            logger.error("Health check failed: %s", error)
            self.metrics.number_of_errors += 1
            return False
        return True

    async def acknowledge(self, events: Sequence[AcknowledgableEvent]):
        commit_offsets = list(
            self._commit_tracker.advance_offsets(
                typing.cast(ConfluentKafkaInputMeta, event.input_meta) for event in events
            )
        )

        if commit_offsets:
            try:
                logger.debug("storing offsets for %d partitions", len(commit_offsets))
                await self._consumer.store_offsets(offsets=commit_offsets)
            except KafkaException as error:
                # only a warning as the next call will generally store higher offsets
                raise InputWarning.from_error(
                    self,
                    error,
                    message=f"could not store offsets ({', '.join(map(str, commit_offsets))})",
                ) from error

    async def shut_down(self) -> None:
        """Shut down the confluent kafka input connector and cleanup resources."""

        if self._consumer is not None:
            await self._consumer.unsubscribe()
            await self._consumer.close()
            self._consumer = None  # type: ignore
        if self._executor is not None:
            self._executor.shutdown()

        await super().shut_down()
