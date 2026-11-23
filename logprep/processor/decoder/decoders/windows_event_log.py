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
from typing import Callable, Literal

from attrs import define

from logprep.processor.decoder.decoders.common import DecoderError
from logprep.util.helper import FieldValue, JsonObject
from logprep.util.time import UTC, TimeParser, TimeParserException

MAX_XML_DEPTH = 10

XmlFieldConvert = Literal["str", "int", "timestamp"]

SECTIONS = ("Event", "System", "EventData", "UserData", "ProcessingErrorData")
RESERVED_TARGET = "EventXML"
XMLFIELD_KEYS = ("element", "section", "name", "attribute", "convert")


@define(frozen=True, kw_only=True)
class XmlFieldOverrides:
    """Optional overrides for a default field or definition of a new field.

    The target field name is the key in the ``xmlfields`` dict and therefore not
    part of the definition itself. ``None`` means that a value is not configured
    and a default is inherited where possible.
    """

    element: str | None = None
    section: str | None = None
    name: str | None = None
    attribute: str | None = None
    convert: XmlFieldConvert | None = None


def _to_iso8601(value: str) -> str:
    """Normalizes a Windows ``SystemTime`` to an ISO 8601 timestamp in UTC."""
    try:
        return TimeParser.from_string(value).astimezone(UTC).isoformat()
    except TimeParserException:
        return value


def _to_int_or_str(value: str) -> FieldValue:
    """Converts numeric strings to int while preserving unparsable values."""
    try:
        return int(value)
    except ValueError:
        return value


_CONVERTERS: dict[XmlFieldConvert, Callable[[str], FieldValue]] = {
    "str": str,
    "int": _to_int_or_str,
    "timestamp": _to_iso8601,
}


def _validate_target(target: object) -> str:
    """Validate and return a target field name."""
    if not isinstance(target, str) or not target:
        raise ValueError("target field names must be non-empty strings")
    if target == RESERVED_TARGET:
        raise ValueError(f"'{RESERVED_TARGET}' is reserved and cannot be configured")
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
            raise ValueError(f"unknown keys in definition of '{target}': {unknown}")
        values = {key: definition[key] for key in XMLFIELD_KEYS if key in definition}
    else:
        raise ValueError(f"definition of '{target}' must be a dict")
    for key, value in values.items():
        if not isinstance(value, str):
            raise ValueError(f"'{key}' of '{target}' must be a string")
    return XmlFieldOverrides(**values)


def _validate_definition_values(target: str, definition: XmlFieldOverrides) -> None:
    """Validate the values of a single field definition."""
    if definition.element is not None and not definition.element:
        raise ValueError(f"'element' of '{target}' must be a non-empty string")
    if definition.section is not None and definition.section not in SECTIONS:
        raise ValueError(f"unknown section for '{target}': {definition.section}")
    if definition.convert is not None and definition.convert not in _CONVERTERS:
        raise ValueError(f"unknown convert type for '{target}': {definition.convert}")
    if target not in DEFAULT_XML_FIELD_TARGETS and not definition.element:
        raise ValueError(f"'element' is required for new target '{target}'")


def parse_xmlfields(xmlfields: object) -> dict[str, XmlFieldOverrides] | None:
    """Validate an ``xmlfields`` rule option and normalize its definitions."""
    if xmlfields is None:
        return None
    if not isinstance(xmlfields, dict):
        raise ValueError("must be a dict that maps target field names to definitions")
    parsed: dict[str, XmlFieldOverrides] = {}
    for target, definition in xmlfields.items():
        validated_target = _validate_target(target)
        parsed_definition = _parse_definition(validated_target, definition)
        _validate_definition_values(validated_target, parsed_definition)
        parsed[validated_target] = parsed_definition
    return parsed


def validate_xmlfields(xmlfields: object) -> None:
    """Validate an ``xmlfields`` rule option, raising ``ValueError`` if invalid."""
    parse_xmlfields(xmlfields)


def _local_name(tag: object) -> str:
    """Strips an optional XML namespace from a tag name.

    ElementTree represents comments and processing instructions with callable
    tags, which are ignored by returning an empty name.
    """
    return tag.rpartition("}")[-1] if isinstance(tag, str) else ""


