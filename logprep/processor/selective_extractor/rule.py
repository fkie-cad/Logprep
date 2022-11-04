"""
Selective Extractor
===================

The selective extractor requires the additional field :code:`selective_extractor`.
The field :code:`selective_extractor.extract` has to be defined.
It contains a dictionary of field names that should be extracted and
a target topic to which they should be send to.
If dot notation is being used, then all fields on the path are being automatically created.

In the following example, the field :code:`field.extract` with
the value :code:`extracted value` is being extracted
and send to the topic :code:`topic_to_send_to`.

..  code-block:: yaml
    :linenos:
    :caption: Example rule with extract from field list

    filter: extract_test
    selective_extractor:
      extract:
        extracted_field_list: ["field.extract", "field2", "field3"]
        target_topic: topic_to_send_to
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
      extract:
        extract_from_file: /path/to/file
        target_topic: topic_to_send_to
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
      extract:
        extract_from_file: /path/to/file
        extracted_field_list: ["field1", "field2", "field4"]
        target_topic: topic_to_send_to
    description: '...'


..  code-block:: text
    :caption: Example of file with field list

    field1
    field2
    field3

"""

from functools import partial
from pathlib import Path
from typing import List, Optional
from attrs import define, field, validators

from logprep.processor.base.rule import Rule, InvalidRuleDefinitionError
from logprep.util.validators import dict_structure_validator, one_of_validator


class SelectiveExtractorRuleError(InvalidRuleDefinitionError):
    """Base class for SelectiveExtractor rule related exceptions."""

    def __init__(self, message: str):
        super().__init__(f"SelectiveExtractor rule ({message})")


class SelectiveExtractorRule(Rule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(Rule.Config):
        """RuleConfig for SelectiveExtractor"""

        extract: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.in_(
                        ["extract_from_file", "target_topic", "extracted_field_list"]
                    ),
                    value_validator=validators.instance_of((str, list)),
                ),
                partial(
                    one_of_validator, member_list=["extracted_field_list", "extract_from_file"]
                ),
                partial(
                    dict_structure_validator,
                    reference_dict={
                        "extract_from_file": Optional[str],
                        "target_topic": str,
                        "extracted_field_list": Optional[list],
                    },
                ),
            ]
        )
        """the extraction mapping"""

        @property
        def extract_from_file(self) -> Path:
            """Returns the PosixPath representation of extract_from_file"""
            extract_from_file = self.extract.get("extract_from_file")
            if extract_from_file is None:
                return None
            return Path(extract_from_file)

        def __attrs_post_init__(self):
            self._add_from_file()

        def _add_from_file(self):
            if self.extract_from_file is None:
                return
            if not self.extract_from_file.is_file():
                raise SelectiveExtractorRuleError("extract_from_file is not a valid file handle")
            extract_list = self.extract.get("extracted_field_list")
            if extract_list is None:
                extract_list = []
            lines_from_file = self.extract_from_file.read_text(encoding="utf8").splitlines()
            extract_list = list({*extract_list, *lines_from_file})
            self.extract = {**self.extract, **{"extracted_field_list": extract_list}}

    @property
    def target_topic(self) -> str:
        """
        returns:
        --------
        target_topic: the topic where to write the extracted fields to
        """
        return self._config.extract.get("target_topic")

    @property
    def extracted_field_list(self) -> List[str]:
        """
        returns:
        --------
        extracted_field_list: a list with extraction field names
        """
        return self._config.extract.get("extracted_field_list")

    def __eq__(self, other: "SelectiveExtractorRule") -> bool:
        return all(
            [
                other.filter == self._filter,
                set(self.extracted_field_list) == set(other.extracted_field_list),
                self.target_topic == other.target_topic,
            ]
        )
