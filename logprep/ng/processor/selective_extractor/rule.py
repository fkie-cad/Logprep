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

``event_template`` is a mapping and supports :ref:`field_template` syntax.
See :ref:`selective_extractor_event_template` for the configuration, available data,
examples, and missing-field behavior, which also apply to this processor.

The available functions are the complete
:ref:`default function set <field_template_default_functions>`.
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

from logprep.ng.abc.processor import OutputSpec
from logprep.processor.selective_extractor.rule import (
    SelectiveExtractorRule as LegacySelectiveExtractorRule,
)
from logprep.util.converters import convert_ordered_tuples_with_factory


class SelectiveExtractorRule(LegacySelectiveExtractorRule):
    """Selective extractor rule with ng output specifications."""

    @define(kw_only=True)
    class Config(LegacySelectiveExtractorRule.Config):
        """RuleConfig for SelectiveExtractor"""

        outputs: Sequence[OutputSpec] = field(  # type: ignore[assignment]
            validator=validators.deep_iterable(
                iterable_validator=validators.min_len(1),
                member_validator=validators.instance_of(OutputSpec),
            ),
            converter=lambda d: convert_ordered_tuples_with_factory(d, OutputSpec),
        )
        """list of output mappings in form of :code:`output_name:topic`.
        Only one mapping is allowed per list element"""

    @property
    def config(self) -> Config:
        """Provides the properly typed configuration object"""
        return typing.cast(SelectiveExtractorRule.Config, self._config)

    @property
    def outputs(self) -> Sequence[OutputSpec]:  # type: ignore[override]
        """
        returns:
        --------
        outputs: list of output mappings
        """
        return self.config.outputs
