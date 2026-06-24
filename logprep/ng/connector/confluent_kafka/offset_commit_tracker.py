"""
OffsetCommitTracker
===================

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

logger = logging.getLogger("OffsetCommitTracker")


@define
class _PartitionOffsets:

    committable_offsets: set[int] = field(factory=set, init=False)
    next_expected_offset: int


@define
class OffsetCommitTracker:
    """
    Helper class able to track committed and ready-to-be committed offsets per
    partition in order to commit only those offsets, which have actually
    been processed.
    """

    _topic: str
    _partition_to_offsets: dict[int, _PartitionOffsets] = field(factory=dict)

    def register_partition(self, partition: int, offset: int) -> None:
        """
        Registers a new partition to be tracked alongside with the next expected offset
        (as returned by `Consumer.committed`).
        """
        logger.debug("registered partition %d with offset %d", partition, offset)
        self._partition_to_offsets[partition] = _PartitionOffsets(next_expected_offset=offset)

    def unregister_partition(self, partition: int) -> set[int]:
        """
        Unregisters a previously registered partition from the tracker.
        Non-committed pending offsets are potentially lost through this operation.
        """
        try:
            tracker = self._partition_to_offsets[partition]
        except KeyError:
            logger.warning("unregistering unknown partition %d", partition)
            return set()
        logger.debug(
            "unregistered partition %d with next expected offset %d",
            partition,
            tracker.next_expected_offset,
        )
        if tracker.committable_offsets:
            logger.warning(
                "offsets %s for partition %s were ready to commit and are now lost",
                tracker.committable_offsets,
                partition,
            )
        del self._partition_to_offsets[partition]
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
        A subsequent call to `advance_offsets` assumes that the previously produced
        partitions/offsets were successfully committed.
        """
        for item in new_committable_offsets:
            try:
                tracker = self._partition_to_offsets[item.partition]
            except KeyError:
                logger.warning(
                    "received offset for unregistered partition: offset=%d, partition=%d",
                    item.offset,
                    item.partition,
                )
                continue
            if item.offset < tracker.next_expected_offset:
                logger.warning(
                    "offset %d already committed (<%d)", item.offset, tracker.next_expected_offset
                )
                continue

            tracker.committable_offsets.add(item.offset)

        results: list[TopicPartition] = []

        for partition, tracker in self._partition_to_offsets.items():
            next_offset = tracker.next_expected_offset
            while next_offset in tracker.committable_offsets:
                next_offset += 1

            if next_offset > tracker.next_expected_offset:
                logger.debug(
                    "offsets from %d to %d (#%d) "
                    "for partition %d and topic %s identified for commit",
                    tracker.next_expected_offset,
                    next_offset,
                    next_offset - tracker.next_expected_offset,
                    partition,
                    self._topic,
                )

                tracker.committable_offsets.difference_update(
                    range(tracker.next_expected_offset, next_offset)
                )

                tracker.next_expected_offset = next_offset
                results.append(
                    TopicPartition(
                        self._topic,
                        partition=partition,
                        offset=tracker.next_expected_offset,
                    )
                )

        return results
