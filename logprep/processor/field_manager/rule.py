from functools import partial
from attrs import define, field, validators
from logprep.util.validators import min_len_validator
from logprep.processor.base.rule import Rule


class FieldManagerRule(Rule):
    """Interface for a simple Rule with source_fields and target_field"""

    @define(kw_only=True)
    class Config(Rule.Config):
        """Config for SimpleSourceTargetRule"""

        source_fields: list = field(
            validator=[
                validators.instance_of(list),
                validators.deep_iterable(member_validator=validators.instance_of(str)),
                partial(min_len_validator, min_length=1),
            ]
        )
        """The fields from where to get the values which should be processed"""
        target_field: str = field(validator=validators.instance_of(str))
        """The field where to write the processed values to"""
        delete_source_fields: str = field(validator=validators.instance_of(bool), default=False)
        """Whether to delete all the source fields or not. Defaults to :code:`False`"""
        overwrite_target: str = field(validator=validators.instance_of(bool), default=False)
        """Overwrite the target field value if exists. Defaults to :code:`False`"""
        extend_target_list: bool = field(validator=validators.instance_of(bool), default=False)
        """If the target field exists and is a list, the list will be extended with the value
        of the source fields. If the source field is a list, the lists will be merged.
        If the target field does not exist, a new field will be added with the
        source field value as list. Defaults to :code:`False`
        """

    # pylint: disable=missing-function-docstring
    @property
    def delete_source_fields(self):
        if hasattr(self, "_config"):
            return self._config.delete_source_fields
        return False

    @property
    def source_fields(self):
        if hasattr(self, "_config"):
            return self._config.source_fields
        return []

    @property
    def target_field(self):
        return self._config.target_field

    @property
    def overwrite_target(self):
        return self._config.overwrite_target

    @property
    def extend_target_list(self):
        return self._config.extend_target_list

    # pylint: enable=missing-function-docstring
