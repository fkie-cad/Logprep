r"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

A speaking example:

..  code-block:: yaml
    :linenos:
    :caption: Given deduplicator rule

    filter: field_1 AND field_2
    deduplicator:
        fields:
            - field_1
    description: '...'

..  code-block:: json
    :linenos:
    :caption: Incoming event

    {"field_1": ["foo", "bar", "bar"], "field_2": ["baz", "baz", "qux"]}

..  code-block:: json
    :linenos:
    :caption: Processed event

    {"field_1": ["foo", "bar"], "field_2": ["baz", "baz", "qux"]}

.. autoclass:: logprep.processor.deduplicator.rule.DeduplicatorRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

Examples for deduplication:
------------------------------------------------

.. datatemplate:import-module:: tests.unit.processor.deduplicator.test_deduplicator
   :template: testcase-renderer.tmpl

"""

from typing import cast

from attrs import define, field

from logprep.processor.field_manager.rule import FieldManagerRule


class DeduplicatorRule(FieldManagerRule):
    """Deduplicator rule"""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Config for Deduplicator"""

        fields: list = field(factory=list, repr=False, eq=False)
        """The fields whose values should be deduplicated."""

    @property
    def fields(self):  # pylint: disable=missing-docstring
        return cast(DeduplicatorRule.Config, self._config).fields
