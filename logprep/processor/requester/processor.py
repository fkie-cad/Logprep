"""
Requester
=========

A processor to invoke http requests. Can be used to enrich events from an external api or
to trigger external systems by and with event field values.

Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - requestername:
        type: requester
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/

"""
import json
import re
import requests

from logprep.abc import Processor
from logprep.processor.base.exceptions import DuplicationError
from logprep.processor.requester.rule import RequesterRule
from logprep.util.helper import add_field_to, get_dotted_field_value, get_source_fields_dict

TEMPLATE_KWARGS = ("url", "json", "data", "params")


class Requester(Processor):
    """A processor to invoke http requests with field data
    and parses response data to field values"""

    rule_class = RequesterRule

    def _apply_rules(self, event, rule):
        source_field_dict = get_source_fields_dict(event, rule)
        self._check_for_missing_values(event, rule, source_field_dict)
        kwargs = self._template_kwargs(rule.kwargs, source_field_dict)
        rsp = self._request(event, rule, kwargs)
        self._handle_response(event, rule, rsp)

    def _handle_response(self, event, rule, rsp):
        if rule.target_field:
            result = self._get_result(rsp)
            successful = add_field_to(
                event,
                rule.target_field,
                result,
                rule.extend_target_list,
                rule.overwrite_target,
            )
            if not successful:
                error = DuplicationError(self.name, [rule.target_field])
                self._handle_warning_error(event, rule, error)
        if rule.target_field_mapping:
            result = self._get_result(rsp)
            for source_field, target_field in rule.target_field_mapping.items():
                source_field_value = get_dotted_field_value(result, source_field)
                successful = add_field_to(
                    event,
                    target_field,
                    source_field_value,
                    rule.extend_target_list,
                    rule.overwrite_target,
                )
                if not successful:
                    error = DuplicationError(self.name, [rule.target_field])
                    self._handle_warning_error(event, rule, error)

    def _request(self, event, rule, kwargs):
        try:
            rsp = requests.request(**kwargs)
            rsp.raise_for_status()
        except requests.exceptions.HTTPError as error:
            self._handle_warning_error(event, rule, error)
        except requests.exceptions.ConnectTimeout as error:
            self._handle_warning_error(event, rule, error)
        return rsp

    @staticmethod
    def _get_result(rsp):
        try:
            result = json.loads(rsp.content)
        except json.JSONDecodeError:
            result = rsp.content.decode("utf-8")
        return result

    def _template_kwargs(self, kwargs: dict, source: dict):
        for key, value in kwargs.items():
            if key in TEMPLATE_KWARGS:
                kwargs.update({key: json.loads(self._template(json.dumps(value), source))})
        return kwargs

    @staticmethod
    def _template(string: str, source: dict) -> str:
        for key, value in source.items():
            key = key.replace(".", r"\.")
            pattern = r"\$\{(" + rf"{key}" + r")\}"
            string = re.sub(pattern, str(value), string)
        return string

    def _check_for_missing_values(self, event, rule, source_field_dict):
        missing_fields = list(
            dict(filter(lambda x: x[1] in [None, ""], source_field_dict.items())).keys()
        )
        if missing_fields:
            error = BaseException(f"{self.name}: no value for fields: {missing_fields}")
            self._handle_warning_error(event, rule, error)
