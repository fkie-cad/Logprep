# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
"""Rebalancing against librdkafka's in-process mock cluster.

`test.mock.num.brokers` runs a broker inside the process, so these exercise real
group coordination without docker. A consumer joins while events are dispatched
but not yet acknowledged, and acknowledgement happens out of order, which is the
scenario the drain on revocation exists for.
"""

import asyncio
import json
import random
import time
import uuid

import pytest
from confluent_kafka import Producer

from logprep.ng.connector.confluent_kafka.input import ConfluentKafkaInput

PARTITIONS = 4  # the mock cluster auto creates topics with four partitions
MESSAGES = 40
EXPECTED = {(number % PARTITIONS, number // PARTITIONS) for number in range(MESSAGES)}

STRATEGIES = [
    pytest.param("cooperative-sticky", False, id="cooperative_sticky"),
    pytest.param("range", True, id="range"),
    pytest.param("roundrobin", True, id="roundrobin"),
]


@pytest.fixture(name="bootstrap")
def fixture_bootstrap():
    producer = Producer({"test.mock.num.brokers": "1"})
    broker = producer.list_topics(timeout=10).brokers[1]
    topic = f"rebalance-{uuid.uuid4().hex[:8]}"
    for number in range(MESSAGES):
        producer.produce(
            topic, value=json.dumps({"number": number}).encode(), partition=number % PARTITIONS
        )
    producer.flush(10)
    yield f"{broker.host}:{broker.port}", topic


class Harness:
    """Runs consumers of one group and records what happened to their partitions."""

    def __init__(self, bootstrap, topic, strategy=None):
        self.bootstrap, self.topic, self.strategy = bootstrap, topic, strategy
        self.group = f"group-{uuid.uuid4().hex[:8]}"
        self.consumers: list[ConfluentKafkaInput] = []
        self.tasks: list[asyncio.Task] = []
        self.stop = asyncio.Event()
        self.hold = asyncio.Event()  # freezes acknowledgement while set
        self.handled: list[tuple[int, int]] = []  # a list, so duplicates stay visible
        self.pending: list[tuple[ConfluentKafkaInput, object]] = []
        self.assigned: dict[str, set[int]] = {}
        self.revoked: dict[str, set[int]] = {}
        self.released_undrained: list[tuple[str, int]] = []
        self.inflight_at_revoke: list[int] = []
        self.lost: list[tuple[str, int]] = []

    def _instrument(self, connector):
        """Wrap the callbacks before setup, subscribe binds them at that point."""
        name = connector.name
        self.assigned[name] = set()
        self.revoked[name] = set()
        assign_callback = connector._assign_callback
        revoke_callback = connector._revoke_callback
        lost_callback = connector._lost_callback
        unregister = connector._unregister_partition

        async def recording_assign(consumer, topic_partitions):
            await assign_callback(consumer, topic_partitions)
            self.assigned[name] |= {each.partition for each in topic_partitions}

        async def recording_revoke(consumer, topic_partitions):
            partitions = [each.partition for each in topic_partitions]
            self.revoked[name] |= set(partitions)
            self.inflight_at_revoke.extend(
                partition
                for partition in partitions
                if (state := connector._partitions.get(partition)) and not state.is_drained
            )
            await revoke_callback(consumer, topic_partitions)

        async def recording_lost(consumer, topic_partitions):
            self.lost.extend((name, each.partition) for each in topic_partitions)
            await lost_callback(consumer, topic_partitions)

        def recording_unregister(partition):
            state = connector._partitions.get(partition)
            if state is not None and not state.is_drained:
                self.released_undrained.append((name, partition))
            unregister(partition)

        connector._assign_callback = recording_assign
        connector._revoke_callback = recording_revoke
        connector._lost_callback = recording_lost
        connector._unregister_partition = recording_unregister

    async def add_consumer(self) -> ConfluentKafkaInput:
        kafka_config: dict[str, str] = {
            "bootstrap.servers": self.bootstrap,
            "group.id": self.group,
            "session.timeout.ms": "3000",
            "heartbeat.interval.ms": "1000",
        }
        if self.strategy is not None:
            kafka_config["partition.assignment.strategy"] = self.strategy
        connector = ConfluentKafkaInput(
            name=f"consumer-{len(self.consumers)}",
            configuration=ConfluentKafkaInput.Config(
                type="confluentkafka_input",
                topic=self.topic,
                kafka_config=kafka_config,  # type: ignore[arg-type]
                # long enough that a correctly draining test never needs it,
                # short enough that a stuck drain fails fast instead of hanging
                revoke_drain_timeout=10.0,
            ),
        )
        self._instrument(connector)
        await connector.setup()
        self.consumers.append(connector)
        self.tasks.append(asyncio.create_task(self._dispatch(connector)))
        return connector

    async def _dispatch(self, connector):
        while not self.stop.is_set():
            event = await connector._get_event(0.3)
            if event is not None:
                self.handled.append((event.input_meta.partition, event.input_meta.offset))
                self.pending.append((connector, event))

    async def _acknowledge(self):
        """Acknowledge out of order and in batches, on its own task.

        Has to be independent of the dispatchers: while a revocation drains, the
        dispatcher of that consumer is blocked inside consume(), so acknowledging
        from there would deadlock, exactly as it would in the pipeline.
        """
        while not self.stop.is_set():
            await asyncio.sleep(0.05)
            if not self.pending or self.hold.is_set():
                continue
            await self._drain_pending()

    async def _drain_pending(self):
        batch = self.pending[: random.randint(1, len(self.pending))]
        del self.pending[: len(batch)]
        random.shuffle(batch)
        for connector, event in batch:
            await connector.acknowledge([event])

    async def start(self) -> ConfluentKafkaInput:
        """Start one consumer and wait until it owns the whole topic.

        Starting a single consumer keeps the initial assignment free of races;
        the rebalance under test is triggered by the second consumer joining.
        """
        self.tasks.append(asyncio.create_task(self._acknowledge()))
        first = await self.add_consumer()
        settled = await self.wait_for(lambda: len(self.assigned[first.name]) == PARTITIONS)
        assert settled, f"the first consumer never took the topic, assigned {self.assigned}"
        return first

    async def wait_for(self, predicate, timeout=20) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate():
                return True
            await asyncio.sleep(0.2)
        return False

    async def wait_until_processed(self, timeout=30) -> bool:
        """Wait for every message to be both dispatched and acknowledged.

        Checking only `handled` is not enough: consume() delivers in batches, so
        dispatch can race far ahead of acknowledgement. Stopping as soon as
        `handled` looks complete would abandon whatever is still in `pending`,
        and the drain below would then wait out its timeout for acks that will
        never come.
        """
        return await self.wait_for(
            lambda: set(self.handled) == EXPECTED and not self.pending, timeout
        )

    def kept_by_existing_consumers(self, joined) -> dict[str, set[int]]:
        """Partitions the consumers that were already running still hold.

        Has to be read while the group is running: closing a consumer revokes
        everything it owns, so this is meaningless after shut_down().
        """
        return {
            name: partitions - self.revoked[name]
            for name, partitions in self.assigned.items()
            if name != joined.name
        }

    async def shut_down(self):
        self.stop.set()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        while self.pending:  # safety net, should be empty if the test waited correctly
            await self._drain_pending()
        for connector in self.consumers:
            await connector.shut_down()


@pytest.fixture(name="harness")
async def fixture_harness(bootstrap):
    server, topic = bootstrap
    built: list[Harness] = []

    def make(strategy=None) -> Harness:
        instance = Harness(server, topic, strategy)
        built.append(instance)
        return instance

    yield make
    for instance in built:
        await instance.shut_down()


@pytest.mark.parametrize("strategy, revokes_everything", STRATEGIES)
async def test_rebalance_drains_without_loss_or_duplicates(harness, strategy, revokes_everything):
    group = harness(strategy)
    await group.start()

    # let it get going, then freeze acknowledgement so the rebalance below
    # starts with events dispatched but not yet acknowledged
    assert await group.wait_for(lambda: len(group.handled) >= PARTITIONS)
    group.hold.set()
    assert await group.wait_for(lambda: bool(group.pending))

    joined = await group.add_consumer()
    assert await group.wait_for(
        lambda: bool(group.inflight_at_revoke), timeout=15
    ), "no revocation started while events were in flight, the test proves nothing"
    group.hold.clear()

    assert await group.wait_until_processed(), (
        f"only {len(set(group.handled))} of {MESSAGES} messages were processed, "
        f"{len(group.pending)} still pending"
    )
    kept = group.kept_by_existing_consumers(joined)

    assert set(group.handled) == EXPECTED, "messages were lost"
    assert (
        len(group.handled) == MESSAGES
    ), f"{len(group.handled) - MESSAGES} duplicates, a clean rebalance must not replay"
    assert not group.released_undrained, f"released before draining: {group.released_undrained}"
    assert not group.lost, f"partitions were lost rather than cleanly revoked: {group.lost}"
    for connector in group.consumers:
        assert (
            connector.metrics.revoke_drain_timeouts.value == 0
        ), f"{connector.name} exceeded its drain timeout, the ack should have arrived in time"
        # a direct state check, independent of whether _unregister_partition was even
        # called: released_undrained only catches a bad release, not a missing one
        leaked = group.revoked[connector.name] & connector._partitions.keys()
        assert not leaked, f"{connector.name} still tracks revoked partitions {leaked}"

    if revokes_everything:
        assert not any(kept.values()), f"an eager strategy must revoke everything, kept {kept}"
    else:
        assert any(kept.values()), f"cooperative rebalancing must keep partitions, kept {kept}"


async def test_shipped_default_rebalances_incrementally(harness):
    """Ties DEFAULTS to the behaviour it was chosen for, so a revert to an eager
    strategy cannot pass unnoticed."""
    group = harness(strategy=None)
    await group.start()

    joined = await group.add_consumer()
    assert await group.wait_for(lambda: any(group.revoked.values()), timeout=15)
    kept = group.kept_by_existing_consumers(joined)

    assert any(kept.values()), f"the shipped default must be cooperative, kept {kept}"
