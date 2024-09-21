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


class ReplacerRule(FieldManagerRule):
    """..."""

    # @define(kw_only=True)
    # class Config(Rule.Config):
    #     """Config for ReplacerRule"""
    #     ...
