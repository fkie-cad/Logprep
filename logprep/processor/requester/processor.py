"""
Requester
=========

A processor to invoke http requests. Could be usefull to enrich events from an external api or
to trigger external systems by and with event field values.

"""
import requests
from typing import List, Tuple, Any

from logprep.abc import Processor
from logprep.processor.base.exceptions import DuplicationError
from logprep.processor.requester.rule import RequesterRule
from logprep.util.helper import get_dotted_field_value, add_field_to, add_and_overwrite


class Requester(Processor):
    """A processor to invoke http requests with field data
    and parses response data to field values"""

    rule_class = RequesterRule

    def _apply_rules(self, event, rule):
        response = requests.request(url=rule.url, method=rule.method, **rule.kwargs)
        response.raise_for_status()
