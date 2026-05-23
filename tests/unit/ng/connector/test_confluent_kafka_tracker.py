# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access


import pytest
from confluent_kafka import TopicPartition

from logprep.ng.connector.confluent_kafka.metadata import ConfluentKafkaMetadata as InputMeta
from logprep.ng.connector.confluent_kafka.offset_commit_tracker import (
    TopicOffsetCommitTracker as Tracker,
)


class TestKafkaInputTopicOffsetCommitTracker:

    @pytest.fixture
    def tracker(self) -> Tracker:
        return Tracker(topic="consumer")

    def test_register_partition(self, tracker: Tracker) -> None:
        tracker.register_partition(partition=0, offset=100)
        assert 0 in tracker._partition_to_tracker
        assert tracker._partition_to_tracker[0].last_committed_offset == 100
        assert tracker._partition_to_tracker[0].committable_offsets == set()

    def test_single_offset_commit(self, tracker: Tracker) -> None:
        tracker.register_partition(partition=0, offset=100)
        result = tracker.advance_offsets([InputMeta(partition=0, offset=100)])

        assert len(result) == 1
        assert result[0] == TopicPartition("consumer", partition=0, offset=101)
        assert tracker._partition_to_tracker[0].last_committed_offset == 101
        assert tracker._partition_to_tracker[0].committable_offsets == set()

    def test_contiguous_offsets_commit(self, tracker: Tracker) -> None:
        tracker.register_partition(partition=0, offset=100)
        offsets = [InputMeta(partition=0, offset=i) for i in [100, 101, 102]]
        result = tracker.advance_offsets(offsets)

        assert len(result) == 1
        assert result[0] == TopicPartition("consumer", partition=0, offset=103)
        assert tracker._partition_to_tracker[0].last_committed_offset == 103
        assert tracker._partition_to_tracker[0].committable_offsets == set()

    def test_out_of_order_contiguous_offsets(self, tracker: Tracker) -> None:
        tracker.register_partition(partition=0, offset=100)
        offsets = [InputMeta(partition=0, offset=i) for i in [102, 100, 101]]
        result = tracker.advance_offsets(offsets)

        assert len(result) == 1
        assert result[0] == TopicPartition("consumer", partition=0, offset=103)
        assert tracker._partition_to_tracker[0].committable_offsets == set()

    def test_gap_filled_later(self, tracker) -> None:
        tracker.register_partition(partition=0, offset=100)
        tracker.advance_offsets(
            [
                InputMeta(partition=0, offset=100),
                # gap at 101
                InputMeta(partition=0, offset=102),
            ]
        )
        assert tracker._partition_to_tracker[0].committable_offsets == {102}

        result = tracker.advance_offsets([InputMeta(partition=0, offset=101)])
        assert len(result) == 1
        assert result[0] == TopicPartition("consumer", partition=0, offset=103)
        assert tracker._partition_to_tracker[0].committable_offsets == set()

    def test_multiple_partitions(self, tracker: Tracker) -> None:
        tracker.register_partition(partition=0, offset=100)
        tracker.register_partition(partition=1, offset=200)

        offsets = [
            InputMeta(partition=0, offset=100),
            InputMeta(partition=0, offset=101),
            InputMeta(partition=1, offset=200),
        ]
        result = tracker.advance_offsets(offsets)

        assert len(result) == 2
        assert TopicPartition("consumer", partition=0, offset=102) in result
        assert TopicPartition("consumer", partition=1, offset=101) in result
        assert TopicPartition("consumer", partition=1, offset=201) in result

    def test_offset_zero(self, tracker: Tracker) -> None:
        tracker.register_partition(partition=0, offset=0)
        result = tracker.advance_offsets([InputMeta(partition=0, offset=0)])

        assert len(result) == 1
        assert result[0] == TopicPartition("consumer", partition=0, offset=1)

    def test_unregister_no_pending_offsets(self, tracker: Tracker) -> None:
        tracker.register_partition(partition=0, offset=100)
        tracker.advance_offsets([InputMeta(partition=0, offset=100)])
        lost = tracker.unregister_partition(partition=0)
        assert lost == set()

    def test_unregister_with_pending_offsets(self, tracker: Tracker, caplog) -> None:
        tracker.register_partition(partition=0, offset=100)
        tracker.advance_offsets(
            [InputMeta(partition=0, offset=101)]
        )  # not contiguous (100 missing)
        lost = tracker.unregister_partition(partition=0)
        assert lost == {101}
        assert "offsets {101} for partition 0 were ready to commit and are now lost" in caplog.text

    def test_sequential_advance_calls(self, tracker: Tracker) -> None:
        tracker.register_partition(partition=0, offset=100)

        result1 = tracker.advance_offsets([InputMeta(partition=0, offset=100)])
        assert result1 == [TopicPartition("consumer", partition=0, offset=101)]

        # Second call: offset 102
        result2 = tracker.advance_offsets([InputMeta(partition=0, offset=101)])
        assert result2 == [TopicPartition("consumer", partition=0, offset=102)]

    def test_idempotent_calls(self, tracker: Tracker) -> None:
        tracker.register_partition(partition=0, offset=100)
        offsets = [InputMeta(partition=0, offset=100), InputMeta(partition=0, offset=101)]
        result1 = tracker.advance_offsets(offsets)
        result2 = tracker.advance_offsets(offsets)
        assert result1 == [TopicPartition("consumer", partition=0, offset=102)]
        assert result2 == []

    def test_many_offsets(self, tracker: Tracker) -> None:
        tracker.register_partition(partition=0, offset=0)
        offsets = [InputMeta(partition=0, offset=i) for i in range(0, 10_000)]
        result = tracker.advance_offsets(offsets)

        assert len(result) == 1
        assert result[0] == TopicPartition("consumer", 0, 10_000)
        assert len(tracker._partition_to_tracker[0].committable_offsets) == 0

    def test_mixed_contiguous_non_contiguous(self, tracker: Tracker) -> None:
        tracker.register_partition(partition=0, offset=100)
        # Contiguous: 100-102, Non-contiguous: 104, 106
        offsets = [InputMeta(partition=0, offset=i) for i in [100, 101, 104, 102, 106]]
        result = tracker.advance_offsets(offsets)

        assert len(result) == 1
        assert result[0] == TopicPartition("consumer", partition=0, offset=103)
        assert tracker._partition_to_tracker[0].committable_offsets == {104, 106}
