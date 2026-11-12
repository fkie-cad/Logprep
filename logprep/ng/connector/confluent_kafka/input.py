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
            auto.offset.reset: "earliest"
            max.poll.interval.ms: "300000"
            # some entries are rejected if set:
            # enable.auto.offset.store
            # enable.auto.commit
            # enable.partition.eof

This connector requires the KIP-848 consumer group protocol and therefore a broker
on version 4.0.0 or later. It is the only protocol under which a revocation can be
held open to drain in-flight events and still commit their offsets.
"""

import asyncio
import concurrent
import logging
import typing
from collections.abc import Iterable, Iterator, Sequence
from functools import cached_property, partial
from socket import getfqdn

import msgspec
from attrs import Factory, define, field, validators
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
from logprep.ng.abc.event import AcknowledgableEvent, ErrorEvent, InputMeta, LogEvent
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

DEFAULT_CONFIG = {
    "auto.offset.reset": "earliest",
    "statistics.interval.ms": "30000",
    "max.poll.interval.ms": "300000",
}

_ENFORCED_CONFIG = {
    "enable.auto.offset.store": "false",  # we track & store offsets ourselves
    "enable.auto.commit": "true",  # required to happen automatically
    "enable.partition.eof": "false",  # signal not needed; we wait for further messages
    "group.protocol": "consumer",  # we only support kafka >= 4.x; thus KIP-848
}
"""Enforced kafka configuration closely linked to our implementation"""

REJECTED_CONFIG = {
    "session.timeout.ms": "set group.consumer.session.timeout.ms on the broker (KIP-848)",
    "heartbeat.interval.ms": "set group.consumer.heartbeat.interval.ms on the broker (KIP-848)",
    "partition.assignment.strategy": "use group.remote.assignor instead (KIP-848)",
    "group.protocol.type": "not applicable to the consumer group protocol (KIP-848)",
} | {key: f'enforced as "{value}"' for key, value in _ENFORCED_CONFIG.items()}
"""Keys not allowed to be set & corresponding hint"""

_DRAIN_TIMEOUT_HEADROOM_S = 10.0
"""Seconds a drain leaves of `max.poll.interval.ms` to commit offsets before being fenced."""

_SPECIAL_OFFSETS = {
    OFFSET_BEGINNING,
    OFFSET_END,
    OFFSET_INVALID,
    OFFSET_STORED,
}

_MISSING_STATISTIC = 0
"""Reported for a statistic librdkafka does not include."""

_DEFAULT_MEMBER_ID = "MISSING_MEMBER_ID"

logger = logging.getLogger("KafkaInput")


def _validate_supported_options(_, __, kafka_config: dict[str, str]) -> None:
    rejected = kafka_config.keys() & REJECTED_CONFIG.keys()
    if rejected:
        reasons = "; ".join(f"{key}: {REJECTED_CONFIG[key]}" for key in sorted(rejected))
        raise ValueError(f"kafka_config contains unsupported entries: {reasons}")


def _max_drain_timeout_s(kafka_config: dict[str, str]) -> float:
    """The longest drain that cannot outlive the rebalance timeout granted by the broker."""
    poll_ms = kafka_config.get("max.poll.interval.ms", DEFAULT_CONFIG["max.poll.interval.ms"])
    return int(poll_ms) / 1000 - _DRAIN_TIMEOUT_HEADROOM_S


def _validate_drain_fits_poll_interval(conf, _, revoke_drain_timeout: float) -> None:
    budget = _max_drain_timeout_s(conf.kafka_config)
    if revoke_drain_timeout > budget:
        raise ValueError(
            f"revoke_drain_timeout ({revoke_drain_timeout:.1f}s) must not exceed "
            f"{budget:.1f}s, which is max.poll.interval.ms minus "
            f"{_DRAIN_TIMEOUT_HEADROOM_S:.0f}s of headroom"
        )


@define(kw_only=True, slots=True)
class _PartitionState:
    """Offset bookkeeping, drain signalling and pre-bound metrics of one partition"""

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
        """Count of failed commits"""

        commit_success: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="count of successful commits.",
                name="confluent_kafka_input_commit_success",
            )
        )
        """Count of successful commits`"""

        current_offsets: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="current offsets of the consumer.",
                name="confluent_kafka_input_current_offsets",
                inject_label_values=False,
            )
        )
        """Current offsets of the consumer"""

        committed_offsets: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="committed offsets of the consumer.",
                name="confluent_kafka_input_committed_offsets",
                inject_label_values=False,
            )
        )
        """Committed offsets of the consumer"""

        revoke_drain_timeouts: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="count of revocations whose drain timed out.",
                name="confluent_kafka_input_revoke_drain_timeouts",
            )
        )
        """Count of revocations whose drain timed out"""

        revoke_drain_seconds: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="seconds the last revocation spent draining in-flight events.",
                name="confluent_kafka_input_revoke_drain_seconds",
            )
        )
        """Seconds the last revocation spent draining"""

        orphaned_acknowledgements: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="count of acknowledgements for partitions no longer held.",
                name="confluent_kafka_input_orphaned_acknowledgements",
            )
        )
        """Count of acknowledgements arriving after their partition was released"""

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

        kafka_config: dict[str, str] = field(
            validator=(
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.instance_of(str),
                ),
                partial(keys_in_validator, expected_keys=["bootstrap.servers", "group.id"]),
                _validate_supported_options,
            ),
        )
        """ Kafka configuration for the kafka client.
        At minimum the following keys must be set:

        - bootstrap.servers (STRING): a comma separated list of kafka brokers
        - group.id (STRING): a unique identifier for the consumer group

        "client.id" defaults to the POD_NAME environment variable, else the host's FQDN.

        For additional configuration options see the official:
        `librdkafka configuration <https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md>`_.

        .. datatemplate:import-module:: logprep.ng.connector.confluent_kafka.input
            :template: defaults-renderer.tmpl

        .. security-best-practice::
           :title: Kafka Input Consumer Authentication and Encryption

           Kafka authentication is a critical aspect of securing your data pipeline.
           Ensure that you have the following configurations in place:

           - Use SSL/mTLS encryption for data in transit.
           - Configure SASL or mTLS authentication for your Kafka clients.
           - Regularly rotate your Kafka credentials and secrets.
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
            validator=(
                validators.instance_of(float),
                validators.gt(0),
                _validate_drain_fits_poll_interval,
            ),
            converter=float,
            default=Factory(
                lambda config: _max_drain_timeout_s(config.kafka_config), takes_self=True
            ),
        )
        """
        Maximum number of seconds a partition revocation waits for in-flight events to be
        acknowledged before releasing the partitions anyway. Events still in flight by
        then are reprocessed by the new owner, which generally leads to duplicates.

        Must exceed the accumulated batch intervals of the pipeline and stay 10s below
        `max.poll.interval.ms`, since overrunning that fences the member and loses the
        whole assignment. Defaults to that maximum.
        """

    __slots__ = [
        "_consumer",
        "_acknowledged_signal",
        "_offsets_dirty",
        "_consuming",
        "_executor",
        "_member_id",
        "_message_iter",
        "_partitions",
    ]

    @cached_property
    def config(self) -> Config:
        """Provides the properly typed configuration object"""
        return typing.cast(ConfluentKafkaInput.Config, self._config)

    @cached_property
    def _metrics(self) -> Metrics:
        """Provides the properly typed metrics object"""
        return typing.cast(ConfluentKafkaInput.Metrics, self.metrics)

    @property
    def _kafka_config(self) -> dict:
        """Get the kafka configuration"""
        callbacks = {
            "logger": logger,
            "on_commit": self._commit_callback,
            "stats_cb": self._stats_callback,
            "error_cb": self._error_callback,
        }
        client_id = {"client.id": ENV_VARS.get("POD_NAME") or getfqdn()}
        return DEFAULT_CONFIG | client_id | self.config.kafka_config | _ENFORCED_CONFIG | callbacks

    async def setup(self) -> None:
        """Set the confluent kafka input connector."""

        try:
            # one thread for consume() and one for callbacks (e.g. on_revoke) inside consume()
            self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
            self._consumer = AIOConsumer(self._kafka_config, executor=self._executor)

            self._message_iter: Iterator[Message] = iter([])
            self._partitions: dict[int, _PartitionState] = {}
            self._acknowledged_signal = asyncio.Event()
            self._offsets_dirty = False
            self._consuming = False
            self._member_id = _DEFAULT_MEMBER_ID
        except KafkaException as error:
            raise FatalInputError.from_error(
                self, error, "could not setup kafka consumer"
            ) from error

        await super().setup()

        try:
            await self._consumer.subscribe(
                [self.config.topic],
                on_assign=self._assign_callback,
                on_revoke=self._revoke_callback,
                on_lost=self._lost_callback,
            )
        except KafkaException as error:
            raise FatalInputError.from_error(
                self, error, "could not subscribe kafka consumer"
            ) from error
        self._consuming = True

    async def _error_callback(self, error: KafkaException) -> None:
        """
        Callback for generic/global error events, these errors are typically
        to be considered informational since the client will automatically try to recover.
        This callback is served upon calling client.consume()
        """
        self._metrics.number_of_errors.inc(1)
        logger.error("%s: %s", self.description, error)

    async def _stats_callback(self, stats_raw: str) -> None:
        """Callback for statistics which is triggered by consume() every `statistics.interval.ms`

        Parameters
        ----------
        stats_raw : str
            statistics from the underlying librdkafka library; see also
            https://github.com/confluentinc/librdkafka/blob/master/STATISTICS.md
        """

        stats = self._decoder.decode(stats_raw)
        self._metrics.librdkafka_age.set(stats.get("age", _MISSING_STATISTIC))
        self._metrics.librdkafka_rx.set(stats.get("rx", _MISSING_STATISTIC))
        self._metrics.librdkafka_tx.set(stats.get("tx", _MISSING_STATISTIC))
        self._metrics.librdkafka_rx_bytes.set(stats.get("rx_bytes", _MISSING_STATISTIC))
        self._metrics.librdkafka_tx_bytes.set(stats.get("tx_bytes", _MISSING_STATISTIC))
        self._metrics.librdkafka_rxmsgs.set(stats.get("rxmsgs", _MISSING_STATISTIC))
        self._metrics.librdkafka_rxmsg_bytes.set(stats.get("rxmsg_bytes", _MISSING_STATISTIC))

        cgrp = stats.get("cgrp", {})
        self._metrics.librdkafka_cgrp_stateage.set(cgrp.get("stateage", _MISSING_STATISTIC))
        self._metrics.librdkafka_cgrp_rebalance_age.set(
            cgrp.get("rebalance_age", _MISSING_STATISTIC)
        )
        self._metrics.librdkafka_cgrp_rebalance_cnt.set(
            cgrp.get("rebalance_cnt", _MISSING_STATISTIC)
        )
        self._metrics.librdkafka_cgrp_assignment_size.set(
            cgrp.get("assignment_size", _MISSING_STATISTIC)
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

        # store pending offsets within the same worker as consume to avoid deadlocks
        await self._store_pending_offsets()

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
        """Get next raw message from kafka"""

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
            # theoretically impossible scenario; defensive log instead of simple assert
            logger.warning("skipped message without partition or offset")
            self._metrics.number_of_warnings.inc(1)
            return None

        state = self._partitions.get(partition)
        if state is None:
            # theoretically impossible scenario; defensive log instead of simple assert
            logger.warning(
                "skipped message of untracked partition %d at offset %d", partition, offset
            )
            self._metrics.number_of_warnings.inc(1)
            return None

        meta = ConfluentKafkaInputMeta(partition=partition, offset=offset)

        if message_value is None:
            # a null value (like a tombstone) never enters the pipeline,
            # but we need to acknowledge it
            self._metrics.number_of_warnings.inc(1)
            logger.warning(
                "skipped message without value of partition %d at offset %d", partition, offset
            )
            self._advance_offsets([meta])
            return None

        state.last_dispatched_offset = max(offset, state.last_dispatched_offset)
        state.current_offset_gauge.set(offset + 1)

        return message_value, meta

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

    def _advance_offsets(self, metadata: Iterable[InputMeta]) -> None:
        """Feed acknowledged offsets in and advance each partition's gap free offset."""

        orphaned = 0
        for item in metadata:
            assert isinstance(item, ConfluentKafkaInputMeta)
            state = self._partitions.get(item.partition)
            if state is None:
                # partition lost/revoked while message in-flight -> message has new owner now
                orphaned += 1
                continue
            if item.offset < state.next_expected_offset:
                logger.warning(
                    "offset %d already committed (<%d)", item.offset, state.next_expected_offset
                )
                continue
            state.committable_offsets.add(item.offset)

        if orphaned:
            self._metrics.orphaned_acknowledgements.inc(orphaned)
            logger.warning("discarded %d acknowledgements for released partitions", orphaned)

        for state in self._partitions.values():
            committable = state.committable_offsets
            next_offset = state.next_expected_offset
            while next_offset in committable:
                next_offset += 1
            if next_offset > state.next_expected_offset:
                committable.difference_update(range(state.next_expected_offset, next_offset))
                state.next_expected_offset = next_offset
                self._offsets_dirty = True

    async def _store_pending_offsets(self) -> None:
        """Hand every partition's acknowledged offset to librdkafka"""

        if not self._offsets_dirty or not self._partitions:
            return
        offsets = [
            TopicPartition(
                self.config.topic, partition=partition, offset=state.next_expected_offset
            )
            for partition, state in self._partitions.items()
        ]
        try:
            await self._consumer.store_offsets(offsets=offsets)
        except KafkaException as error:
            self._metrics.number_of_warnings.inc(1)
            logger.warning("could not store offsets, retrying with the next call: %s", error)
            return
        self._offsets_dirty = False

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

        try:
            # direct call: an offloaded one is rejected while this callback runs
            member_id = self._consumer._consumer.memberid()  # pylint: disable=protected-access
            self._member_id = member_id or _DEFAULT_MEMBER_ID
        except RuntimeError as error:
            logger.error("Failed to retrieve member ID: %s", error)

        for tp in topic_partitions:
            try:
                offset = next(p.offset for p in committed_offsets if p.partition == tp.partition)
            except StopIteration as error:
                raise FatalInputError.from_message(
                    self, f"failed to get committed offset for partition {tp.partition}"
                ) from error

            if offset in _SPECIAL_OFFSETS:
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

        The coordinator withholds these partitions from their next owner until this
        member acknowledges the revocation, which librdkafka only does once the
        callback returned, the partitions were unassigned and their offsets committed.

        - Runs inside `consume()` on an executor thread, so no further messages are
          dispatched meanwhile. The other pipeline workers are separate asyncio tasks
          and keep draining, which is what lets the wait terminate.
        - librdkafka pauses the fetchers of the whole assignment, not just of the
          revoked partitions, so a long drain also costs throughput elsewhere.
        - The broker enforces `max.poll.interval.ms` as the rebalance timeout even
          though librdkafka does not enforce it during a blocking poll. Overrunning it
          is a fencing, not a late handover, and surfaces as `on_lost`.
        """

        partitions = [tp.partition for tp in topic_partitions]
        self._metrics.number_of_warnings.inc(len(partitions))
        logger.warning(
            "%s to be revoked from topic: %s | partitions %s",
            self._member_id,
            self.config.topic,
            partitions,
        )

        try:
            await self._drain(partitions)
            await self._store_pending_offsets()
        finally:
            for partition in partitions:
                self._unregister_partition(partition)

    async def _drain(self, partitions: list[int]) -> None:
        """Wait until every dispatched event of `partitions` is acknowledged, or time out."""

        started = asyncio.get_running_loop().time()
        try:
            async with asyncio.timeout(self.config.revoke_drain_timeout):
                while not self._is_drained(partitions):
                    self._acknowledged_signal.clear()
                    await self._acknowledged_signal.wait()

            logger.info(
                "drained partitions %s in %.1fs, offsets are committed on handover",
                partitions,
                asyncio.get_running_loop().time() - started,
            )
        except TimeoutError:
            self._metrics.revoke_drain_timeouts.inc(1)
            logger.error(
                "drain timeout of %.1fs exceeded while revoking partitions %s, "
                "in-flight events will be reprocessed by the new owner",
                self.config.revoke_drain_timeout,
                partitions,
            )
        finally:
            self._metrics.revoke_drain_seconds.set(asyncio.get_running_loop().time() - started)

    async def _lost_callback(self, _: AIOConsumer, topic_partitions: list[TopicPartition]) -> None:
        """Drop the partitions without draining; duplicates are likely for messages affected by this"""
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
            if offset in _SPECIAL_OFFSETS:
                offset = 0
            state.committed_offset_gauge.set(offset)

    async def health(self) -> bool:  # type: ignore[override]
        """
        Check that the topic exists until subscribed,
        afterwards calling the consumer could deadlock a rebalance
        """
        if not await super().health():
            return False
        if self._consuming:
            return True
        return await self._topic_available()

    async def _topic_available(self) -> bool:
        """Ask the broker whether the topic exists."""

        try:
            metadata = await self._consumer.list_topics(timeout=self.config.health_timeout)
        except KafkaException as error:
            logger.error("Health check failed: %s", error)
            self._metrics.number_of_errors.inc(1)
            return False
        if self.config.topic not in metadata.topics:
            logger.error("Topic '%s' does not exist", self.config.topic)
            return False
        return True

    async def acknowledge(self, events: Sequence[AcknowledgableEvent]):
        """Mark `events` as processed. In-memory only, the consume-loop stores the offsets"""
        self._advance_offsets(event.input_meta for event in events)
        self._acknowledged_signal.set()

    async def shut_down(self) -> None:
        """Shut down the confluent kafka input connector and cleanup resources."""

        if self._consumer is not None:
            await self._consumer.unsubscribe()
            await self._consumer.close()
            self._consumer = None  # type: ignore
        if self._executor is not None:
            self._executor.shutdown()

        await super().shut_down()
