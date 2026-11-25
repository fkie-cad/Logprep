# pylint: disable=line-too-long  # long lines are part of the rendered JSON examples
"""
Decoder
============

With the :code:`decoder` processor you are able to parse fields from
different formats.

A speaking example:

..  code-block:: yaml
    :linenos:
    :caption: Given decoder rule

    filter: message
    decoder:
        source_format: json
        mapping:
            message: parsed
    description: 'parse message field to the field called parsed'

..  code-block:: json
    :linenos:
    :caption: Incoming event

    {
        "message": "{\\"timestamp\\": \\"2019-08-02T09:46:18.625Z\\", \\"log\\": \\"user login failed\\"}"
    }

..  code-block:: json
    :linenos:
    :caption: Processed event

    {
        "message": "{\\"timestamp\\": \\"2019-08-02T09:46:18.625Z\\", \\"log\\": \\"user login failed\\"}",
        "parsed": {
            "timestamp": "2019-08-02T09:46:18.625Z",
            "log": "user login failed"
        }
    }

For :code:`windows_event_log`, the :code:`xmlfields` option can change default
fields and add fields from any XML section. It is a dict whose keys are the
target field names:

..  code-block:: yaml
    :linenos:
    :caption: Custom XML fields

    filter: message
    decoder:
        source_format: windows_event_log
        mapping:
            message: parsed
        xmlfields:
            EventID:
                convert: str
            SourceName:
                attribute: Guid
            User:
                element: Data
                section: EventData
                name: TargetUserName

The default fields are always extracted and the entries of :code:`xmlfields`
are merged into them. A target that matches a default field inherits all
properties that are not given (for example :code:`EventID` keeps its element
and only changes :code:`convert`). New targets like :code:`User` need an
:code:`element` and are added to the result. Because overrides are applied
last, they replace default or event data fields with the same name.


.. autoclass:: logprep.processor.decoder.rule.DecoderRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

Examples for decoder:
---------------------

.. datatemplate:import-module:: tests.unit.processor.decoder.test_decoder
   :template: testcase-renderer.tmpl

"""

import typing
from typing import Callable, Literal

from attrs import define, field, validators

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.decoder.decoders.registry import DECODERS, get_decoder
from logprep.processor.decoder.decoders.windows_event_log import (
    DEFAULT_XMLFIELD_TARGETS,
    DEFAULT_XMLFIELDS,
    XmlFieldSpec,
    to_int_or_str,
    to_iso8601,
)
from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.util.helper import FieldValue

IMPLEMENTED_DECODERS = tuple(DECODERS.keys())

XmlFieldConvert = Literal["str", "int", "timestamp"]


@define(frozen=True, kw_only=True)
class XmlFieldOverrides:
    """Raw override for a default field or definition of a new field.

    The target field name is the key in the ``xmlfields`` dict and therefore not
    part of the definition itself. ``None`` means that a value is not configured
    and a default is inherited when the rule is parsed.
    """

    element: str | None = None
    section: str | None = None
    name: str | None = None
    attribute: str | None = None
    convert: XmlFieldConvert | None = None


XMLFIELD_KEYS = ("element", "section", "name", "attribute", "convert")
XMLFIELD_SECTIONS = ("Event", "System", "EventData", "UserData", "ProcessingErrorData")
XMLFIELD_CONVERTS = typing.get_args(XmlFieldConvert)
XMLFIELD_CONVERTERS: dict[str, Callable[[str], FieldValue]] = {
    "str": str,
    "int": to_int_or_str,
    "timestamp": to_iso8601,
}


def _validate_target(target: object) -> str:
    """Validate and return a target field name."""
    if not isinstance(target, str) or not target:
        raise InvalidRuleDefinitionError("xmlfields: target field names must be non-empty strings")
    return target


def _parse_definition(target: str, definition: object) -> XmlFieldOverrides:
    """Validate a single field definition and turn it into an attrs dataclass."""
    if isinstance(definition, XmlFieldOverrides):
        values = {
            key: value for key in XMLFIELD_KEYS if (value := getattr(definition, key)) is not None
        }
    elif isinstance(definition, dict):
        unknown_keys = set(definition) - set(XMLFIELD_KEYS)
        if unknown_keys:
            unknown = sorted(str(key) for key in unknown_keys)
            raise InvalidRuleDefinitionError(
                f"xmlfields: unknown keys in definition of '{target}': {unknown}"
            )
        values = {key: definition[key] for key in XMLFIELD_KEYS if key in definition}
    else:
        raise InvalidRuleDefinitionError(f"xmlfields: definition of '{target}' must be a dict")
    for key, value in values.items():
        if not isinstance(value, str):
            raise InvalidRuleDefinitionError(f"xmlfields: '{key}' of '{target}' must be a string")
    return XmlFieldOverrides(**values)


