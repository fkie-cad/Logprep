"""
Replacer
============

A speaking example:

..  code-block:: yaml
    :linenos:
    :caption: Given replacer rule

    filter: message
    replacer:
        ...
    description: '...'

..  code-block:: json
    :linenos:
    :caption: Incoming event

    <INCOMMING_EVENT>

..  code-block:: json
    :linenos:
    :caption: Processed event

    <PROCESSED_EVENT>


.. autoclass:: logprep.processor.replacer.rule.ReplacerRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

Examples for replacer:
------------------------------------------------

.. datatemplate:import-module:: tests.unit.processor.replacer.test_replacer
   :template: testcase-renderer.tmpl

"""

from attrs import define, field, validators

from logprep.processor.field_manager.rule import FieldManagerRule

REPLACEMENT_PATTERN = r".*%{.+}.*"


class ReplacerRule(FieldManagerRule):
    """..."""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Config for ReplacerRule"""

        source_fields: list = field(init=False, factory=list, eq=False)
        target_field: list = field(init=False, default="", eq=False)
        mapping: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.min_len(1),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.matches_re(REPLACEMENT_PATTERN),
                ),
            ]
        )
        """A mapping of fieldnames to patterns to replace"""
