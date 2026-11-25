"""Decoder for Windows Event Log XML.

The XML is parsed into a flat dict: by default the values of the ``System``
section are mapped to field names known from `im_msvistalog`_, while event
data fields are added at the same level. The ``xmlfields`` rule option can
override default fields and add fields from any XML section. To prevent entity
expansion attacks, DOCTYPE declarations and deeply nested documents are
rejected.

.. _im_msvistalog: https://docs.nxlog.co/agent/current/im/msvistalog.html
"""

import xml.etree.ElementTree as ET
from collections.abc import Iterable, Sequence
from enum import StrEnum
from typing import Any, Callable, Literal, get_args

from attrs import define

from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.decoder.decoders.common import DecoderError
from logprep.util.helper import FieldValue, JsonObject
from logprep.util.time import UTC, TimeParser, TimeParserException

MAX_XML_DEPTH = 10
XmlFieldConvert = Literal["str", "int", "timestamp"]
XMLFIELD_KEYS = ("element", "section", "name", "attribute", "convert")
XMLFIELD_CONVERTS = get_args(XmlFieldConvert)


class WindowsEventLogElement(StrEnum):
    """String constants for Windows Event Log XML elements/sections."""

    SYSTEM = "System"
    EVENT = "Event"
    EVENT_DATA = "EventData"
    USER_DATA = "UserData"
    PROCESSING_ERROR_DATA = "ProcessingErrorData"


@define(frozen=True, kw_only=True)
class XmlFieldSpec:
    """Specification for a value to extract from the Windows Event Log XML.

    ``target`` names the result field. The other attributes may be omitted to
    inherit them from a default field. :func:`parse_xmlfields` resolves an
    ``xmlfields`` rule option into fully populated specs.
    """

    target: str
    element: str | None = None
    section: str | None = None
    name: str | None = None
    attribute: str | None = None
    convert: Callable[[str], FieldValue] | None = None


def to_iso8601(value: str) -> str:
    """Normalizes a Windows ``SystemTime`` to an ISO 8601 timestamp in UTC."""
    try:
        return TimeParser.from_string(value).astimezone(UTC).isoformat()
    except TimeParserException:
        return value


def to_int_or_str(value: str) -> FieldValue:
    """Converts numeric strings to int while preserving unparsable values."""
    try:
        return int(value)
    except ValueError:
        return value


def _find_child(element: ET.Element, name: str) -> ET.Element | None:
    """Returns the first direct child with ``name``."""
    return next((child for child in element if child.tag == name), None)


def _text(element: ET.Element) -> str:
    """Returns the stripped text of a leaf element."""
    return (element.text or "").strip()


XMLFIELDS = (
    XmlFieldSpec(element="Provider", target="SourceName", attribute="Name"),
    XmlFieldSpec(element="Provider", target="ProviderGuid", attribute="Guid"),
    XmlFieldSpec(element="EventID", target="EventID", convert=to_int_or_str),
    XmlFieldSpec(element="Version", target="Version", convert=to_int_or_str),
    XmlFieldSpec(element="Level", target="LevelValue", convert=to_int_or_str),
    XmlFieldSpec(element="Task", target="TaskValue", convert=to_int_or_str),
    XmlFieldSpec(element="Opcode", target="OpcodeValue", convert=to_int_or_str),
    XmlFieldSpec(element="Keywords", target="Keywords"),
    XmlFieldSpec(
        element="TimeCreated",
        target="EventTime",
        attribute="SystemTime",
        convert=to_iso8601,
    ),
    XmlFieldSpec(element="EventRecordID", target="RecordNumber", convert=to_int_or_str),
    XmlFieldSpec(element="Correlation", target="ActivityID", attribute="ActivityID"),
    XmlFieldSpec(
        element="Execution",
        target="ExecutionProcessID",
        attribute="ProcessID",
        convert=to_int_or_str,
    ),
    XmlFieldSpec(
        element="Execution",
        target="ExecutionThreadID",
        attribute="ThreadID",
        convert=to_int_or_str,
    ),
    XmlFieldSpec(element="Channel", target="Channel"),
    XmlFieldSpec(element="Computer", target="Hostname"),
)

DATA_SECTIONS = (
    WindowsEventLogElement.EVENT_DATA,
    WindowsEventLogElement.USER_DATA,
    WindowsEventLogElement.PROCESSING_ERROR_DATA,
)
XMLFIELD_SECTIONS = tuple(section.value for section in WindowsEventLogElement)
DEFAULT_XMLFIELDS = {spec.target: spec for spec in XMLFIELDS}
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


