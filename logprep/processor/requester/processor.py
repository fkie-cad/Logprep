"""
Requester
=========

A processor to invoke http requests. Could be usefull to enrich events from an external api or
to trigger external systems by and with event field values.

"""
import re
import requests
from typing import List, Tuple, Any

from logprep.abc import Processor
from logprep.processor.base.exceptions import DuplicationError
from logprep.processor.requester.rule import RequesterRule
from logprep.util.helper import get_dotted_field_value, add_field_to, add_and_overwrite
from logprep.processor.calculator.rule import FIELD_PATTERN


class Requester(Processor):
    """A processor to invoke http requests with field data
    and parses response data to field values"""

    rule_class = RequesterRule

    def _apply_rules(self, event, rule):
        url = rule.url

        try:
            response = requests.request(url=url, method=rule.method, **rule.kwargs)
            response.raise_for_status()
        except requests.HTTPError as error:
            self._handle_warning_error(event, rule, error)

    @staticmethod
    def _template(string: str, source: dict) -> str:
        for key, value in source.items():
            key = key.replace(".", r"\.")
            pattern = r"\$\{(" + rf"{key}" + r")\}"
            string = re.sub(pattern, str(value), string)
        return string
