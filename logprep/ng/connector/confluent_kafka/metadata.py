"""kafka input classes and logic"""

from attrs import define, field, validators

from logprep.ng.abc.event import InputMeta


@define(kw_only=True)
class ConfluentKafkaInputMeta(InputMeta):
    """Concrete InputMeta holding Kafka input metadata."""

    partition: int = field(validator=validators.instance_of(int))
    offset: int = field(validator=validators.instance_of(int))
