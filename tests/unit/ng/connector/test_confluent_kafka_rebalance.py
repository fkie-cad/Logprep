# pylint: disable=missing-docstring
# pylint: disable=protected-access
"""Rebalancing the kafka input against librdkafka's in-process mock cluster.

By default `test.mock.num.brokers` runs a broker inside the process, so these tests
exercise real group coordination without docker. Setting `LOGPREP_TEST_KAFKA_BOOTSTRAP`
runs them against that broker instead, which has to be on Kafka 4.0 or later with the
consumer group protocol enabled. Only plaintext is supported. The compose example provides one:

    docker compose -f examples/compose/docker-compose.yml up -d --wait kafka
    LOGPREP_TEST_KAFKA_BOOTSTRAP=127.0.0.1:9092 \\
        pytest tests/unit/ng/connector/test_confluent_kafka_rebalance.py

The mock cluster never enforces the rebalance timeout, so the fencing test only runs
against a real broker.

The connector enforces the KIP-848 consumer protocol. The broker assigns partitions
and revokes them incrementally, and it holds a revoked partition back from its next
owner until the current owner has released it. The connector uses that window to
drain: it releases a partition only once every event it dispatched from there is
acknowledged. The tests drive every acknowledgement explicitly, so each phase of
that handover can be observed.
"""

import asyncio
import contextlib
import json
import os
import time
import uuid
from collections import Counter
from collections.abc import AsyncIterator, Callable, Iterable, Iterator
from itertools import groupby, islice
from unittest.mock import AsyncMock

import attrs
import pytest
from confluent_kafka import KafkaError, Message, Producer
from confluent_kafka.admin import AdminClient, NewTopic

from logprep.ng.abc.event import ErrorEvent, LogEvent
from logprep.ng.connector.confluent_kafka.input import ConfluentKafkaInput
from logprep.ng.connector.confluent_kafka.metadata import ConfluentKafkaInputMeta

pytestmark = pytest.mark.timeout(180)

PARTITIONS = 4  # the mock cluster auto creates topics with four partitions
ALL_PARTITIONS = set(range(PARTITIONS))
TIMEOUT_S = 10

KAFKA_BOOTSTRAP_ENV = "LOGPREP_TEST_KAFKA_BOOTSTRAP"
"""Bootstrap servers of a real broker to test against instead of the mock cluster"""

needs_real_broker = pytest.mark.skipif(
    not os.environ.get(KAFKA_BOOTSTRAP_ENV),
    reason=f"needs a real Kafka 4.x broker, set {KAFKA_BOOTSTRAP_ENV}",
)


async def until(predicate: Callable[[], object], seconds: float = 20) -> bool:
    """Poll `predicate` until it holds or `seconds` passed"""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.1)
    return bool(predicate())


@attrs.frozen(order=True)
class MessageMeta:
    partition: int
    offset: int


@attrs.frozen
class Kafka:
    """The broker to test against, a fresh topic with `PARTITIONS` partitions and a producer"""

    bootstrap: str
    topic: str
    producer: Producer


@pytest.fixture(name="kafka")
def fixture_kafka() -> Iterator[Kafka]:
    """On the broker from `LOGPREP_TEST_KAFKA_BOOTSTRAP`, else on an in-process mock cluster"""
    topic = f"rebalance-{uuid.uuid4().hex[:8]}"

    admin: AdminClient | None = None
    if bootstrap := os.environ.get(KAFKA_BOOTSTRAP_ENV):
        producer = Producer({"bootstrap.servers": bootstrap})
        admin = AdminClient({"bootstrap.servers": bootstrap})
        new_topic = NewTopic(topic, num_partitions=PARTITIONS, replication_factor=1)
        admin.create_topics([new_topic])[topic].result(timeout=TIMEOUT_S)
    else:
        # the mock cluster lives inside this producer, as long as it does
        producer = Producer({"test.mock.num.brokers": "1"})
        broker = producer.list_topics(timeout=TIMEOUT_S).brokers[1]
        bootstrap = f"{broker.host}:{broker.port}"

    # the mock cluster creates the topic on this request
    metadata = producer.list_topics(topic, timeout=TIMEOUT_S).topics[topic]
    assert metadata.error is None, f"topic unusable: {metadata.error}"
    assert len(metadata.partitions) == PARTITIONS, f"{len(metadata.partitions)} partitions"

    yield Kafka(bootstrap, topic, producer)

    if admin is not None:
        admin.delete_topics([topic])[topic].result(timeout=TIMEOUT_S)


