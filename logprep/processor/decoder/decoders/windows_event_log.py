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
from collections.abc import Iterable
from typing import Callable

from attrs import define

from logprep.processor.decoder.decoders.common import DecoderError
from logprep.util.helper import FieldValue, JsonObject
from logprep.util.time import UTC, TimeParser, TimeParserException

MAX_XML_DEPTH = 10


@define(frozen=True, kw_only=True)
class XmlFieldSpec:
    """Description of a single value to extract from the Windows Event Log XML."""

    element: str
    target: str
    section: str = "System"
    name: str | None = None
    attribute: str | None = None
    convert: Callable[[str], FieldValue] = str


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


XML_FIELDS = (
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

DATA_SECTIONS = ("EventData", "UserData", "ProcessingErrorData")
DEFAULT_XML_FIELDS = {spec.target: spec for spec in XML_FIELDS}
DEFAULT_XML_FIELD_TARGETS = frozenset(DEFAULT_XML_FIELDS)


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


def _find_field_element(root: ET.Element, spec: XmlFieldSpec) -> ET.Element | None:
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


def _parse_fields(root: ET.Element, fields: JsonObject, specs: Iterable[XmlFieldSpec]) -> None:
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
    log_line: str, xmlfields: dict[str, XmlFieldSpec] | None = None
) -> JsonObject:
    """Parses Windows Event Log XML into a flat dict of fields.

    The default extraction maps values of the ``System`` section to field
    names produced by `im_msvistalog
    <https://docs.nxlog.co/agent/current/im/msvistalog.html>`_ (for example
    ``EventID``, ``RecordNumber`` and ``Hostname``). Data fields from
    ``EventData``, ``UserData`` and ``ProcessingErrorData`` are flattened into
    the same dict, keyed by their ``Name`` attribute; unnamed data fields use
    their tag name instead.

    The optional ``xmlfields`` mapping contains fully resolved ``XmlFieldSpec``
    instances that were created by the decoder rule when the rule was loaded.
    They are applied after the defaults and therefore override default or event
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
    if xmlfields:
        _parse_fields(root, parsed, xmlfields.values())
    parsed["EventXML"] = log_line
    return parsed