def _find_child(element: ET.Element, name: str) -> ET.Element | None:
    """Returns the first direct child with ``name``, ignoring namespaces."""
    return next((child for child in element if _local_name(child.tag) == name), None)


def _text(element: ET.Element) -> str:
    """Returns the stripped text of a leaf element."""
    return (element.text or "").strip()


@define(frozen=True, kw_only=True)
class _XmlField:
    """Description of a single value to extract from the Windows Event Log XML."""

    element: str
    target: str
    section: str = "System"
    name: str | None = None
    attribute: str | None = None
    convert: Callable[[str], FieldValue] = str


XML_FIELDS = (
    _XmlField(element="Provider", target="SourceName", attribute="Name"),
    _XmlField(element="Provider", target="ProviderGuid", attribute="Guid"),
    _XmlField(element="EventID", target="EventID", convert=_to_int_or_str),
    _XmlField(element="Version", target="Version", convert=_to_int_or_str),
    _XmlField(element="Level", target="LevelValue", convert=_to_int_or_str),
    _XmlField(element="Task", target="TaskValue", convert=_to_int_or_str),
    _XmlField(element="Opcode", target="OpcodeValue", convert=_to_int_or_str),
    _XmlField(element="Keywords", target="Keywords"),
    _XmlField(
        element="TimeCreated",
        target="EventTime",
        attribute="SystemTime",
        convert=_to_iso8601,
    ),
    _XmlField(element="EventRecordID", target="RecordNumber", convert=_to_int_or_str),
    _XmlField(element="Correlation", target="ActivityID", attribute="ActivityID"),
    _XmlField(
        element="Execution",
        target="ExecutionProcessID",
        attribute="ProcessID",
        convert=_to_int_or_str,
    ),
    _XmlField(
        element="Execution",
        target="ExecutionThreadID",
        attribute="ThreadID",
        convert=_to_int_or_str,
    ),
    _XmlField(element="Channel", target="Channel"),
    _XmlField(element="Computer", target="Hostname"),
)

DATA_SECTIONS = ("EventData", "UserData", "ProcessingErrorData")
DEFAULT_XML_FIELDS = {spec.target: spec for spec in XML_FIELDS}
DEFAULT_XML_FIELD_TARGETS = frozenset(DEFAULT_XML_FIELDS)


def _build_fields(xmlfields: dict[str, XmlFieldOverrides]) -> tuple[_XmlField, ...]:
    """Turns configured overrides into field descriptions.

    Targets that match a default field inherit its unspecified properties. New
    targets use ``System`` and ``str`` as defaults.
    """
    fields = []
    for target, override in xmlfields.items():
        default = DEFAULT_XML_FIELDS.get(target)
        if override.convert is not None:
            convert = _CONVERTERS[override.convert]
        else:
            convert = default.convert if default else str
        fields.append(
            _XmlField(
                element=override.element or (default.element if default else ""),
                target=target,
                section=(
                    override.section
                    if override.section is not None
                    else (default.section if default else "System")
                ),
                name=(
                    override.name
                    if override.name is not None
                    else (default.name if default else None)
                ),
                attribute=(
                    override.attribute
                    if override.attribute is not None
                    else (default.attribute if default else None)
                ),
                convert=convert,
            )
        )
    return tuple(fields)


class _SafeTreeBuilder(ET.TreeBuilder):
    """ElementTree target that rejects DTDs and excessive nesting."""

    def __init__(self) -> None:
        super().__init__()
        self._depth = 0

    def doctype(self, name: str, pubid: str | None, system: str | None) -> None:
        """Reject any DTD declaration before entities can be expanded."""
        raise DecoderError("doctype is not supported in windows event logs")

    def start(self, tag: str, attrs: dict[str, str]) -> ET.Element:
        """Track the depth and reject documents nested deeper than the limit."""
        self._depth += 1
        if self._depth > MAX_XML_DEPTH:
            raise DecoderError("windows event log xml is nested too deeply")
        return super().start(tag, attrs)

    def end(self, tag: str) -> ET.Element:
        """Decrement the depth after an element is closed."""
        self._depth -= 1
        return super().end(tag)