def _validate_definition_values(target: str, definition: XmlFieldOverrides) -> None:
    """Validate the values of a single field definition."""
    if definition.element is not None and not definition.element:
        raise InvalidRuleDefinitionError(
            f"xmlfields: 'element' of '{target}' must be a non-empty string"
        )
    if definition.section is not None and definition.section not in XMLFIELD_SECTIONS:
        raise InvalidRuleDefinitionError(
            f"xmlfields: unknown section for '{target}': {definition.section}"
        )
    if definition.convert is not None and definition.convert not in XMLFIELD_CONVERTS:
        raise InvalidRuleDefinitionError(
            f"xmlfields: unknown convert type for '{target}': {definition.convert}"
        )
    if target not in DEFAULT_XMLFIELD_TARGETS and not definition.element:
        raise InvalidRuleDefinitionError(
            f"xmlfields: 'element' is required for new target '{target}'"
        )


def _build_spec(target: str, override: XmlFieldOverrides) -> XmlFieldSpec:
    """Resolve an override against the default fields into a field spec."""
    default = DEFAULT_XMLFIELDS.get(target)
    if override.convert is not None:
        convert = XMLFIELD_CONVERTERS[override.convert]
    else:
        convert = default.convert if default else str
    return XmlFieldSpec(
        element=(
            override.element
            if override.element is not None
            else (default.element if default else "")
        ),
        target=target,
        section=(
            override.section
            if override.section is not None
            else (default.section if default else "System")
        ),
        name=override.name if override.name is not None else (default.name if default else None),
        attribute=(
            override.attribute
            if override.attribute is not None
            else (default.attribute if default else None)
        ),
        convert=convert,
    )


def parse_xmlfields(xmlfields: object) -> dict[str, XmlFieldSpec] | None:
    """Validate an ``xmlfields`` rule option and resolve its field specs."""
    if xmlfields is None:
        return None
    if not isinstance(xmlfields, dict):
        raise InvalidRuleDefinitionError(
            "xmlfields: must be a dict that maps target field names to definitions"
        )
    parsed: dict[str, XmlFieldSpec] = {}
    for target, definition in xmlfields.items():
        validated_target = _validate_target(target)
        if isinstance(definition, XmlFieldSpec):
            parsed[validated_target] = definition
            continue
        override = _parse_definition(validated_target, definition)
        _validate_definition_values(validated_target, override)
        parsed[validated_target] = _build_spec(validated_target, override)
    return parsed


def validate_xmlfields(instance, attribute, value) -> None:
    """Validate the optional ``xmlfields`` configuration."""
    if value is not None and instance.source_format != "windows_event_log":
        raise InvalidRuleDefinitionError(
            f"{attribute.name} is only supported with source_format windows_event_log"
        )


class DecoderRule(FieldManagerRule):
    """Rule for the |PROCESSOR_NAME| processor"""

    decode_func: Callable[[str], FieldValue]

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Config for DecoderRule"""

        source_fields: list = field(
            validator=(
                validators.max_len(1),
                validators.instance_of(list),
                validators.deep_iterable(member_validator=validators.instance_of(str)),
            ),
            factory=list,
        )
        """The field to decode as list with maximum one element. For multi field operations
           use :code:`mapping` instead.
        """
        source_format: str = field(
            validator=(validators.instance_of(str), validators.in_(IMPLEMENTED_DECODERS)),
            default="json",
        )
        """The source format in the source field. Defaults to :code:`json`
        Possible values are
        :code:`json`,
        :code:`base64`,
        :code:`clf`,
        :code:`nginx`,
        :code:`syslog_rfc5424`,
        :code:`syslog_rfc3164`,
        :code:`syslog_rfc3164_local`,
        :code:`logfmt`,
        :code:`cri`,
        :code:`docker`,
        :code:`decolorize`,
        :code:`windows_event_log`
        """
        xmlfields: dict[str, XmlFieldSpec] | None = field(
            converter=parse_xmlfields,
            validator=validate_xmlfields,
            default=None,
        )
        """Optional configuration for the :code:`windows_event_log` format. It is a dict that maps
           a target field name to an override definition and is merged into the default extraction.
           If the target is one of the default field names, only the given properties are changed;
           all other properties are inherited. New targets are added and require an :code:`element`.
           Overrides are applied after the defaults and therefore win over default and data fields
           with the same name. Each definition may set :code:`element`, :code:`section`
           (:code:`Event`, :code:`System`, :code:`EventData`, :code:`UserData` or
           :code:`ProcessingErrorData`), :code:`name` to match an element's ``Name`` attribute,
           :code:`attribute` and :code:`convert` (:code:`str`, :code:`int` or :code:`timestamp`).
           Without this option the `im_msvistalog
           <https://docs.nxlog.co/agent/current/im/msvistalog.html>`_-style fields plus flattened
           data fields are emitted.
        """

    @property
    def config(self) -> Config:
        """Provides the properly typed rule configuration object"""
        return typing.cast(DecoderRule.Config, self._config)

    @property
    def source_format(self) -> str:
        """Getter for rule config"""
        return self.config.source_format

    @property
    def xmlfields(self) -> dict[str, XmlFieldSpec] | None:
        """Getter for the optional windows_event_log field mapping"""
        return self.config.xmlfields

    def __init__(self, filter_rule: FilterExpression, config: Config, processor_name: str):
        super().__init__(filter_rule, config, processor_name)
        self.decode_func = get_decoder(self.source_format, self.xmlfields)
