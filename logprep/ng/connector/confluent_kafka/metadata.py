"""kafka input classes and logic"""

import attrs

from logprep.ng.abc.event import EventMetadata


@attrs.define(slots=True, kw_only=True)
class KafkaInputMetadata(EventMetadata):
    """Concrete EventMetadata holding Kafka input metadata."""

    partition: int = attrs.field(validator=attrs.validators.instance_of(int))
    offset: int = attrs.field(validator=attrs.validators.instance_of(int))