def _spec_from_definition(target: str, definition: object) -> XmlFieldSpec:
    """Turn a YAML mapping entry into a partially filled ``XmlFieldSpec``."""
    if not isinstance(definition, dict):
        raise InvalidRuleDefinitionError(f"xmlfields: definition of '{target}' must be a dict")
    unknown = sorted(str(key) for key in set(definition) - set(XMLFIELD_KEYS))
    if unknown:
        raise InvalidRuleDefinitionError(
            f"xmlfields: unknown keys in definition of '{target}': {unknown}"
        )
    values: dict[str, Any] = {}
    for key in XMLFIELD_KEYS:
        if key not in definition:
            continue
        value = definition[key]
        if not isinstance(value, str):
            raise InvalidRuleDefinitionError(f"xmlfields: '{key}' of '{target}' must be a string")
        if key == "convert":
            if value not in XMLFIELD_CONVERTS:
                raise InvalidRuleDefinitionError(
                    f"xmlfields: unknown convert type for '{target}': {value}"
                )
            values[key] = XMLFIELD_CONVERTERS[value]
        else:
            values[key] = value
    return XmlFieldSpec(target=target, **values)


def _validate_spec(spec: XmlFieldSpec) -> None:
    """Validate the attributes of a (possibly partial) field specification."""
    target = _validate_target(spec.target)
    for key in ("element", "section", "name", "attribute"):
        value = getattr(spec, key)
        if value is not None and not isinstance(value, str):
            raise InvalidRuleDefinitionError(f"xmlfields: '{key}' of '{target}' must be a string")
    if spec.element is not None and not spec.element:
        raise InvalidRuleDefinitionError(
            f"xmlfields: 'element' of '{target}' must be a non-empty string"
        )
    if spec.section is not None and spec.section not in XMLFIELD_SECTIONS:
        raise InvalidRuleDefinitionError(
            f"xmlfields: unknown section for '{target}': {spec.section}"
        )
    if spec.convert is not None and not callable(spec.convert):
        raise InvalidRuleDefinitionError(f"xmlfields: 'convert' of '{target}' must be a callable")


def _resolve_spec(spec: XmlFieldSpec) -> XmlFieldSpec:
    """Merge a specification with the default field for its target."""
    default = DEFAULT_XMLFIELDS.get(spec.target)
    element = spec.element if spec.element is not None else (default.element if default else None)
    if not element:
        raise InvalidRuleDefinitionError(
            f"xmlfields: 'element' is required for new target '{spec.target}'"
        )
    return XmlFieldSpec(
        target=spec.target,
        element=element,
        section=(
            spec.section
            if spec.section is not None
            else (default.section if default else None) or WindowsEventLogElement.SYSTEM
        ),
        name=spec.name if spec.name is not None else (default.name if default else None),
        attribute=(
            spec.attribute
            if spec.attribute is not None
            else (default.attribute if default else None)
        ),
        convert=(
            spec.convert
            if spec.convert is not None
            else (default.convert if default else None) or str
        ),
    )


def parse_xmlfields(xmlfields: object) -> tuple[XmlFieldSpec, ...] | None:
    """Validate an ``xmlfields`` rule option and resolve its field specs.

    Accepts a mapping of target names to override definitions (as used in YAML)
    or a sequence of ``XmlFieldSpec`` instances for programmatic use. The result
    is a sequence of fully populated specs with no redundant mapping keys.
    """
    if xmlfields is None:
        return None
    if isinstance(xmlfields, dict):
        specs = [
            _spec_from_definition(_validate_target(target), definition)
            for target, definition in xmlfields.items()
        ]
    elif isinstance(xmlfields, Sequence) and not isinstance(xmlfields, (str, bytes)):
        specs = []
        for spec in xmlfields:
            if not isinstance(spec, XmlFieldSpec):
                raise InvalidRuleDefinitionError(
                    "xmlfields: must be a dict or a sequence of XmlFieldSpec"
                )
            _validate_target(spec.target)
            specs.append(spec)
    else:
        raise InvalidRuleDefinitionError(
            "xmlfields: must be a dict that maps target field names to definitions "
            "or a sequence of XmlFieldSpec"
        )
    for spec in specs:
        _validate_spec(spec)
    return tuple(_resolve_spec(spec) for spec in specs)


