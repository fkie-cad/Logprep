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

For :code:`windows_event_log`, the following fields are extracted from the
:code:`System` section by default. If no XML attribute is listed, the stripped
text of the element is used:

..  list-table:: Default Windows Event Log fields
   :header-rows: 1

   * - Target field
     - XML element
     - XML attribute
     - Conversion
   * - :code:`SourceName`
     - :code:`Provider`
     - :code:`Name`
     - -
   * - :code:`ProviderGuid`
     - :code:`Provider`
     - :code:`Guid`
     - -
   * - :code:`EventID`
     - :code:`EventID`
     - -
     - :code:`int`
   * - :code:`Version`
     - :code:`Version`
     - -
     - :code:`int`
   * - :code:`LevelValue`
     - :code:`Level`
     - -
     - :code:`int`
   * - :code:`TaskValue`
     - :code:`Task`
     - -
     - :code:`int`
   * - :code:`OpcodeValue`
     - :code:`Opcode`
     - -
     - :code:`int`
   * - :code:`Keywords`
     - :code:`Keywords`
     - -
     - -
   * - :code:`EventTime`
     - :code:`TimeCreated`
     - :code:`SystemTime`
     - :code:`timestamp`
   * - :code:`RecordNumber`
     - :code:`EventRecordID`
     - -
     - :code:`int`
   * - :code:`ActivityID`
     - :code:`Correlation`
     - :code:`ActivityID`
     - -
   * - :code:`ExecutionProcessID`
     - :code:`Execution`
     - :code:`ProcessID`
     - :code:`int`
   * - :code:`ExecutionThreadID`
     - :code:`Execution`
     - :code:`ThreadID`
     - :code:`int`
   * - :code:`Channel`
     - :code:`Channel`
     - -
     - -
   * - :code:`Hostname`
     - :code:`Computer`
     - -
     - -

The :code:`int` conversion turns numeric strings into integers and leaves other
values unchanged. :code:`timestamp` normalizes timestamps to ISO 8601 in UTC
and leaves values that cannot be parsed unchanged. Fields from the
:code:`EventData`, :code:`UserData` and :code:`ProcessingErrorData` sections are
additionally flattened into the result, keyed by their :code:`Name` attribute.

The :code:`xmlfields` option can change these defaults and add fields from any
XML section. It is a dict whose keys are the target field names:

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
from collections.abc import Sequence
from typing import Callable

from attrs import define, field, validators

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.decoder.decoders.registry import DECODERS, get_decoder
from logprep.processor.decoder.decoders.windows_event_log import (
    XmlFieldSpec,
    parse_xmlfields,
)
from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.util.helper import FieldValue

IMPLEMENTED_DECODERS = tuple(DECODERS.keys())


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
        xmlfields: Sequence[XmlFieldSpec] | None = field(
            converter=parse_xmlfields,
            validator=validate_xmlfields,
            default=None,
        )
        """Optional configuration for the :code:`windows_event_log` format. In YAML it is a dict
           that maps a target field name to an override definition; programmatically a sequence of
           :code:`XmlFieldSpec` is accepted as well. It is resolved into a sequence of fully
           populated :code:`XmlFieldSpec` instances. If the target is one of the default field
           names, only the given properties are changed; all other properties are inherited. New
           targets are added and require an :code:`element`. Overrides are applied after the
           defaults and therefore win over default and data fields with the same name. Each
           definition may set :code:`element`, :code:`section` (:code:`Event`, :code:`System`,
           :code:`EventData`, :code:`UserData` or :code:`ProcessingErrorData`), :code:`name` to
           match an element's ``Name`` attribute, :code:`attribute` and :code:`convert`
           (:code:`str`, :code:`int` or :code:`timestamp`). Without this option the `im_msvistalog
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
    def xmlfields(self) -> Sequence[XmlFieldSpec] | None:
        """Getter for the resolved windows_event_log field specifications"""
        return self.config.xmlfields

    def __init__(self, filter_rule: FilterExpression, config: Config, processor_name: str):
        super().__init__(filter_rule, config, processor_name)
        self.decode_func = get_decoder(self.source_format, self.xmlfields)