class GroupMember:
    """One consumer of the group and what the test observed of it

    It dispatches continuously on its own task, as the pipeline would. Events are only
    acknowledged when the test calls `acknowledge`.
    """

    def __init__(self, connector: ConfluentKafkaInput, monkeypatch: pytest.MonkeyPatch) -> None:
        self.connector = connector
        self.dispatches: list[MessageMeta] = []
        """Every dispatch in order, including repeated ones"""
        self._unacknowledged_events: dict[MessageMeta, LogEvent | ErrorEvent] = {}
        self._revoke_callback = AsyncMock(wraps=connector._revoke_callback)
        self._lost_callback = AsyncMock(wraps=connector._lost_callback)
        monkeypatch.setattr(connector, "_revoke_callback", self._revoke_callback)
        monkeypatch.setattr(connector, "_lost_callback", self._lost_callback)

    @property
    def assigned(self) -> set[int]:
        return set(self.connector._partitions)

    @property
    def dispatched(self) -> set[MessageMeta]:
        return set(self.dispatches)

    @property
    def revoked(self) -> set[int]:
        """Partitions of the latest revocation, empty if there was none"""
        if not self._revoke_callback.called:
            return set()
        return {each.partition for each in self._revoke_callback.call_args.args[1]}

    @property
    def lost(self) -> bool:
        """Whether the partitions were lost, i.e. the member was fenced"""
        return self._lost_callback.called

    async def dispatch(self, stopping: asyncio.Event) -> None:
        while not stopping.is_set():
            event = await self.connector._get_event(0.3)
            if event is not None:
                meta = event.input_meta
                assert isinstance(meta, ConfluentKafkaInputMeta)
                msg = MessageMeta(meta.partition, meta.offset)
                self.dispatches.append(msg)
                self._unacknowledged_events[msg] = event

    async def acknowledge(self, msgs: Iterable[MessageMeta]) -> None:
        """Acknowledge the events of `msgs`, as the pipeline would"""
        events = [self._unacknowledged_events.pop(msg) for msg in msgs]
        await self.connector.acknowledge(events)  # type: ignore[arg-type]  # input_meta is set

    async def acknowledge_all(self) -> None:
        await self.acknowledge(list(self._unacknowledged_events))

    def lowest_unacknowledged(self, messages_per_partition: int) -> set[MessageMeta]:
        """The `messages_per_partition` lowest unacknowledged offsets of each partition"""
        by_partition = groupby(sorted(self._unacknowledged_events), lambda msg: msg.partition)
        return {msg for _, msgs in by_partition for msg in islice(msgs, messages_per_partition)}


class ConsumerGroup:
    """The members of one consumer group and the messages produced for them"""

    def __init__(self, kafka: Kafka, monkeypatch: pytest.MonkeyPatch) -> None:
        self.kafka = kafka
        self.monkeypatch = monkeypatch
        self.group_id = f"group-{uuid.uuid4().hex[:8]}"
        self.members: list[GroupMember] = []
        self.dispatch_tasks: list[asyncio.Task[None]] = []
        self.stopping = asyncio.Event()
        self.produced: set[MessageMeta] = set()

    def produce(self, count: int) -> set[MessageMeta]:
        """Produce `count` messages round robin over all partitions"""
        batch: set[MessageMeta] = set()

        def on_delivery(error: KafkaError | None, msg: Message) -> None:
            assert error is None, f"produce failed: {error}"
            partition, offset = msg.partition(), msg.offset()
            assert partition is not None and offset is not None
            batch.add(MessageMeta(partition, offset))

        for number in range(count):
            self.kafka.producer.produce(
                self.kafka.topic,
                value=json.dumps({"number": number}).encode(),
                partition=number % PARTITIONS,
                on_delivery=on_delivery,
            )
        self.kafka.producer.flush(TIMEOUT_S)
        assert len(batch) == count, f"{len(batch)} of {count} delivered"
        self.produced.update(batch)
        return batch

    async def add_consumer(
        self,
        name: str,
        *,
        kafka_config: dict[str, str] | None = None,
        revoke_drain_timeout: float = 15.0,
        validate: bool = True,
    ) -> GroupMember:
        """Create, instrument and start a consumer that dispatches on its own task

        `revoke_drain_timeout` defaults to well above how long a test holds a drain
        open, so only a drain that never completes runs into it. `validate=False`
        allows configurations the connector rejects, to provoke their failure.
        """
        settings: dict[str, str] = {
            "bootstrap.servers": self.kafka.bootstrap,
            "group.id": self.group_id,
            **(kafka_config or {}),
        }
        with contextlib.nullcontext() if validate else attrs.validators.disabled():
            config = ConfluentKafkaInput.Config(
                type="confluentkafka_input",
                topic=self.kafka.topic,
                kafka_config=settings,
                revoke_drain_timeout=revoke_drain_timeout,
            )
        member = GroupMember(ConfluentKafkaInput(name=name, configuration=config), self.monkeypatch)
        await member.connector.setup()
        self.members.append(member)
        self.dispatch_tasks.append(asyncio.create_task(member.dispatch(self.stopping)))
        return member

    @property
    def dispatched(self) -> set[MessageMeta]:
        """What any member dispatched"""
        return set().union(*(member.dispatched for member in self.members))

    @property
    def duplicates(self) -> set[MessageMeta]:
        """Dispatched more than once, by the same member or by several"""
        counts = Counter(msg for member in self.members for msg in member.dispatches)
        return {msg for msg, count in counts.items() if count > 1}

    async def shut_down(self) -> None:
        self.stopping.set()
        await asyncio.gather(*self.dispatch_tasks, return_exceptions=True)
        # shutting down revokes everything, which drains, which needs acknowledgements
        for member in self.members:
            await member.acknowledge_all()
        for member in self.members:
            await member.connector.shut_down()


