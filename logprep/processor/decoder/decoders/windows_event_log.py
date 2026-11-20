"""Decoder for Windows Event Log XML.

The XML is parsed into a flat dict: by default the values of the ``System``
section are mapped to field names known from `im_msvistalog`_, while event
data fields are added at the same level. Any field of the XML can be selected
and renamed with the ``fields`` rule option. To prevent entity expansion
attacks, DOCTYPE declarations and deeply nested documents are rejected.

.. _im_msvistalog: https://docs.nxlog.co/agent/current/im/msvistalog.html
"""

import xml.etree.ElementTree as ET
from typing import Callable, Literal, NamedTuple, NotRequired, TypedDict

from logprep.processor.decoder.decoders.common import DecoderError
from logprep.util.helper import FieldValue
from logprep.util.time import UTC, TimeParser, TimeParserException

MAX_XML_DEPTH = 10

XmlFieldConvert = Literal["str", "int", "timestamp"]

SECTIONS = ("Event", "System", "EventData", "UserData", "ProcessingErrorData")


class XmlFieldDefinition(TypedDict):
    """Configuration of a single field to extract from the Windows Event Log XML."""

    element: str
    target: str
    section: NotRequired[str]
    name: NotRequired[str]
    attribute: NotRequired[str]
    convert: NotRequired[XmlFieldConvert]


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


def validate_fields(fields: object) -> None:
    """Validate a ``fields`` rule option, raising ``ValueError`` if invalid."""
    if fields is None:
        return
    if not isinstance(fields, list):
        raise ValueError("must be a list of field definitions")
    for definition in fields:
        if not isinstance(definition, dict):
            raise ValueError("each field definition must be a dict")
        allowed_keys = {"element", "target", "section", "name", "attribute", "convert"}
        unknown_keys = set(definition) - allowed_keys
        if unknown_keys:
            raise ValueError(f"unknown keys in field definition: {sorted(unknown_keys)}")
        for key in ("element", "target"):
            if not isinstance(definition.get(key), str) or not definition[key]:
                raise ValueError(f"'{key}' must be a non-empty string")
        for key in ("section", "name", "attribute", "convert"):
            if key in definition and not isinstance(definition[key], str):
                raise ValueError(f"'{key}' must be a string")
        section = definition.get("section", "System")
        if section not in SECTIONS:
            raise ValueError(f"unknown section: {section}")
        if definition.get("convert", "str") not in _CONVERTERS:
            raise ValueError(f"unknown convert type: {definition.get('convert')}")


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


class _XmlField(NamedTuple):
    """Description of a single value to extract from the Windows Event Log XML."""

    element: str
    target: str
    section: str = "System"
    name: str | None = None
    attribute: str | None = None
    convert: Callable[[str], FieldValue] = str


XML_FIELDS = (
    _XmlField("Provider", "SourceName", attribute="Name"),
    _XmlField("Provider", "ProviderGuid", attribute="Guid"),
    _XmlField("EventID", "EventID", convert=_to_int_or_str),
    _XmlField("Version", "Version", convert=_to_int_or_str),
    _XmlField("Level", "LevelValue", convert=_to_int_or_str),
    _XmlField("Task", "TaskValue", convert=_to_int_or_str),
    _XmlField("Opcode", "OpcodeValue", convert=_to_int_or_str),
    _XmlField("Keywords", "Keywords"),
    _XmlField("TimeCreated", "EventTime", attribute="SystemTime", convert=_to_iso8601),
    _XmlField("EventRecordID", "RecordNumber", convert=_to_int_or_str),
    _XmlField("Correlation", "ActivityID", attribute="ActivityID"),
    _XmlField("Execution", "ExecutionProcessID", attribute="ProcessID", convert=_to_int_or_str),
    _XmlField("Execution", "ExecutionThreadID", attribute="ThreadID", convert=_to_int_or_str),
    _XmlField("Channel", "Channel"),
    _XmlField("Computer", "Hostname"),
)

DATA_SECTIONS = ("EventData", "UserData", "ProcessingErrorData")


def _build_fields(definitions: list[XmlFieldDefinition]) -> tuple[_XmlField, ...]:
    """Turns rule configuration into field descriptions."""
    return tuple(
        _XmlField(
            element=definition["element"],
            target=definition["target"],
            section=definition.get("section", "System"),
            name=definition.get("name"),
            attribute=definition.get("attribute"),
            convert=_CONVERTERS[definition.get("convert", "str")],
        )
        for definition in definitions
    )


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


def _parse_fields(
    root: ET.Element, fields: dict[str, FieldValue], specs: tuple[_XmlField, ...]
) -> None:
    """Adds the values described by ``specs`` to ``fields``."""
    for spec in specs:
        element = _find_field_element(root, spec)
        if element is None:
            continue
        value = element.get(spec.attribute) if spec.attribute else _text(element)
        if value:
            fields[spec.target] = spec.convert(value.strip())


def _parse_data_section(section: ET.Element, fields: dict[str, FieldValue]) -> None:
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
    log_line: str, fields: list[XmlFieldDefinition] | None = None
) -> dict[str, FieldValue]:
    """Parses Windows Event Log XML into a flat dict of fields.

    By default, values of the ``System`` section are named after the fields
    produced by `im_msvistalog <https://docs.nxlog.co/agent/current/im/msvistalog.html>`_
    (for example ``EventID``, ``RecordNumber`` and ``Hostname``), and data
    fields from ``EventData``, ``UserData`` and ``ProcessingErrorData`` are
    added at the same level, keyed by their ``Name`` attribute. Unnamed data
    fields use their tag name instead.

    The optional ``fields`` configuration replaces this default extraction.
    Each definition requires an ``element`` and a ``target`` field name and
    accepts these optional keys:

    - ``section``: section to search; one of ``Event`` (the root), ``System``
      (default), ``EventData``, ``UserData`` or ``ProcessingErrorData``. Use
      ``section: Event`` and ``element: Event`` to read root attributes.
    - ``name``: value of the element's ``Name`` attribute, e.g. to select a
      specific ``Data`` element
    - ``attribute``: read an attribute instead of the element's text
    - ``convert``: ``str`` (default), ``int`` or ``timestamp``

    The unmodified XML is always kept in ``EventXML``.

    Timestamps are normalized to ISO 8601 in UTC when converted with
    :code:`timestamp`; values that cannot be converted are kept as strings.

    Limitations:

    - DOCTYPE declarations are rejected to prevent entity expansion, and
      documents nested deeper than ``MAX_XML_DEPTH`` are rejected as well.
    - Fields that are not part of the XML (for example rendered messages or
      event categories) cannot be derived and are not added.
    """
    validate_fields(fields)
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

    parsed: dict[str, FieldValue] = {}
    if fields is None:
        _parse_fields(root, parsed, XML_FIELDS)
        for section_name in DATA_SECTIONS:
            section = _find_child(root, section_name)
            if section is not None:
                _parse_data_section(section, parsed)
    else:
        _parse_fields(root, parsed, _build_fields(fields))
    parsed["EventXML"] = log_line
    return parsed