def _find_field_element(root: ET.Element, spec: _XmlField) -> ET.Element | None:
    """Find the first element in the configured section matching the specification."""
    section = root if spec.section == "Event" else _find_child(root, spec.section)
    if section is None:
        return None
    if _local_name(section.tag) == spec.element:
        return section
    return next(
        (
            element
            for element in section.iter()
            if element is not section
            and _local_name(element.tag) == spec.element
            and (spec.name is None or element.get("Name") == spec.name)
        ),
        None,
    )


def _parse_fields(root: ET.Element, fields: JsonObject, specs: tuple[_XmlField, ...]) -> None:
    """Adds the values described by ``specs`` to ``fields``."""
    for spec in specs:
        element = _find_field_element(root, spec)
        if element is None:
            continue
        value = element.get(spec.attribute) if spec.attribute else _text(element)
        if value:
            fields[spec.target] = spec.convert(value.strip())


def _parse_data_section(section: ET.Element, fields: JsonObject) -> None:
    """Flattens event data elements, using their ``Name`` attribute as field name."""
    elements = list(section)
    while elements:
        element = elements.pop()
        name = element.get("Name")
        if name:
            fields[name] = _text(element)
        elif len(element):
            elements.extend(reversed(element))
        else:
            fields[_local_name(element.tag)] = _text(element)


def parse_windows_event_log(
    log_line: str, xmlfields: dict[str, XmlFieldOverrides] | None = None
) -> JsonObject:
    """Parses Windows Event Log XML into a flat dict of fields.

    The default extraction maps values of the ``System`` section to field
    names produced by `im_msvistalog
    <https://docs.nxlog.co/agent/current/im/msvistalog.html>`_ (for example
    ``EventID``, ``RecordNumber`` and ``Hostname``). Data fields from
    ``EventData``, ``UserData`` and ``ProcessingErrorData`` are flattened into
    the same dict, keyed by their ``Name`` attribute; unnamed data fields use
    their tag name instead.

    The optional ``xmlfields`` configuration is merged into this result. It is
    a dict that maps a target field name to a definition with these optional
    keys:

    - ``element``: element name to read; required for new targets, optional
      when overriding a default field
    - ``section``: section to search; one of ``Event`` (the root), ``System``
      (default), ``EventData``, ``UserData`` or ``ProcessingErrorData``. Use
      ``section: Event`` and ``element: Event`` to read root attributes.
    - ``name``: value of the element's ``Name`` attribute, e.g. to select a
      specific ``Data`` element
    - ``attribute``: read an attribute instead of the element's text
    - ``convert``: ``str`` (default), ``int`` or ``timestamp``

    If the target matches a default field, only the given keys are changed and
    all other properties are inherited. New targets are added. Configured
    fields are extracted after the defaults and therefore override default or
    data fields with the same name. The unmodified XML is always kept in
    ``EventXML``, which is reserved and cannot be configured.

    Timestamps are normalized to ISO 8601 in UTC when converted with
    :code:`timestamp`; values that cannot be converted are kept as strings.

    Limitations:

    - DOCTYPE declarations are rejected to prevent entity expansion, and
      documents nested deeper than ``MAX_XML_DEPTH`` are rejected as well.
    - Fields that are not part of the XML (for example rendered messages or
      event categories) cannot be derived and are not added.
    """
    parsed_xmlfields = parse_xmlfields(xmlfields)
    parser = ET.XMLParser(target=_SafeTreeBuilder())
    try:
        parser.feed(log_line)
        root = parser.close()
    except ET.ParseError as error:
        raise DecoderError("can't parse windows event log xml") from error
    if _local_name(root.tag) != "Event":
        raise DecoderError("not a windows event log")
    system = _find_child(root, "System")
    if system is None:
        raise DecoderError("windows event log has no System section")

    parsed: JsonObject = {}
    _parse_fields(root, parsed, XML_FIELDS)
    for section_name in DATA_SECTIONS:
        section = _find_child(root, section_name)
        if section is not None:
            _parse_data_section(section, parsed)
    if parsed_xmlfields:
        _parse_fields(root, parsed, _build_fields(parsed_xmlfields))
    parsed["EventXML"] = log_line
    return parsed
