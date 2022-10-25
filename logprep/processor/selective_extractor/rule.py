"""This module is used to extract fields from documents via a given list."""

from functools import partial
import os
from pathlib import Path
from typing import List, Optional
from attrs import define, field, validators

from logprep.processor.base.rule import Rule, InvalidRuleDefinitionError
from logprep.util.validators import dict_structure_validator, one_of_validator


class SelectiveExtractorRuleError(InvalidRuleDefinitionError):
    """Base class for SelectiveExtractor rule related exceptions."""

    def __init__(self, message: str):
        super().__init__(f"SelectiveExtractor rule ({message})")


class InvalidSelectiveExtractorDefinition(SelectiveExtractorRuleError):
    """Raise if SelectiveExtractor definition invalid."""

    def __init__(self, definition):
        message = f"The following SelectiveExtractor definition is invalid: {definition}"
        super().__init__(message)


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
            extract_list = list(set([*extract_list, *lines_from_file]))
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
