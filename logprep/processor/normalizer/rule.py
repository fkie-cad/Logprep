"""This module is used to get documents that match a normalization filter."""

from typing import Union, Dict, List

import re
from pygrok import Grok

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.base.rule import Rule, InvalidRuleDefinitionError

GROK_DELIMITER = "__________________"


class NormalizerRuleError(InvalidRuleDefinitionError):
    """Base class for Normalizer rule related exceptions."""

    def __init__(self, message):
        super().__init__(f"Normalizer rule ({message}): ")


class InvalidNormalizationDefinition(NormalizerRuleError):
    """Raise if normalization definition invalid."""

    def __init__(self, definition: Union[list, dict]):
        message = f"The following normalization definition is invalid: {definition}"
        super().__init__(message)


class InvalidGrokDefinition(NormalizerRuleError):
    """Raise if grok definition invalid."""

    def __init__(self, definition: Union[list, dict]):
        message = f"The following grok-expression is invalid: {definition}"
        super().__init__(message)


class InvalidTimestampDefinition(NormalizerRuleError):
    """Raise if timestamp definition invalid."""

    def __init__(self, definition: Union[list, dict]):
        message = f"The following timestamp normalization definition is invalid: {definition}"
        super().__init__(message)


class GrokWrapper:
    """Wrap around pygrok to add delimiter support."""

    grok_delimiter_pattern = re.compile(GROK_DELIMITER)

    def __init__(self, patterns: Union[str, List[str]], **kwargs):
        if isinstance(patterns, str):
            self._grok_list = [Grok(f"^{patterns}$", **kwargs)]
        else:
            patterns = [f"^{pattern}$" for pattern in patterns]
            self._grok_list = [Grok(pattern_item, **kwargs) for pattern_item in patterns]

        self._match_cnt_initialized = False

    def match(self, text: str, pattern_matches: dict = None) -> Dict[str, str]:
        """Match string via grok using delimiter and count matches if enabled."""
        if pattern_matches is not None and not self._match_cnt_initialized:
            for grok in self._grok_list:
                pattern_matches[grok.pattern] = 0
            self._match_cnt_initialized = True

        for grok in self._grok_list:
            matches = grok.match(text)
            if matches:
                if pattern_matches is not None:
                    pattern_matches[grok.pattern] += 1
                dotted_matches = {}
                for key, value in matches.items():
                    dotted_matches[self.grok_delimiter_pattern.sub(".", key)] = value
                return dotted_matches
        return dict()


class NormalizerRule(Rule):
    """Check if documents match a filter."""

    additional_grok_patterns = None
    extract_field_pattern = re.compile(r"%{(\w+):([\w\[\]]+)(?::\w+)?}")
    sub_fields_pattern = re.compile(r"(\[(\w+)\])")

    def __init__(self, filter_rule: FilterExpression, normalizations: dict):
        super().__init__(filter_rule)
        self._substitutions = {}
        self._grok = {}
        self._timestamps = {}

        self._parse_normalizations(normalizations)

    def _parse_normalizations(self, normalizations):
        for src, norm in normalizations.items():
            if isinstance(norm, dict) and norm.get("grok"):
                norm["grok"] = [norm["grok"]] if isinstance(norm["grok"], str) else norm["grok"]
                for idx, grok in enumerate(norm["grok"]):
                    patterns = self.extract_field_pattern.findall(grok)
                    for pattern in patterns:
                        if len(pattern) >= 2:
                            sub_fields = re.findall(self.sub_fields_pattern, pattern[1])
                            if sub_fields:
                                mutable_pattern = list(pattern)
                                mutable_pattern[1] = GROK_DELIMITER.join(
                                    (sub_field[1] for sub_field in sub_fields)
                                )
                                to_replace = re.escape(r"%{" + r":".join(pattern))
                                transformed_fields_names = "%{" + ":".join(mutable_pattern)
                                norm["grok"][idx] = re.sub(
                                    to_replace, transformed_fields_names, norm["grok"][idx]
                                )
                    self._grok.update(
                        {
                            src: GrokWrapper(
                                norm["grok"],
                                custom_patterns_dir=NormalizerRule.additional_grok_patterns,
                            )
                        }
                    )
            elif isinstance(norm, dict) and norm.get("timestamp"):
                self._timestamps.update({src: norm})
            else:
                self._substitutions.update({src: norm})

    def __eq__(self, other: "NormalizerRule") -> bool:
        return (
            (other.filter == self._filter)
            and (self._substitutions == other.substitutions)
            and (self._grok == other.grok)
        )

    # pylint: disable=C0111
    @property
    def substitutions(self) -> dict:
        return self._substitutions

    @property
    def grok(self) -> dict:
        return self._grok

    @property
    def timestamps(self) -> dict:
        return self._timestamps

    # pylint: enable=C0111

    @staticmethod
    def _create_from_dict(rule: dict) -> "NormalizerRule":
        NormalizerRule._check_rule_validity(rule, "normalize")
        NormalizerRule._check_if_normalization_valid(rule)

        filter_expression = Rule._create_filter_expression(rule)
        return NormalizerRule(filter_expression, rule["normalize"])

    @staticmethod
    def _check_if_normalization_valid(rule: dict):
        for value in rule["normalize"].values():
            if isinstance(value, list):
                if len(value) != 3:
                    raise InvalidNormalizationDefinition(value)
            if isinstance(value, dict):

                if any([key for key in value.keys() if key not in ("grok", "timestamp")]):
                    raise InvalidNormalizationDefinition(value)

                if "grok" in value.keys():
                    grok = value["grok"]
                    if not grok:
                        raise InvalidNormalizationDefinition(value)
                    if isinstance(grok, list):
                        if any([not isinstance(pattern, str) for pattern in grok]):
                            raise InvalidNormalizationDefinition(value)
                    try:
                        GrokWrapper(
                            grok, custom_patterns_dir=NormalizerRule.additional_grok_patterns
                        )
                    except Exception as error:
                        raise InvalidGrokDefinition(grok) from error

                if "timestamp" in value.keys():
                    timestamp = value.get("timestamp")
                    if not timestamp:
                        raise InvalidNormalizationDefinition(value)
                    if not isinstance(timestamp.get("destination"), str):
                        raise InvalidTimestampDefinition(timestamp)
                    if not isinstance(timestamp.get("source_formats"), list):
                        raise InvalidTimestampDefinition(timestamp)
                    if not isinstance(timestamp.get("source_timezone"), str):
                        raise InvalidTimestampDefinition(timestamp)
                    if not isinstance(timestamp.get("destination_timezone"), str):
                        raise InvalidTimestampDefinition(timestamp)
