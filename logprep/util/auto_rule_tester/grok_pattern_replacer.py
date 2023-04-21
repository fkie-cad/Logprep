#!/usr/bin/python3
"""This module implements a grok pattern replacer for the auto tester."""

import re
from pprint import pprint
from typing import Any

from logprep.util.grok_pattern_loader import GrokPatternLoader as gpl
from logprep.util.helper import get_dotted_field_value


# pylint: disable=protected-access
class GrokPatternReplacer:
    """Used to replace strings with pre-defined grok patterns."""

    def __init__(self, config: dict):
        self._grok_patterns = {
            "PSEUDONYM": r"<pseudonym:[a-fA-F0-9]{64}>",
            "UUID": r"[a-fA-F0-9]{8}-(?:[a-fA-F0-9]{4}-){3}[a-fA-F0-9]{12}",
            "NUMBER": r"[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?",
            "WORD": r"\w+",
            "IPV4": r"\d{1,3}(\.\d{1,3}){3}",
            "IPV4_PORT": r"\d{1,3}(\.\d{1,3}){3}:\d+",
        }

        additional_patterns_list = []
        pipeline_cfg = config.get("pipeline", [])
        for processor_cfg in pipeline_cfg:
            processor_values = list(processor_cfg.values())[0]
            additional_patterns = processor_values.get("grok_patterns")
            if additional_patterns:
                additional_patterns_list.append(processor_values.get("grok_patterns"))

        for additional_patterns in additional_patterns_list:
            if isinstance(additional_patterns, str):
                additional_patterns = [additional_patterns]
            for auto_test_pattern in additional_patterns:
                self._grok_patterns.update(gpl.load(auto_test_pattern))

        print("\nGrok Patterns:")
        pprint(self._grok_patterns)

        self._grok_base = re.compile(r"%\{.*?\}")

    @staticmethod
    def _change_dotted_field_value(event: dict, dotted_field: str, new_value: str):
        fields = dotted_field.split(".")
        dict_ = event
        last_field = None
        for field in fields:
            if field in dict_ and isinstance(dict_[field], dict):
                dict_ = dict_[field]
            last_field = field
        if last_field:
            dict_[last_field] = new_value

    @staticmethod
    def _change_dotted_field_list_value(event: dict, dotted_field: str, new_value: str, idx: int):
        fields = dotted_field.split(".")
        dict_ = event
        last_field = None
        for field in fields:
            if field in dict_ and isinstance(dict_[field], dict):
                dict_ = dict_[field]
            last_field = field
        if last_field:
            dict_[last_field][idx] = new_value

    def _replace_all_keywords_in_value(self, dotted_value: str) -> str:
        while bool(self._grok_base.search(str(dotted_value))):
            for identifier, grok_value in self._grok_patterns.items():
                pattern = "%{" + identifier + "}"
                dotted_value = str(dotted_value)
                dotted_value = dotted_value.replace(pattern, grok_value)
        return dotted_value

    def replace_grok_keywords(self, processed: dict, reference_dict: dict, dotted_field: str = ""):
        """Replace grok keywords in dotted field.

        Parameters
        ----------
        processed : dict
            Expected test result for rule test.
        reference_dict : dict
            Original test data containing test input and expected.
        dotted_field : str
            Field that contains value that should be replaced.

        """
        for processed_field, processed_sub in list(processed.items()):
            target_field = f"{dotted_field}.{processed_field}" if dotted_field else processed_field
            processed_val = get_dotted_field_value(reference_dict["processed"], target_field)

            if isinstance(processed_val, (str, int, float)):
                if processed_field.endswith("|re"):
                    new_key = processed_field.replace("|re", "")
                    value_raw = self._get_raw_value(target_field, reference_dict)
                    processed_val = self._change_value_to_grok(processed_val)
                    new_value = (
                        value_raw
                        if self._value_is_in_raw(processed_val, value_raw)
                        else processed_val
                    )
                    self._change_dotted_field_value(
                        reference_dict["processed"], target_field, new_value
                    )
                    processed[new_key] = processed.pop(processed_field)

            if isinstance(processed_sub, list):
                if self._is_regex_field(processed_field):
                    regex_selections = self._get_regex_selections(processed_field, processed_sub)

                    new_key = self._strip_regex_attribute(processed_field)
                    values_raw = self._get_raw_value(target_field, reference_dict)

                    for idx_1, processed_val in enumerate(processed[processed_field]):
                        if idx_1 in regex_selections:
                            value_raw = values_raw[idx_1]
                            processed_val_re = self._change_value_to_grok(processed_val)

                            if self._value_is_in_raw(processed_val_re, value_raw):
                                self._change_dotted_field_list_value(
                                    reference_dict["processed"],
                                    target_field,
                                    value_raw,
                                    idx_1,
                                )
                            else:
                                self._change_dotted_field_list_value(
                                    reference_dict["processed"],
                                    target_field,
                                    processed_val,
                                    idx_1,
                                )
                    processed[new_key] = processed.pop(processed_field)

            if isinstance(processed_sub, dict):
                self.replace_grok_keywords(processed_sub, reference_dict, dotted_field=target_field)

    @staticmethod
    def _strip_regex_attribute(dotted_field):
        return dotted_field.rsplit("|re", maxsplit=1)[0]

    @staticmethod
    def _is_regex_field(dotted_field):
        search_ends_with_regex = re.search(r"\|re(\(.+\)){0,1}$", dotted_field)
        return search_ends_with_regex if search_ends_with_regex else False

    @staticmethod
    def _get_regex_selections(processed_field, processed_sub):
        if re.search(r"\|re\(.+\)$", processed_field):
            regex_extra = processed_field.rsplit("|re", maxsplit=1)[1][1:-1].replace(" ", "")
            if re.search(r"^\d(,\d)*$", regex_extra):
                return [int(num) for num in regex_extra.split(",")]
        if processed_field.endswith("|re"):
            return list(range(len(processed_sub)))
        return []

    @staticmethod
    def _value_is_in_raw(value, value_raw):
        return bool(re.search(value, str(value_raw))) if value_raw else False

    def _change_value_to_grok(self, value):
        value = self._replace_grok_keywords_if_defined(value)
        value = "^" + value + "$"
        return value

    def _replace_grok_keywords_if_defined(self, value):
        grok_keywords_in_value = self._get_grok_keywords_in_value(value)
        if self._grok_keywords_in_value_are_defined(grok_keywords_in_value):
            value = self._replace_all_keywords_in_value(value)
        return value

    def _grok_keywords_in_value_are_defined(self, grok_keywords):
        defined_grok_keywords = self._construct_grok_keywords_from_patterns()
        return all(((grok_keyword in defined_grok_keywords) for grok_keyword in grok_keywords))

    def _construct_grok_keywords_from_patterns(self):
        return ["%{" + grok_definition + "}" for grok_definition in self._grok_patterns]

    def _get_grok_keywords_in_value(self, dotted_value: Any) -> set:
        return set(self._grok_base.findall(str(dotted_value)))

    def _get_raw_value(self, dotted_field: str, reference_dict: dict):
        value_raw = get_dotted_field_value(
            reference_dict["raw"], self._strip_regex_attribute(dotted_field)
        )
        return value_raw
