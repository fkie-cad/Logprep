"""kafka input classes and logic"""

from attrs import define, field, validators

from logprep.ng.abc.event import EventMetadata


@define(kw_only=True)
class ConfluentKafkaMetadata(EventMetadata):
    """Concrete EventMetadata holding Kafka input metadata."""

    partition: int = field(validator=validators.instance_of(int))
    offset: int = field(validator=validators.instance_of(int))
