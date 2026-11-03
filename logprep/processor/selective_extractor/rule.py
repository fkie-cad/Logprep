"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

The selective extractor requires the additional field :code:`selective_extractor`.
It contains a list of field names that should be extracted (:code:`source_fields`)
and list of output mappings to which they should be send to (:code:`outputs`).
If dotted notation is being used, then all fields on the path are being automatically
created.

In the following example, the field :code:`field.extract` with
the value :code:`extracted value` is being extracted
and send to the output named :code:`kafka` and the topic named :code:`topic_to_send_to`.

..  code-block:: yaml
    :linenos:
    :caption: Example rule with extract from field list

    filter: extract_test
    selective_extractor:
      source_fields: ["field.extract", "field2", "field3"]
      outputs:
        - kafka: topic_to_send_to
    description: '...'


..  code-block:: json
    :caption: Example event

    {
      "extract_test": {
        "field": {
          "extract": "extracted value"
        }
      }
    }

..  code-block:: json
    :caption: Extracted event from Example

    {
      "extract": "extracted value"
    }



Alternatively, the additional field :code:`selective_extractor.extract_from_file`
can be added.
It contains the path to a text file with a list of fields per line to be extracted.

..  code-block:: yaml
    :linenos:
    :caption: Example rule with extract from file

    filter: extract_test
    selective_extractor:
        extract_from_file: /path/to/file
        outputs:
            - opensearch: topic_to_send_to
    description: '...'


..  code-block:: text
    :caption: Example of file with field list

    field1
    field2
    field3

The file has to exist.

It is possible to mix both extraction sources. They will be merged to one list without duplicates.


..  code-block:: yaml
    :linenos:
    :caption: Example rule with extract from file

    filter: extract_test
    selective_extractor:
        extract_from_file: /path/to/file
        source_fields: ["field1", "field2", "field4"]
        outputs:
          - kafka: topic_to_send_to
    description: '...'


..  code-block:: text
    :caption: Example of file with field list

    field1
    field2
    field3

Event templates
---------------

Use ``event_template`` to build nested extra events from literal values and
whole-value expressions. It cannot be combined with nonempty ``source_fields``
or field names loaded through ``extract_from_file``. ``outputs`` remains required.

.. code-block:: yaml

    filter: message
    description: 'Create an audit event'
    selective_extractor:
      event_template:
        message: '${source_event.message}'
        rule_description: '${rule.description}'
        created_at: '${context.now}'
        event_id: '${context.id}'
      outputs:
        - kafka: audit_events

``source_event`` exposes the incoming event. ``rule`` exposes its ``id`` as a
string, its ``description``, and the normalized ``filter`` expression. ``context``
provides ``now`` as a UTC ISO 8601 timestamp and ``id`` as a UUID4 string. Context
values are computed only when referenced, reused within one rule evaluation,
and refreshed for the next evaluation.

Expressions can appear in mapping keys, nested mappings, and lists. Resolved
keys must be strings; for example, ``${source_event.id | str}`` converts an ID
to a string. A standalone expression preserves its value's type, including
``None``. Interpolation into surrounding literal text is unsupported. See
:class:`logprep.util.field_mapping_template.FieldMappingTemplate` for function
calls, escaping, and the full template syntax.

Invalid template syntax or functions raise ``InvalidRuleDefinitionError`` when
the rule is created. Incorrect configuration types retain attrs validation
errors. A missing runtime lookup records a warning and adds
``_selective_extractor_missing_field_warning`` to the source event; no extra
event is emitted. ``ignore_missing_fields`` applies to legacy field selection,
not explicit templates. Empty templates are accepted and emit no extra event.

.. autoclass:: logprep.processor.selective_extractor.rule.SelectiveExtractorRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

Examples for selective_extractor:
------------------------------------------------

.. datatemplate:import-module:: tests.unit.processor.selective_extractor.test_selective_extractor
   :template: testcase-renderer.tmpl

