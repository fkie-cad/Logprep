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

from attrs import define, field, validators

from logprep.processor.field_manager.rule import FieldManagerRule


class KeyCheckerRule(FieldManagerRule):
    """key_checker rule"""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
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
        mapping: dict = field(default="", init=False, repr=False, eq=False)
        ignore_missing_fields: bool = field(default=False, init=False, repr=False, eq=False)
