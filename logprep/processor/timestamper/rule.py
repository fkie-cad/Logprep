"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

A speaking example:

..  code-block:: yaml
    :linenos:
    :caption: Given timestamper rule

    filter: "winlog.event_id: 123456789"
    timestamper: 
        source_fields: ["winlog.event_data.some_timestamp_utc"]
        target_field: "@timestamp"
        source_format: UNIX
        source_timezone: UTC
        target_timezone: Europe/Berlin
    description: example timestamper rule

..  code-block:: json
    :linenos:
    :caption: Incoming event

        {
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_utc": "1642160449"},
            }
        }

..  code-block:: json
    :linenos:
    :caption: Processed event

        {
            "@timestamp": "2022-01-14T12:40:49+01:00",
            "winlog": {
                "api": "wineventlog",
                "event_id": 123456789,
                "event_data": {"some_timestamp_utc": "1642160449"},
            },
        }


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
        source_format: list = field(
            validator=validators.deep_iterable(
                member_validator=validators.instance_of(str),
                iterable_validator=validators.instance_of(list),
            ),
            default=["ISO8601"],
            converter=lambda x: x if isinstance(x, list) else [x],
        )
        """A list of possible source formats if source_fields is not an iso8601 compliant
        time format string the format must be given in the syntax of the
        python builtin :code:`datetime.strptime`
        (see: https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes).
        Additionally, the value :code:`ISO8601` (default)  and :code:`UNIX` can be used in the list
        of the source_formats field. The former can be used if the timestamp already exists
        in the ISO8601 format, such that only a timezone conversion should be applied.
        And the latter can be used if the timestamp is given in the UNIX Epoch Time.
        This supports the Unix timestamps in seconds and milliseconds.
        Be aware that :code:`UNIX` and :code:`ISO8601` formats do not validate the completeness of
        input string. If you want to ensure, the completeness of the input string, you have to use
        the :code:`datetime.strptime` syntax.

        For example, the following time formats are valid :code:`ISO8601` formats:

        - :code:`hh:mm`
        - :code:`hh:mm:ss`
        - :code:`hh:mm:ss.sss`
        - :code:`hhmmss.ssssss`
        - :code:`hhmm`
        - :code:`hhmmss`

        The output string will always be in this format: :code:`2000-12-31T22:59:59Z`.
        As you can see the output string has a time with seconds.
        If the input string does not have a time or the time does not have seconds,
        the output string will have seconds or times set to zero.

        If you don't want this behavior, you have to use the :code:`datetime.strptime` syntax.
        With this syntax, the :code:`timestamper`errors out with a :code:`TimeParserException` and
        a tag :code:`_timestamper_failure` will be added to the event.
        """
        source_timezone: ZoneInfo = field(
            validator=[validators.instance_of(ZoneInfo)], converter=ZoneInfo, default="UTC"
        )
        """ timezone of source_fields. defaults to :code:`UTC`"""
        target_timezone: ZoneInfo = field(
            validator=[validators.instance_of(ZoneInfo)], converter=ZoneInfo, default="UTC"
        )
        """ timezone for target_field. defaults to :code:`UTC`"""
        mapping: dict = field(default="", init=False, repr=False, eq=False)
        ignore_missing_fields: bool = field(default=False, init=False, repr=False, eq=False)

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
