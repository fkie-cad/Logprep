# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init

import pytest

from logprep.ng.abc.event import InputMeta
from logprep.ng.connector.confluent_kafka.metadata import ConfluentKafkaInputMeta


class TestKafkaInputMetadata:
    def test_inherits_event_metadata(self):
        meta = ConfluentKafkaInputMeta(partition=1, offset=0)
        assert isinstance(meta, InputMeta)

    def test_valid_instantiation(self):
        meta = ConfluentKafkaInputMeta(partition=3, offset=100)
        assert meta.partition == 3
        assert meta.offset == 100

    @pytest.mark.parametrize("invalid_partition", ["0", None, 1.5, [], {}])
    def test_invalid_partition_type_raises(self, invalid_partition):
        with pytest.raises(TypeError):
            ConfluentKafkaInputMeta(partition=invalid_partition, offset=10)

    @pytest.mark.parametrize("invalid_offset", ["0", None, 1.5, [], {}])
    def test_invalid_offset_type_raises(self, invalid_offset):
        with pytest.raises(TypeError):
            ConfluentKafkaInputMeta(partition=1, offset=invalid_offset)

    def test_slots_are_used(self):
        assert hasattr(ConfluentKafkaInputMeta, "__slots__")
