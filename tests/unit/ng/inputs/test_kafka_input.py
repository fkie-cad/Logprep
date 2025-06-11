# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init

import pytest
from attr import asdict

from logprep.ng.abc.event import EventMetadata
from logprep.ng.inputs.kafka_input import KafkaInputMetadata


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

    def test_repr_contains_classname(self):
        meta = KafkaInputMetadata(partition=1, offset=1)
        assert "KafkaInputMetadata" in repr(meta)

    def test_equality_works(self):
        a = KafkaInputMetadata(partition=1, offset=10)
        b = KafkaInputMetadata(partition=1, offset=10)
        assert a == b

    def test_fields_are_accessible(self):
        meta = KafkaInputMetadata(partition=5, offset=123)
        assert meta.partition == 5
        assert meta.offset == 123

    def test_slots_are_used(self):
        assert hasattr(KafkaInputMetadata, "__slots__")

    def test_asdict_conversion(self):
        meta = KafkaInputMetadata(partition=5, offset=10)
        meta_dict = asdict(meta)
        assert meta_dict == {"partition": 5, "offset": 10}

    def test_accessing_unknown_attribute_raises(self):
        meta = KafkaInputMetadata(partition=1, offset=2)
        with pytest.raises(AttributeError):
            _ = meta.topic

    def test_creating_with_unknown_attribute_raises(self):
        with pytest.raises(TypeError) as exc_info:
            KafkaInputMetadata(partition=1, offset=2, topic="not allowed")
        assert "unexpected keyword argument" in str(exc_info.value)