class _SafeTreeBuilder(ET.TreeBuilder):
    """ElementTree target that rejects DTDs and excessive nesting."""

    def __init__(self) -> None:
        super().__init__()
        self._depth = 0

    @staticmethod
    def _local_tag(tag: str) -> str:
        # str.rpartition("}")[-1] also returns the original string when "}" is absent.
        return tag.rpartition("}")[-1]

    def doctype(self, name: str, pubid: str | None, system: str | None) -> None:
        """Reject any DTD declaration before entities can be expanded."""
        raise DecoderError("doctype is not supported in windows event logs")

    def start(self, tag: str, attrs: dict[str, str]) -> ET.Element:
        """Track the depth and reject documents nested deeper than the limit."""
        self._depth += 1
        if self._depth > MAX_XML_DEPTH:
            raise DecoderError("windows event log xml is nested too deeply")
        return super().start(self._local_tag(tag), attrs)

    def end(self, tag: str) -> ET.Element:
        """Decrement the depth after an element is closed."""
        self._depth -= 1
        return super().end(self._local_tag(tag))


def _find_field_element(root: ET.Element, spec: XmlFieldSpec) -> ET.Element | None:
    """Find the first element in the configured section matching the specification."""
    section_name = spec.section or WindowsEventLogElement.SYSTEM
    section = (
        root if section_name == WindowsEventLogElement.EVENT else _find_child(root, section_name)
    )
    if section is None:
        return None
    if section.tag == spec.element:
        return section
    return next(
        (
            element
            for element in section.iter()
            if element.tag == spec.element
            and (spec.name is None or element.get("Name") == spec.name)
        ),
        None,
    )


def _parse_fields(root: ET.Element, fields: JsonObject, specs: Iterable[XmlFieldSpec]) -> None:
    """Adds the values described by ``specs`` to ``fields``."""
    for spec in specs:
        element = _find_field_element(root, spec)
        if element is None:
            continue
        value = element.get(spec.attribute) if spec.attribute else _text(element)
        if value:
            convert = spec.convert or str
            fields[spec.target] = convert(value.strip())


def _parse_data_section(section: ET.Element, fields: JsonObject) -> None:
    """Flattens event data elements, using their ``Name`` attribute as field name.

    Unnamed values are rejected because deriving the field name from the element
    tag would make multiple unnamed values collide.
    """
    elements = list(reversed(section))
    while elements:
        element = elements.pop()
        name = element.get("Name")
        if name:
            value = _text(element)
            if value:
                fields.setdefault(name, value)
        elif len(element):
            elements.extend(reversed(element))
        elif _text(element):
            raise DecoderError("unnamed value in windows event log data section")


def parse_windows_event_log(
    log_line: str, xmlfields: Sequence[XmlFieldSpec] | None = None
) -> JsonObject:
    """Parses Windows Event Log XML into a flat dict of fields.

    The default extraction maps values of the ``System`` section to field
    names produced by `im_msvistalog
    <https://docs.nxlog.co/agent/current/im/msvistalog.html>`_ (for example
    ``EventID``, ``RecordNumber`` and ``Hostname``). Data fields from
    ``EventData``, ``UserData`` and ``ProcessingErrorData`` are flattened into
    the same dict, keyed by their ``Name`` attribute; unnamed values are
    rejected.

    The optional ``xmlfields`` sequence contains fully resolved ``XmlFieldSpec``
    instances created by :func:`parse_xmlfields` when the rule was loaded.
    They are applied after the defaults and therefore override default or event
    data fields with the same name.

    Timestamps are normalized to ISO 8601 in UTC when converted with
    :code:`timestamp`; values that cannot be converted are kept as strings.

    Limitations:

    - DOCTYPE declarations are rejected to prevent entity expansion, and
      documents nested deeper than ``MAX_XML_DEPTH`` are rejected as well.
    - Unnamed values in data sections are rejected to avoid field name collisions.
    - Fields that are not part of the XML (for example rendered messages or
      event categories) cannot be derived and are not added.
    """
    parser = ET.XMLParser(target=_SafeTreeBuilder())
    try:
        parser.feed(log_line)
        root = parser.close()
    except ET.ParseError as error:
        raise DecoderError("can't parse windows event log xml") from error
    if root.tag != WindowsEventLogElement.EVENT:
        raise DecoderError("not a windows event log")
    if _find_child(root, WindowsEventLogElement.SYSTEM) is None:
        raise DecoderError("windows event log has no System section")

    parsed: JsonObject = {}
    _parse_fields(root, parsed, XMLFIELDS)
    for section_name in DATA_SECTIONS:
        section = _find_child(root, section_name)
        if section is not None:
            _parse_data_section(section, parsed)
    if xmlfields:
        _parse_fields(root, parsed, xmlfields)
    return parsed
