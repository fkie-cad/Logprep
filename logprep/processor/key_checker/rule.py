"""
KeyCheckerRule
------------

The `key_checker` processor needs a list with at least one element in it.
The Rule contains this list and it also contains a custom field where the processor
can store all missing keys.

..  code-block:: yaml
    :linenos:
    :caption: Given key_checker rule

    filter: *
    key_checker: {
            key_list: [
                "key1",
                "key2",
            ],
            output_field: "missing_fields"
        },
    description: '...'

..  code-block:: json
    :linenos:
    :caption: Incoming event

    {
        testkey: "key1_value",
        _index: "value",
    }

..  code-block:: json
    :linenos:
    :caption: Processed event

    {
        testkey: "key1_value",
        _index: "value",
        missing_fields: "key1","key2"
    }
"""

from functools import partial

from attrs import define, field, validators

from logprep.processor.base.rule import Rule


from logprep.util.validators import min_len_validator


class KeyCheckerRule(Rule):
    """key_checker rule"""

    @define(kw_only=True)
    class Config(Rule.Config):
        """key_checker rule config"""

        key_list: set = field(
            validator=[
                validators.deep_iterable(
                    member_validator=validators.instance_of(str),
                    iterable_validator=validators.instance_of(set),
                ),
                partial(min_len_validator, min_length=1),
            ],
            converter=set,
        )

        output_field: str = field(validator=validators.instance_of(str))

    @property
    def key_list(self) -> list:  # pylint: disable=missing-docstring
        return self._config.key_list

    @property
    def output_field(self) -> str:  # pylint: disable=missing-docstring
        return self._config.output_field
