"""
Timestamper
============

The `timestamper` processor ...

A speaking example:

..  code-block:: yaml
    :linenos:
    :caption: Given timestamper rule

    filter: message
    timestamper:
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


.. autoclass:: logprep.processor.timestamper.rule.TimestamperRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

Examples for timestamper:
------------------------------------------------

.. datatemplate:import-module:: tests.unit.processor.timestamper.test_timestamper
   :template: testcase-renderer.tmpl

"""

from attrs import define, field, validators

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.field_manager.rule import FieldManagerRule


class TimestamperRule(FieldManagerRule):
    """Timestamper Rule"""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Config for TimestamperRule"""

        source_fields: list = field(
            validator=[
                validators.instance_of(list),
                validators.min_len(1),
                validators.max_len(1),
                validators.deep_iterable(member_validator=validators.instance_of(str)),
            ]
        )
        """The field from where to get the time from as list with one element"""
        target_field: str = field(validator=validators.instance_of(str), default="@timestamp")
        """The field where to write the processed values to, defaults to :code:`@timestamp`"""
        source_format: str = field(validator=validators.instance_of(str), default="")
        """The source format if source_fields is not an iso8601 complient time format string"""

    @property
    def source_format(self):
        """the arrow style source format"""
        return self._config.source_format
