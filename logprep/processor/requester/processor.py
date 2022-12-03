"""
Requester
=========

A processor to invoke http requests. Could be usefull to enrich events from an external api or
to trigger external systems by and with event field values.

"""
from functools import partial
import json
import re
import requests

from logprep.abc import Processor
from logprep.processor.base.exceptions import DuplicationError
from logprep.processor.requester.rule import RequesterRule
from logprep.util.helper import get_dotted_field_value, add_field_to, add_and_overwrite

TEMPLATE_KWARGS = ("url", "json", "data", "params")


class Requester(Processor):
    """A processor to invoke http requests with field data
    and parses response data to field values"""

    rule_class = RequesterRule

    def _apply_rules(self, event, rule):
        source_fields = rule.source_fields
        source_field_values = map(partial(get_dotted_field_value, event), source_fields)
        source_field_dict = dict(zip(source_fields, source_field_values))
        self._check_for_missing_values(event, rule, source_field_dict)
        kwargs = self._template_kwargs(rule.kwargs, source_field_dict)
        try:
            rsp = requests.request(**kwargs)
            rsp.raise_for_status()
        except requests.exceptions.HTTPError as error:
            self._handle_warning_error(event, rule, error)

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
