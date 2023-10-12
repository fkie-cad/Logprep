"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

A speaking example:

..  code-block:: yaml
    :linenos:
    :caption: Given string_splitter rule

    filter: message
    string_splitter:
        source_fields: ["message"]
        target_field: result
    description: '...'

..  code-block:: json
    :linenos:
    :caption: Incoming event

    {"message": "this is the message"}

..  code-block:: json
    :linenos:
    :caption: Processed event

    {"message": "this is the message", "result": ["this", "is", "the", "message"]}


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

from logprep.processor.field_manager.rule import FieldManagerRule


class StringSplitterRule(FieldManagerRule):
    """..."""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Config for StringSplitterRule"""

        delimeter: str = field(validator=validators.instance_of(str), default=" ")
        """The delimeter for splitting. Defaults to whitespace"""
        mapping: dict = field(default="", init=False, repr=False, eq=False)
        ignore_missing_fields: bool = field(default=False, init=False, repr=False, eq=False)

    @property
    def delimeter(self):
        """returns the configured delimeter"""
        return self._config.delimeter
