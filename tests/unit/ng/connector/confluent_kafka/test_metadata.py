# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init

import pytest

from logprep.ng.abc.event import EventMetadata
from logprep.ng.connector.confluent_kafka.metadata import KafkaInputMetadata


class TestKafkaInputMetadata:
    def test_inherits_event_metadata(self):
        meta = KafkaInputMetadata(partition=1, offset=0)
        assert isinstance(meta, EventMetadata)

    def test_valid_instantiation(self):
        meta = KafkaInputMetadata(partition=3, offset=100)
        assert meta.partition == 3
        assert meta.offset == 100

    @pytest.mark.parametrize("invalid_partition", ["0", None, 1.5, [], {}])
    def test_invalid_partition_type_raises(self, invalid_partition):
        with pytest.raises(TypeError):
            KafkaInputMetadata(partition=invalid_partition, offset=10)

    @pytest.mark.parametrize("invalid_offset", ["0", None, 1.5, [], {}])
    def test_invalid_offset_type_raises(self, invalid_offset):
        with pytest.raises(TypeError):
            KafkaInputMetadata(partition=1, offset=invalid_offset)

    def test_slots_are_used(self):
        assert hasattr(KafkaInputMetadata, "__slots__")

    def test_accessing_unknown_attribute_raises(self):
        meta = KafkaInputMetadata(partition=1, offset=2)
        with pytest.raises(AttributeError):
            getattr(meta, "topic")