"""

import typing
from typing import List

from attrs import define, field, validators

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.base.rule import InvalidRuleDefinitionError
from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.util.field_mapping_template import (
    FieldMappingTemplate,
    FieldMappingTemplateConfigError,
)
from logprep.util.field_mapping_template_helpers import (
    rule_to_fmt_context,
    source_fields_to_fmt,
)
from logprep.util.getter import GetterFactory
from logprep.util.helper import FieldValue, field_value_validator


class SelectiveExtractorRuleError(InvalidRuleDefinitionError):
    """Base class for SelectiveExtractor rule related exceptions."""

    def __init__(self, message: str):
        super().__init__(f"SelectiveExtractor rule ({message})")


class SelectiveExtractorRule(FieldManagerRule):
    """Compile selected fields or an event template for matching source events."""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Configure output destinations and either field selection or an event template."""

        source_fields: list = field(
            validator=[
                validators.deep_iterable(
                    member_validator=validators.instance_of(str),
                    iterable_validator=validators.instance_of(list),
                )
            ],
            factory=list,
            converter=sorted,
        )
        """List of fields in dotted field notation"""
        outputs: tuple[dict[str, str], ...] = field(
            validator=[
                validators.deep_iterable(
                    member_validator=[
                        validators.and_(
                            validators.instance_of(dict),
                            validators.deep_mapping(
                                key_validator=validators.instance_of(str),
                                value_validator=validators.instance_of(str),
                                mapping_validator=validators.max_len(1),
                            ),
                        ),
                    ],
                    iterable_validator=validators.instance_of(tuple),
                ),
                validators.min_len(1),
            ],
            converter=tuple,
        )
        """list of output mappings in form of :code:`output_name:topic`.
        Only one mapping is allowed per list element"""
        extract_from_file: str = field(validator=validators.instance_of(str), default="", eq=False)
        """The path or url to a file with a flat list of fields to extract.
        For string format see :ref:`getters`."""
        ignore_missing_fields: bool = field(validator=validators.instance_of(bool), default=True)
        """Ignore missing fields in legacy field selection when true (the default).

        Applies to ``source_fields`` and ``extract_from_file``. Explicit templates
        always report missing lookups as warnings and skip the extra event.
        """
        target_field: str = field(default="", init=False, repr=False, eq=False)
        overwrite_target: bool = field(default=False, init=False, repr=False, eq=False)
        merge_with_target: bool = field(default=False, init=False, repr=False, eq=False)
        mapping: dict = field(factory=dict, init=False, repr=False, eq=False)

        event_template: dict[str, FieldValue] | None = field(
            validator=validators.optional([validators.instance_of(dict), field_value_validator]),
            default=None,
        )
        """Mapping used to create an extra event from source, rule, and runtime context.

        Keys and values support field mapping template expressions. An empty mapping
        emits no extra event. ``None`` builds a template from legacy source fields.
        Nonempty legacy field selection cannot be combined with an explicit template.
        """

        deduplicate: bool = field(init=False, default=False)
        """Not active for this processor"""

        def __attrs_post_init__(self):
            super().__attrs_post_init__()
            if self.extract_from_file:
                try:
                    content = GetterFactory.from_string(self.extract_from_file).get()
                except FileNotFoundError as error:
                    raise SelectiveExtractorRuleError(
                        "extract_from_file is not a valid file handle"
                    ) from error
                self.source_fields = list({*self.source_fields, *content.splitlines()})
                if len(self.source_fields) < 1:
                    raise InvalidRuleDefinitionError("no field to extract")
            if self.event_template is not None and self.source_fields:
                raise InvalidRuleDefinitionError(
                    "one of event_template, extract_from_file or source_fields only allowed"
                )
            if self.event_template is None:
                self.event_template = source_fields_to_fmt(self.source_fields)

    def __init__(self, filter_rule: FilterExpression, config: Config, processor_name: str):
        """Compile the normalized template, translating template configuration errors.

        Raises ``InvalidRuleDefinitionError`` for invalid template syntax, references,
        or function signatures. Exceptions from functions run during folding propagate.
        """
        super().__init__(filter_rule, config, processor_name)

        if self.config.event_template is None:
            raise RuntimeError("SelectiveExtractor configuration did not initialize event_template")

        try:
            self.compiled_template = FieldMappingTemplate.compile(
                self.config.event_template,
                static_context={"rule": rule_to_fmt_context(self)},
                runtime_roots=["source_event", "context"],
            )
        except FieldMappingTemplateConfigError as error:
            raise InvalidRuleDefinitionError(f"Invalid event_template: {error}") from error

    @property
    def outputs(self) -> tuple[dict[str, str], ...]:
        """
        returns:
        --------
        outputs: list of output mappings
        """
        return self.config.outputs

    @property
    def extracted_field_list(self) -> List[str]:
        """
        returns:
        --------
        extracted_field_list: a list with extraction field names
        """
        return self.config.source_fields

    @property
    def config(self) -> Config:
        """Return the validated configuration, including its normalized event template."""
        return typing.cast(SelectiveExtractorRule.Config, self._config)

    def __eq__(self, other) -> bool:
        return isinstance(other, SelectiveExtractorRule) and all(
            [other.filter == self._filter, other._config == self._config]
        )
