"""This module is used to extract fields from documents via a given list."""

import os
from typing import List

from ruamel.yaml import YAML

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.base.rule import Rule, InvalidRuleDefinitionError

yaml = YAML(typ="safe", pure=True)


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

    _extract: dict = None

    _extract_from_file: os.PathLike = None

    _target_topic: str = None

    def __init__(self, filter_rule: FilterExpression, selective_extractor_cfg: dict):
        super().__init__(filter_rule)

        self._extract = selective_extractor_cfg.get("extract")
        self._target_topic = self._extract.get("target_topic")
        self._extract_from_file = self._extract.get("extract_from_file")
        if self._extract_from_file:
            self._add_from_file()

    @property
    def target_topic(self) -> str:
        """
        returns:
        --------
        target_topic: the topic where to write the extracted fields to
        """
        return self._target_topic

    @property
    def extracted_field_list(self) -> List[str]:
        """
        returns:
        --------
        extracted_field_list: a list with extraction field names
        """
        return self._extract.get("extracted_field_list")

    def _add_from_file(self):
        if not os.path.isfile(self._extract_from_file):
            raise SelectiveExtractorRuleError("extract_from_file is not a valid file handle")
        extract_list = self._extract.get("extracted_field_list")
        if extract_list is None:
            extract_list = []
        with open(self._extract_from_file, "r", encoding="utf8") as extract_file:
            lines_from_file = extract_file.read().splitlines()
            extract_list = list(set([*extract_list, *lines_from_file]))
        self._extract["extracted_field_list"] = extract_list

    def __eq__(self, other: "SelectiveExtractorRule") -> bool:
        return all(
            [
                other.filter == self._filter,
                set(self.extracted_field_list) == set(other.extracted_field_list),
                self.target_topic == other.target_topic,
            ]
        )

    @staticmethod
    def _create_from_dict(rule: dict) -> "SelectiveExtractorRule":
        SelectiveExtractorRule._check_rule_validity(rule, "selective_extractor")
        SelectiveExtractorRule._check_if_valid(rule)

        filter_expression = Rule._create_filter_expression(rule)
        return SelectiveExtractorRule(filter_expression, rule["selective_extractor"])

    @staticmethod
    def _check_if_valid(rule: dict):
        selective_extractor_cfg = rule.get("selective_extractor")
        if not isinstance(selective_extractor_cfg, dict):
            raise InvalidSelectiveExtractorDefinition(
                "'selective_extractor' definition has to be a dict"
            )
        if not "extract" in selective_extractor_cfg:
            raise InvalidSelectiveExtractorDefinition(
                "'selective_extractor' must contain 'extract'!"
            )
        extract = selective_extractor_cfg.get("extract")
        if not isinstance(extract, dict):
            raise InvalidSelectiveExtractorDefinition("'extract' definition has to be a dict")
        extract_from_file = extract.get("extract_from_file")
        extracted_field_list = extract.get("extracted_field_list")
        target_topic = extract.get("target_topic")
        if not (extract_from_file or extracted_field_list):
            raise InvalidSelectiveExtractorDefinition(
                (
                    "'selective_extractor' has no 'extracted_field_list' "
                    "or 'extract_from_file' field"
                )
            )
        if not target_topic:
            raise InvalidSelectiveExtractorDefinition("'selective_extractor' has no 'target_topic'")
        if not isinstance(target_topic, str):
            raise InvalidSelectiveExtractorDefinition("'target_topic' has to be a string")
        if extracted_field_list:
            if not isinstance(extracted_field_list, list):
                raise InvalidSelectiveExtractorDefinition("'extracted_field_list' has to be a list")
        if extract_from_file:
            if not isinstance(extract_from_file, str):
                raise InvalidSelectiveExtractorDefinition("'extract_from_file' has to be a string")
