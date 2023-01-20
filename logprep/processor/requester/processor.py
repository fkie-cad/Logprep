"""
Requester
=========

A processor to invoke http requests. Can be used to enrich events from an external api or
to trigger external systems by and with event field values.

For further information for the rule language see: :ref:`requester_rule`.

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

from logprep.abc.processor import Processor
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
        response = self._request(event, rule, kwargs)
        self._handle_response(event, rule, response)

    def _handle_response(self, event, rule, response):
        conflicting_fields = []
        if rule.target_field:
            result = self._get_result(response)
            successful = add_field_to(
                event,
                rule.target_field,
                result,
                rule.extend_target_list,
                rule.overwrite_target,
            )
            if not successful:
                conflicting_fields.append(rule.target_field)
        if rule.target_field_mapping:
            result = self._get_result(response)
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
                    conflicting_fields.append(rule.target_field)
        if conflicting_fields:
            raise DuplicationError(self.name, [rule.target_field])

    def _request(self, event, rule, kwargs):
        try:
            response = requests.request(**kwargs)
            response.raise_for_status()
        except requests.exceptions.HTTPError as error:
            self._handle_warning_error(event, rule, error)
        except requests.exceptions.ConnectTimeout as error:
            self._handle_warning_error(event, rule, error)
        return response

    @staticmethod
    def _get_result(response):
        try:
            result = json.loads(response.content)
        except json.JSONDecodeError:
            result = response.content.decode("utf-8")
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