@pytest.fixture(name="group")
async def fixture_group(
    kafka: Kafka, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[ConsumerGroup]:
    group = ConsumerGroup(kafka, monkeypatch)
    yield group
    try:
        await asyncio.wait_for(group.shut_down(), 30)
    except TimeoutError:
        pytest.fail("shutdown took more than 30s")


async def test_revocation_waits_for_acknowledgement_before_handover(group: ConsumerGroup) -> None:
    first_batch = group.produce(20 * PARTITIONS)

    c1 = await group.add_consumer("c1")
    assert await until(lambda: c1.assigned == ALL_PARTITIONS)
    assert await until(lambda: c1.dispatched == first_batch)

    # a quarter of each partition
    await c1.acknowledge(c1.lowest_unacknowledged(messages_per_partition=5))

    c2 = await group.add_consumer("c2")

    # rebalancing starts, the revoked partitions wait for their drain
    assert await until(lambda: c1.revoked), "nothing revoked"
    draining_partitions = c1.revoked
    kept_partitions = ALL_PARTITIONS - draining_partitions
    assert draining_partitions and kept_partitions, "partitions not split between consumers"

    # only dispatched after the handover
    second_batch = group.produce(20 * PARTITIONS)

    # health must not block on the consumer, which waits for the drain
    for _ in range(4):
        try:
            healthy = await asyncio.wait_for(c1.connector.health(), 1)
        except TimeoutError:
            pytest.fail("health blocked during the drain")
        assert healthy, "unhealthy during the drain"
        await asyncio.sleep(0.5)

    assert not c2.assigned, "handed over before drained"
    assert c1.assigned == ALL_PARTITIONS, "released before drained"
    assert c1.dispatched == first_batch, "dispatched more during the drain"

    # completes the drain
    await c1.acknowledge_all()

    assert await until(
        lambda: c1.assigned == kept_partitions and c2.assigned == draining_partitions
    ), f"handover incomplete: c1 {c1.assigned}, c2 {c2.assigned}"
    assert await until(
        lambda: group.dispatched == group.produced
    ), f"lost: {group.produced - group.dispatched}"

    assert not group.duplicates, f"dispatched twice: {group.duplicates}"
    assert c2.dispatched == {
        msg for msg in second_batch if msg.partition in draining_partitions
    }, "c2 did not resume at the committed offsets"
    assert {
        msg for msg in second_batch if msg.partition in kept_partitions
    } <= c1.dispatched, "c1 did not continue on the kept partitions"
    for member in group.members:
        assert not member.lost, "fenced"
        assert member.connector.metrics.revoke_drain_timeouts.value == 0, "drain timed out"


@needs_real_broker
async def test_overrunning_the_rebalance_timeout_fences_and_replays(group: ConsumerGroup) -> None:
    produced = group.produce(10 * PARTITIONS)

    # deliberate misconfiguration: draining may take longer than the poll interval
    c1 = await group.add_consumer(
        "c1",
        kafka_config={"max.poll.interval.ms": "10000"},
        revoke_drain_timeout=20.0,
        validate=False,
    )
    assert await until(lambda: c1.assigned == ALL_PARTITIONS)
    assert await until(lambda: c1.dispatched == produced)

    # c1 never acknowledges, so its drain overruns the poll interval
    await group.add_consumer("c2", revoke_drain_timeout=5.0)
    assert await until(lambda: c1.revoked), "nothing revoked"

    assert await until(lambda: c1.lost, seconds=40), "not fenced"
    assert await until(
        lambda: group.duplicates == produced
    ), f"not replayed: {produced - group.duplicates}"
