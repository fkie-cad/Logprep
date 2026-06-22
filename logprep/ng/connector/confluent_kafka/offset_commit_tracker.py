"""
TopicCommitTracker
==================

Helper class able to track committed and ready-to-be committed offsets per
partition in order to commit only those offsets, which have actually
been processed.

"""

import logging
from collections.abc import Iterable, Sequence

from attrs import define, field
from confluent_kafka import (
    TopicPartition,
)

from logprep.ng.connector.confluent_kafka.metadata import ConfluentKafkaInputMeta

logger = logging.getLogger("KafkaOffsetTracker")


@define
class _PartitionOffsets:

    committable_offsets: set[int] = field(factory=set, init=False)
    last_committed_offset: int


@define(frozen=True)
class TopicOffsetCommitTracker:
    """
    Helper class able to track committed and ready-to-be committed offsets per
    partition in order to commit only those offsets, which have actually
    been processed.
    """

    _topic: str
    _partition_to_tracker: dict[int, _PartitionOffsets] = field(factory=dict)

    def register_partition(self, partition: int, offset: int) -> None:
        """
        Registers a new partition to be tracked alongside with the offset of the
        last comitted message (as returned by `Consumer.committed` and +1 by convention).
        """
        logger.debug("registerered partition %d with offset %d", partition, offset)
        self._partition_to_tracker[partition] = _PartitionOffsets(last_committed_offset=offset)

    def unregister_partition(self, partition: int) -> set[int]:
        """
        Unregisters a previously registered partition from the tracker.
        Non-committed pending offsets are potentially lost through this operation.
        """
        tracker = self._partition_to_tracker[partition]
        logger.debug(
            "unregistered partition %d with last committed offset %d",
            partition,
            tracker.last_committed_offset,
        )
        if tracker.committable_offsets:
            logger.warning(
                "offsets %s for partition %s were ready to commit and are now lost",
                tracker.committable_offsets,
                partition,
            )
        del self._partition_to_tracker[partition]
        return tracker.committable_offsets

    def advance_offsets(
        self, new_committable_offsets: Iterable[ConfluentKafkaInputMeta]
    ) -> Sequence[TopicPartition]:
        """
        Feeds partitions/offsets (`ConfluentKafkaInputMeta`) to the tracker
        which are ready to be committed.
        The tracker incorporates the new data into its state, identifies the
        maximum offset ready for commit per partition (leaving no gaps) and
        returns these partitions/offsets (`TopicPartition`).
        A subsequent call to `advance_offsets` assumes that the priorly produced
        partitions/offsets were successfully committed.
        """
        for item in new_committable_offsets:
            tracker = self._partition_to_tracker[item.partition]
            if item.offset < tracker.last_committed_offset:
                logger.warning(
                    "offset %d already committed (<%d)", item.offset, tracker.last_committed_offset
                )
            try:
                tracker.committable_offsets.add(item.offset)
            except KeyError:
                logger.warning(
                    "received offset for unregistered partition: offset=%d, partition=%d",
                    item.offset,
                    item.partition,
                )

        results: list[TopicPartition] = []

        for partition, tracker in self._partition_to_tracker.items():
            next_offset = tracker.last_committed_offset
            while next_offset in tracker.committable_offsets:
                next_offset += 1

            if next_offset > tracker.last_committed_offset:
                logger.debug(
                    "offsets from %d to %d (#%d) "
                    "for partition %d and topic %s identified for commit",
                    tracker.last_committed_offset,
                    next_offset,
                    next_offset - tracker.last_committed_offset,
                    partition,
                    self._topic,
                )

                tracker.committable_offsets.difference_update(
                    range(tracker.last_committed_offset, next_offset)
                )

                tracker.last_committed_offset = next_offset
                results.append(
                    TopicPartition(
                        self._topic,
                        partition=partition,
                        offset=tracker.last_committed_offset,
                    )
                )

        return results
