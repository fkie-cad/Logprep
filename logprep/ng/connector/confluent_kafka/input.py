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

import asyncio
import concurrent
import logging
import typing
from collections.abc import Iterable, Iterator, Sequence
from functools import cached_property, partial
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
from logprep.util.environ import ENV_VARS
from logprep.util.validators import keys_in_validator

DEFAULTS = {
    "auto.offset.reset": "earliest",
    "session.timeout.ms": "45000",
    "statistics.interval.ms": "30000",
    "partition.assignment.strategy": "cooperative-sticky",
}

SPECIAL_OFFSETS = {
    OFFSET_BEGINNING,
    OFFSET_END,
    OFFSET_INVALID,
    OFFSET_STORED,
}

DEFAULT_RETURN = 0
DEFAULT_MEMBER_ID = "MISSING_MEMBER_ID"

logger = logging.getLogger("KafkaInput")


@define(kw_only=True, slots=True)
class _PartitionState:
    """Offset bookkeeping, drain signalling and pre-bound metrics of one partition.

    Registered on assignment, unregistered on revocation or loss.
    """

    next_expected_offset: int
    """Offset to commit next. Everything below is acknowledged and gap free."""

    last_dispatched_offset: int = field(default=-1)
    """Last offset received from kafka and handed to the pipeline. Drain target for rebalancing."""

    committable_offsets: set[int] = field(factory=set)
    """Acknowledged offsets above `next_expected_offset`, possibly with gaps."""

    current_offset_gauge: GaugeMetric
    """`current_offsets` child, pre-bound to this topic/partition."""

    committed_offset_gauge: GaugeMetric
    """`committed_offsets` child, pre-bound to this topic/partition."""

    @property
    def is_drained(self) -> bool:
        """True if every received offset is acknowledged."""
        return self.next_expected_offset > self.last_dispatched_offset


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

        revoke_drain_timeouts: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="count of revocations whose drain timed out.",
                name="confluent_kafka_input_revoke_drain_timeouts",
            )
        )
        """count of revocations whose drain timed out. Is filled by `_revoke_callback`"""

        revoked_messages_dropped: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="count of consumed messages dropped because their partition was revoked.",
                name="confluent_kafka_input_revoked_messages_dropped",
            )
        )
        """count of consumed messages dropped because their partition was revoked.
           Is filled by `_get_raw_event`
        """

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

        revoke_drain_timeout: float = field(
            validator=validators.instance_of(float),
            converter=float,
            default=120.0,
        )
        """
        Maximum number of seconds a partition revocation waits for in-flight events to be
        acknowledged before releasing the partitions anyway. Must stay well below
        `max.poll.interval.ms`, and above the accumulated batch intervals of the pipeline.
        Events still in flight when the timeout hits are reprocessed by the new owner.
        Defaults to 120.0.
        """

    __slots__ = [
        "_consumer",
        "_offsets_stored_signal",
        "_executor",
        "_member_id",
        "_message_iter",
        "_partitions",
    ]

    @cached_property
    def config(self) -> Config:
        """Provides the properly typed rule configuration object"""
        return typing.cast(ConfluentKafkaInput.Config, self._config)

    @cached_property
    def _metrics(self) -> Metrics:
        """Provides the properly typed metrics object"""
        return typing.cast(ConfluentKafkaInput.Metrics, self.metrics)

    @property
    def _kafka_config(self) -> dict:
        """Get the kafka configuration.

        Returns
        -------
        dict
            The kafka configuration.
        """
        forced_config = {
            "logger": logger,
            "enable.auto.offset.store": "false",
            "enable.auto.commit": "true",
            "enable.partition.eof": "false",
            "on_commit": self._commit_callback,
            "stats_cb": self._stats_callback,
            "error_cb": self._error_callback,
        }
        id_defaults = {"client.id": ENV_VARS.get("POD_NAME") or getfqdn()}
        return DEFAULTS | id_defaults | self.config.kafka_config | forced_config

    async def setup(self) -> None:
        """Set the confluent kafka input connector."""

        try:
            self._executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=self.config.max_workers
            )

            self._consumer = AIOConsumer(self._kafka_config, executor=self._executor)
            self._message_iter: Iterator[Message] = iter([])
            self._partitions: dict[int, _PartitionState] = {}
            self._offsets_stored_signal = asyncio.Event()
            self._member_id = DEFAULT_MEMBER_ID

            await self._consumer.subscribe(
                [self.config.topic],
                on_assign=self._assign_callback,
                on_revoke=self._revoke_callback,
                on_lost=self._lost_callback,
            )
        except KafkaException as error:
            raise FatalInputError.from_error(
                self, error, "could not setup kafka consumer"
            ) from error

        await super().setup()

    async def _error_callback(self, error: KafkaException) -> None:
        """
        Callback for generic/global error events, these errors are typically
        to be considered informational since the client will automatically try to recover.
        This callback is served upon calling client.consume()
        """
        self._metrics.number_of_errors.inc(1)
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
        self._metrics.librdkafka_age.set(stats.get("age", DEFAULT_RETURN))
        self._metrics.librdkafka_rx.set(stats.get("rx", DEFAULT_RETURN))
        self._metrics.librdkafka_tx.set(stats.get("tx", DEFAULT_RETURN))
        self._metrics.librdkafka_rx_bytes.set(stats.get("rx_bytes", DEFAULT_RETURN))
        self._metrics.librdkafka_tx_bytes.set(stats.get("tx_bytes", DEFAULT_RETURN))
        self._metrics.librdkafka_rxmsgs.set(stats.get("rxmsgs", DEFAULT_RETURN))
        self._metrics.librdkafka_rxmsg_bytes.set(stats.get("rxmsg_bytes", DEFAULT_RETURN))

        self._metrics.librdkafka_cgrp_stateage.set(
            stats.get("cgrp", {}).get("stateage", DEFAULT_RETURN)
        )
        self._metrics.librdkafka_cgrp_rebalance_age.set(
            stats.get("cgrp", {}).get("rebalance_age", DEFAULT_RETURN)
        )
        self._metrics.librdkafka_cgrp_rebalance_cnt.set(
            stats.get("cgrp", {}).get("rebalance_cnt", DEFAULT_RETURN)
        )
        self._metrics.librdkafka_cgrp_assignment_size.set(
            stats.get("cgrp", {}).get("assignment_size", DEFAULT_RETURN)
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

        if partition is None or offset is None:
            # only unpartitioned/invalid messages, which are error events handled above
            logger.warning("Message without partition or offset. Skipping")
            return None

        state = self._partitions.get(partition)
        if state is None:
            # consume() hands out messages of partitions revoked during the very same call,
            # see confluent-kafka-python#1013. They belong to the new owner now.
            self._metrics.revoked_messages_dropped.inc(1)
            return None

        if message_value is None:
            # a null value never enters the pipeline, so nothing would ever acknowledge
            # this offset and it would block the commit watermark forever
            logger.warning("Unexpected empty input message. Skipping")
            state.committable_offsets.add(offset)
            return None

        state.last_dispatched_offset = max(offset, state.last_dispatched_offset)
        state.current_offset_gauge.set(offset + 1)

        return message_value, ConfluentKafkaInputMeta(partition=partition, offset=offset)

    def _register_partition(self, partition: int, offset: int) -> None:
        """Start tracking `partition`, resuming at `offset` (as returned by `committed`)."""

        labels = {"description": f"topic: {self.config.topic} - partition: {partition}"}
        state = _PartitionState(
            next_expected_offset=offset,
            current_offset_gauge=self._metrics.current_offsets.child_collector(labels),
            committed_offset_gauge=self._metrics.committed_offsets.child_collector(labels),
        )
        state.current_offset_gauge.set(offset)
        state.committed_offset_gauge.set(offset)
        self._partitions[partition] = state

    def _unregister_partition(self, partition: int) -> None:
        """Stop tracking `partition`. Offsets not yet stored are lost."""

        state = self._partitions.pop(partition, None)
        if state is not None and state.committable_offsets:
            logger.warning(
                "offsets %s of partition %d were ready to commit and are now lost",
                sorted(state.committable_offsets),
                partition,
            )

    def _is_drained(self, partitions: Iterable[int]) -> bool:
        """True if every dispatched offset of `partitions` is acknowledged."""

        states = self._partitions
        return all(p not in states or states[p].is_drained for p in partitions)

    def _advance_offsets(self, metadata: Iterable[ConfluentKafkaInputMeta]) -> list[TopicPartition]:
        """Feed acknowledged offsets in and return the gap free offsets to store."""

        touched: set[int] = set()
        for item in metadata:
            state = self._partitions.get(item.partition)
            if state is None:
                logger.warning(
                    "received offset for unregistered partition: offset=%d, partition=%d",
                    item.offset,
                    item.partition,
                )
                continue
            if item.offset < state.next_expected_offset:
                logger.warning(
                    "offset %d already committed (<%d)", item.offset, state.next_expected_offset
                )
                continue
            state.committable_offsets.add(item.offset)
            touched.add(item.partition)

        offsets: list[TopicPartition] = []
        for partition in touched:
            state = self._partitions[partition]
            committable = state.committable_offsets
            next_offset = state.next_expected_offset
            while next_offset in committable:
                next_offset += 1
            if next_offset == state.next_expected_offset:
                continue
            committable.difference_update(range(state.next_expected_offset, next_offset))
            state.next_expected_offset = next_offset
            offsets.append(
                TopicPartition(self.config.topic, partition=partition, offset=next_offset)
            )
        return offsets

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

        self._member_id = await self._get_memberid()

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
                self._member_id,
                tp.topic,
                tp.partition,
                offset,
            )

            self._register_partition(tp.partition, offset)

    async def _revoke_callback(
        self, _: AIOConsumer, topic_partitions: list[TopicPartition]
    ) -> None:
        """Hold the partitions until their in-flight events are acknowledged.

        Runs inside `consume()`, so no new messages are dispatched while it waits and the
        rest of the pipeline keeps draining. Returning releases the partitions, therefore
        offsets not stored by then are reprocessed by the new owner.
        """

        partitions = [tp.partition for tp in topic_partitions]
        self._metrics.number_of_warnings.inc(len(partitions))

        try:
            logger.warning(
                "%s to be revoked from topic: %s | partitions %s",
                self._member_id,
                self.config.topic,
                partitions,
            )
            async with asyncio.timeout(self.config.revoke_drain_timeout):
                while not self._is_drained(partitions):
                    # no await between clear and wait, so no acknowledgement is missed
                    self._offsets_stored_signal.clear()
                    await self._offsets_stored_signal.wait()
        except TimeoutError:
            self._metrics.revoke_drain_timeouts.inc(1)
            logger.error(
                "drain timeout of %.1fs exceeded while revoking partitions %s, "
                "in-flight events will be reprocessed by the new owner",
                self.config.revoke_drain_timeout,
                partitions,
            )
        finally:
            # also on cancellation, otherwise the partitions leak
            for partition in partitions:
                self._unregister_partition(partition)

    async def _lost_callback(self, _: AIOConsumer, topic_partitions: list[TopicPartition]) -> None:
        # the assignment is already gone, draining would neither commit nor help
        partitions = [tp.partition for tp in topic_partitions]
        self._metrics.number_of_warnings.inc(len(partitions))
        for partition in partitions:
            self._unregister_partition(partition)
        logger.warning(
            "%s has lost topic: %s | partitions %s",
            self._member_id,
            self.config.topic,
            partitions,
        )

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
            self._metrics.commit_failures.inc(1)
            raise InputWarning.from_error(self, error, "Could not commit offsets")
        self._metrics.commit_success.inc(1)
        for tp in topic_partitions:
            state = self._partitions.get(tp.partition)
            if state is None:
                continue
            offset = tp.offset
            if offset in SPECIAL_OFFSETS:
                offset = 0
            state.committed_offset_gauge.set(offset)

    async def _get_memberid(self) -> str:
        """
        Fetches the memberid and ensures a string is returned (default value as fallback).
        """
        try:
            memberid = None
            if self._consumer is not None:
                memberid = self._consumer._consumer.memberid()  # pylint: disable=protected-access
        except RuntimeError as error:
            logger.error("Failed to retrieve member ID: %s", error)
        return memberid or DEFAULT_MEMBER_ID

    async def health(self) -> bool:  # type: ignore[override]
        """Check the health of the component."""

        if not await super().health():
            return False

        try:
            metadata = await self._consumer.list_topics(timeout=self.config.health_timeout)
            if self.config.topic not in metadata.topics:
                logger.error("Topic  '%s' does not exit", self.config.topic)
                return False
        except KafkaException as error:
            logger.error("Health check failed: %s", error)
            self._metrics.number_of_errors.inc(1)
            return False
        return True

    async def acknowledge(self, events: Sequence[AcknowledgableEvent]):
        commit_offsets = self._advance_offsets(
            typing.cast(ConfluentKafkaInputMeta, event.input_meta) for event in events
        )

        if not commit_offsets:
            return

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
        finally:
            self._offsets_stored_signal.set()

    async def shut_down(self) -> None:
        """Shut down the confluent kafka input connector and cleanup resources."""

        if self._consumer is not None:
            await self._consumer.unsubscribe()
            await self._consumer.close()
            self._consumer = None  # type: ignore
        if self._executor is not None:
            self._executor.shutdown()

        await super().shut_down()
