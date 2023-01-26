"""
StringSplitter
============

The `string_splitter` processor ...

A speaking example:

..  code-block:: yaml
    :linenos:
    :caption: Given string_splitter rule

    filter: message
    string_splitter:
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


.. autoclass:: logprep.processor.string_splitter.rule.StringSplitterRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

Examples for string_splitter:
------------------------------------------------

.. datatemplate:import-module:: tests.unit.processor.string_splitter.test_string_splitter
   :template: testcase-renderer.tmpl

"""

from attrs import define, field, validators
from logprep.processor.base.rule import Rule

class StringSplitterRule(Rule):
    """..."""

    @define(kw_only=True)
    class Config(Rule.Config):
        """Config for StringSplitterRule"""
        ...