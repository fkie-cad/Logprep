"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

The `key_checker` processor needs a list with at least one element in it.
The Rule contains this list and it also contains a custom field where the processor
can store all missing keys.

..  code-block:: yaml
    :linenos:
    :caption: Given key_checker rule

    filter: testkey
    key_checker:
        source_fields:
            - key1
            - key2
        target_field: "missing_fields"
    description: '...'

..  code-block:: json
    :linenos:
    :caption: Incoming event

    {
        "testkey": "key1_value",
        "_index": "value"
    }

..  code-block:: json
    :linenos:
    :caption: Processed event

    {
        "testkey": "key1_value",
        "_index": "value",
        "missing_fields": "key1","key2"
    }

.. autoclass:: logprep.processor.key_checker.rule.KeyCheckerRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:
"""

import typing

from attrs import define, field, validators

from logprep.processor.base.rule import Rule


class KeyCheckerRule(Rule):
    """key_checker rule"""

    @define(kw_only=True)
    class Config(Rule.Config):
        """key_checker rule config"""

        source_fields: set = field(
            validator=[
                validators.deep_iterable(
                    member_validator=validators.instance_of(str),
                    iterable_validator=validators.instance_of(set),
                ),
                validators.min_len(1),
            ],
            converter=set,
        )
        """List of fields to check for."""

        target_field: str = field(validator=validators.instance_of(str))
        """The field where to write the processed values to. """

        overwrite_target: bool = field(validator=validators.instance_of(bool), default=False)

        merge_with_target: bool = field(validator=validators.instance_of(bool), default=False)

    @property
    def config(self) -> Config:
        return typing.cast(KeyCheckerRule.Config, self._config)

    @property
    def source_fields(self) -> set[str]:
        return self.config.source_fields

    @property
    def target_field(self) -> str:
        return self.config.target_field

    @property
    def overwrite_target(self) -> bool:
        return self.config.overwrite_target

    @property
    def merge_with_target(self) -> bool:
        return self.config.merge_with_target
