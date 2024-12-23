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

.. autoclass:: logprep.processor.selective_extractor.rule.SelectiveExtractorRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:
"""

from typing import List

from attrs import define, field, validators

from logprep.processor.base.rule import InvalidRuleDefinitionError
from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.util.getter import GetterFactory


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
        outputs: tuple[dict[str, str]] = field(
            validator=[
                validators.deep_iterable(
                    member_validator=[
                        validators.instance_of(dict),
                        validators.deep_mapping(
                            key_validator=validators.instance_of(str),
                            value_validator=validators.instance_of(str),
                            mapping_validator=validators.max_len(1),
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
        """If set to :code:`True` missing fields will be ignored, no warning is logged and the event
        is not tagged with the failure tag. Defaults to :code:`True`"""
        target_field: str = field(default="", init=False, repr=False, eq=False)
        overwrite_target: bool = field(default=False, init=False, repr=False, eq=False)
        merge_with_target: bool = field(default=False, init=False, repr=False, eq=False)
        mapping: dict = field(default="", init=False, repr=False, eq=False)

        def __attrs_post_init__(self):
            super().__attrs_post_init__()
            if not self.extract_from_file:
                return
            try:
                content = GetterFactory.from_string(self.extract_from_file).get()
            except FileNotFoundError as error:
                raise SelectiveExtractorRuleError(
                    "extract_from_file is not a valid file handle"
                ) from error
            self.source_fields = list({*self.source_fields, *content.splitlines()})
            if len(self.source_fields) < 1:
                raise InvalidRuleDefinitionError("no field to extract")

    @property
    def outputs(self) -> str:
        """
        returns:
        --------
        outputs: list of output mappings
        """
        return self._config.outputs

    @property
    def extracted_field_list(self) -> List[str]:
        """
        returns:
        --------
        extracted_field_list: a list with extraction field names
        """
        return self._config.source_fields

    def __eq__(self, other: "SelectiveExtractorRule") -> bool:
        return all([other.filter == self._filter, other._config == self._config])
