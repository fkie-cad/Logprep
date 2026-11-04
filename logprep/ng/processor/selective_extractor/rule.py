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



Alternatively, the additional field :code:`selective_extractor.extract.extract_from_file`
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

``event_template`` supports :ref:`field_mapping_template`. See
:ref:`selective_extractor_event_template` for the configuration, available data,
examples, and missing-field behavior, which also apply to this processor.

The available functions are the complete
:ref:`default function set <field_mapping_template_default_functions>`.
See the shared reference for accepted inputs, keyword arguments, and examples.
There are currently no additional functions specific to this processor.

.. autoclass:: logprep.processor.selective_extractor.rule.SelectiveExtractorRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:
"""

import typing
from collections.abc import Sequence

from attrs import define, field, validators

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.ng.abc.processor import OutputSpec
from logprep.processor.base.rule import InvalidRuleDefinitionError
from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.processor.selective_extractor.rule import (
    rule_to_fmt_context,
    source_fields_to_fmt,
)
from logprep.util.converters import convert_ordered_tuples_with_factory
from logprep.util.field_mapping_template import (
    FieldMappingTemplate,
    FieldMappingTemplateConfigError,
)
from logprep.util.getter import GetterFactory
from logprep.util.helper import FieldValue, field_value_validator


class SelectiveExtractorRuleError(InvalidRuleDefinitionError):
    """Base class for SelectiveExtractor rule related exceptions."""

    def __init__(self, message: str):
        super().__init__(f"SelectiveExtractor rule ({message})")


class SelectiveExtractorRule(FieldManagerRule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """RuleConfig for SelectiveExtractor"""

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

        outputs: Sequence[OutputSpec] = field(
            validator=validators.deep_iterable(
                iterable_validator=validators.min_len(1),
                member_validator=validators.instance_of(OutputSpec),
            ),
            converter=lambda d: convert_ordered_tuples_with_factory(d, OutputSpec),
        )
        """list of output mappings in form of :code:`output_name:topic`.
        Only one mapping is allowed per list element"""

        extract_from_file: str = field(validator=validators.instance_of(str), default="", eq=False)
        """The path or url to a file with a flat list of fields to extract.
        For string format see :ref:`getters`."""

        ignore_missing_fields: bool = field(validator=validators.instance_of(bool), default=True)
        """Warn and skip the whole extra event for missing fields when true (the default).

        When false, missing fields cause a critical processing error. Applies to
        ``source_fields``, ``extract_from_file``, and ``event_template``.
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
        Non-empty legacy field selection cannot be combined with an explicit template.
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
    def config(self) -> Config:
        """Provides the properly typed configuration object"""
        return typing.cast(SelectiveExtractorRule.Config, self._config)

    @property
    def outputs(self) -> Sequence[OutputSpec]:
        """
        returns:
        --------
        outputs: list of output mappings
        """
        return self.config.outputs

    @property
    def extracted_field_list(self) -> list[str]:
        """
        returns:
        --------
        extracted_field_list: a list with extraction field names
        """
        return self.config.source_fields

    def __eq__(self, other: object) -> bool:
        return isinstance(other, SelectiveExtractorRule) and all(
            [other.filter == self._filter, other._config == self._config]
        )
