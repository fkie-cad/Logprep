"""
Common
======

Configuration properties shared between input types.

.. autoclass:: logprep.util.input_common.PreprocessingConfig
   :no-index-entry:
   :members:
   :undoc-members:
   :inherited-members:

.. autoclass:: logprep.util.input_common.FullEventConfig
   :no-index-entry:
   :members:
   :undoc-members:
   :inherited-members:

.. autoclass:: logprep.util.input_common.TimeDeltaConfig
   :no-index-entry:
   :members:
   :undoc-members:
   :inherited-members:

.. autoclass:: logprep.util.input_common.HmacConfig
   :no-index-entry:
   :members:
   :undoc-members:
   :inherited-members:
"""

from attrs import define, field, validators

from logprep.util.converters import convert_from_dict


@define(kw_only=True)
class HmacConfig:
    """Configuration property for automatically attaching HMACs to incoming messages."""

    target: str = field(validator=validators.instance_of(str))
    """Defines a field inside the log message which should be used for the hmac
    calculation. If the target field is not found or does not exists an error message
    is written into the configured output field. If the hmac should be calculated on
    the full incoming raw message instead of a subfield the target option should be set to
    :code:`<RAW_MSG>`."""

    key: str = field(validator=validators.instance_of(str))
    """The secret key that will be used to calculate the hmac."""

    output_field: str = field(validator=validators.instance_of(str))
    """The parent name of the field where the hmac result should be written to in the
    original incoming log message. As subfields the result will have a field called :code:`hmac`,
    containing the calculated hmac, and :code:`compressed_base64`, containing the original message
    that was used to calculate the hmac in compressed and base64 encoded. In case the output
    field exists already in the original message an error is raised."""

    def all_set(self) -> bool:
        """
        Checks whether all essential attributes are set.
        """
        return all(map(bool, [self.target, self.key, self.output_field]))


@define(kw_only=True)
class TimeDeltaConfig:
    """
    This preprocessor calculates the difference between the arrival time of logs in Logprep
    and their generation timestamp, which is then added to every incoming log message.
    """

    target_field: str = field(validator=(validators.instance_of(str), lambda _, __, x: bool(x)))
    """
    Defines the fieldname to which the time difference should be written to.
    """

    reference_field: str = field(validator=(validators.instance_of(str), lambda _, __, x: bool(x)))
    """
    Defines a field with a timestamp that should be used for the time difference.
    The calculation will be the arrival time minus the time of this reference field.
    """


@define(kw_only=True)
class FullEventConfig:
    """
    To use this preprocessor the fields :code:`format` and :code:`target_field` have to bet set.
    When the format :code:`str` is set the event is automatically escaped.
    This can be used to identify and resolve mapping errors raised by opensearch.
    """

    format: str = field(validator=validators.in_(["dict", "str"]), default="str")
    """
    Specifies the format which the event is written in.
    The default format ist :code:`str` which leads to automatic json escaping of the given event.
    Also possible is the value :code:`dict` which copies the event as mapping to the specified
    :code:`target_field`.
    If the format :code:`str` is set it is necessary to have a timestamp set in the event
    for opensearch to receive the event in the string format.
    This can be achived by using the :code:`log_arrival_time_target_field` preprocessor.
    """

    target_field: str = field(validator=validators.instance_of(str), default="event.original")
    """
    Specifies the field to which the event should be written to.
    The default is :code:`event.original`.
    """

    clear_event: bool = field(validator=validators.instance_of(bool), default=True)
    """
    Specifies if the singular field should be the only field or appended.
    The default is :code: `True`.
    """


@define(kw_only=True)
class PreprocessingConfig:
    """
    Different configuration options for event preprocessing, available in all
    input classes.
    """

    version_info_target_field: str = field(default="")
    """
    If required it is possible to automatically add the logprep version
    and the used configuration version to every incoming log message.
    This helps to keep track of the processing of the events
    when the configuration is changed often.
    To enable adding the versions to each event this field needs to be configured.
    It defines the name of the dotted parent field under which the version info should be given.
    If not set or empty, no version information is added to the event.
    """

    hmac: HmacConfig = field(
        factory=lambda: HmacConfig(target="", key="", output_field=""),
        converter=lambda d: convert_from_dict(HmacConfig, d),
    )
    """
    If required it is possible to automatically attach an HMAC to incoming log messages.
    To activate this preprocessor, the properties of this object need to be configured.
    This field is completely optional and can also be omitted if no HMAC is needed.
    See :class:`.HmacConfig` for further details.
    """

    log_arrival_time_target_field: str = field(default="")
    """
    It is possible to automatically add the arrival time in Logprep to every incoming log message.
    To enable adding the versions to each event this field needs to be configured.
    It defines the name of the dotted field in which the arrival times should be stored.
    If not set or empty, no version information is added to the event.
    """

    log_arrival_timedelta: TimeDeltaConfig | None = field(
        default=None,
        converter=lambda d: convert_from_dict(TimeDeltaConfig, d),
    )
    """
    It is possible to automatically calculate the difference between the arrival time of logs
    in Logprep and their generation timestamp, which is then added to every incoming log message.
    This feature is optional and can be enabled by setting the properties of this object.
    See :class:`.TimeDeltaConfig` for further details.
    """

    enrich_by_env_variables: dict[str, str] = field(factory=dict)
    """
    If required it is possible to automatically enrich incoming events by environment variables.
    To activate this preprocessor the fields value has to be a mapping
    from the dotted target field name (key) to the environment variable name (value).
    """

    add_full_event_to_target_field: FullEventConfig | None = field(
        default=None,
        converter=lambda d: convert_from_dict(FullEventConfig, d),
    )
    """
    If required it is possible to automatically copy all event fields
    to one singular field or subfield.
    This feature is optional and can be enabled by setting the properties of this object.
    See :class:`.FullEventConfig` for further details.
    """
