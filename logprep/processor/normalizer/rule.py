"""This module is used to get documents that match a normalization filter."""

import re
from typing import Union, Dict, List

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

    def __init__(self, patterns: Union[str, List[str]], failure_target_field=None, **kwargs):
        if isinstance(patterns, str):
            self._grok_list = [Grok(f"^{patterns}$", **kwargs)]
        else:
            patterns = [f"^{pattern}$" for pattern in patterns]
            self._grok_list = [Grok(pattern_item, **kwargs) for pattern_item in patterns]

        self._match_cnt_initialized = False
        self.failure_target_field = failure_target_field

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
        return {}


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
        for source_field, normalization in normalizations.items():
            if isinstance(normalization, dict) and normalization.get("grok"):
                self._extract_grok_pattern(normalization, source_field)
            elif isinstance(normalization, dict) and normalization.get("timestamp"):
                self._timestamps.update({source_field: normalization})
            else:
                self._substitutions.update({source_field: normalization})

    def _extract_grok_pattern(self, normalization, source_field):
        """Checks the rule file for grok pattern, reformats them and adds them to self._grok"""
        if isinstance(normalization["grok"], str):
            normalization["grok"] = [normalization["grok"]]
        for idx, grok in enumerate(normalization["grok"]):
            patterns = self.extract_field_pattern.findall(grok)
            self._reformat_grok_pattern(idx, normalization, patterns)
            failure_target_field = normalization.get("failure_target_field")
            self._grok.update(
                {
                    source_field: GrokWrapper(
                        patterns=normalization["grok"],
                        custom_patterns_dir=NormalizerRule.additional_grok_patterns,
                        failure_target_field=failure_target_field,
                    )
                }
            )

    def _reformat_grok_pattern(self, idx, normalization, patterns):
        """
        Changes the grok pattern format by removing the square brackets and introducing
        the GROK_DELIMITER.
        """
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
                    normalization["grok"][idx] = re.sub(
                        to_replace, transformed_fields_names, normalization["grok"][idx]
                    )

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
                NormalizerRule._validate_allowed_keys(value)
                if "grok" in value.keys():
                    NormalizerRule._validate_grok(value)
                if "timestamp" in value.keys():
                    NormalizerRule._validate_timestamp(value)

    @staticmethod
    def _validate_allowed_keys(value):
        allowed_keys = ["grok", "timestamp", "failure_target_field"]
        if any(key for key in value.keys() if key not in allowed_keys):
            raise InvalidNormalizationDefinition(value)

    @staticmethod
    def _validate_grok(value):
        grok = value["grok"]
        if not grok:
            raise InvalidNormalizationDefinition(value)
        if isinstance(grok, list):
            if any(not isinstance(pattern, str) for pattern in grok):
                raise InvalidNormalizationDefinition(value)
        try:
            GrokWrapper(
                grok, custom_patterns_dir=NormalizerRule.additional_grok_patterns
            )
        except Exception as error:
            raise InvalidGrokDefinition(grok) from error

    @staticmethod
    def _validate_timestamp(value):
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
