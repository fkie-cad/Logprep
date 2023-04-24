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
from zoneinfo import ZoneInfo

from attrs import define, field, validators

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
        source_format: str = field(validator=validators.instance_of(str), default="ISO8601")
        """The source format if source_fields is not an iso8601 complient time format string
        the format string could be given in the syntax of the :code:`arrow` library 
        (see: https://arrow.readthedocs.io/en/latest/guide.html#supported-tokens)
        or in the format of the python builtin :code:`datetime.strptime`
        (see: https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes).
        Additionally, the value :code:`ISO8601` (default)  and :code:`UNIX` can be used for
        the source_formats field. The former can be used if the timestamp already exists
        in the ISO8601 format, such that only a timezone conversion should be applied.
        And the latter can be used if the timestamp is given in the UNIX Epoch Time.
        This supports the Unix timestamps in seconds and milliseconds
        """
        source_timezone: ZoneInfo = field(
            validator=[validators.instance_of(ZoneInfo)], converter=ZoneInfo, default="UTC"
        )
        """ timezone of source_fields. defaults to :code:`UTC`"""
        target_timezone: ZoneInfo = field(
            validator=[validators.instance_of(ZoneInfo)], converter=ZoneInfo, default="UTC"
        )
        """ timezone for target_field. defaults to :code:`UTC`"""

    @property
    def source_format(self):
        """returns the source format"""
        return self._config.source_format

    @property
    def target_timezone(self):
        """returns the target timezone"""
        return self._config.target_timezone

    @property
    def source_timezone(self):
        """returns the source timezone"""
        return self._config.source_timezone
