"""
Requester
=========

A processor to invoke http requests. Can be used to enrich events from an external api or
to trigger external systems by and with event field values.

.. security-best-practice::
   :title: Processor - Requester

   As the `requester` can execute arbitrary http requests it is advised to execute requests only
   against known and trusted endpoints and that the communication is protected with a valid
   SSL-Certificate. Do so by setting a certificate path with the option :code:`cert`.
   To ensure that the communication is trusted it is also recommended to set either an
   :code:`Authorization`-Header or a corresponding authentication with a username and password, via
   :code:`auth`.

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - requestername:
        type: requester
        rules:
            - tests/testdata/rules/rules

.. autoclass:: logprep.processor.requester.processor.Requester.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.requester.rule
"""

import json

import requests

from logprep.processor.base.exceptions import FieldExistsWarning
from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.requester.rule import RequesterRule
from logprep.util.helper import (
    add_fields_to,
    create_template_resolver,
    get_source_fields_dict,
    transform_field_value,
)

TEMPLATE_KWARGS = ("url", "json", "data", "params")


class Requester(FieldManager):
    """A processor to invoke http requests with field data
    and parses response data to field values"""

    rule_class = RequesterRule

    def _apply_rules(self, event, rule):
        source_field_dict = get_source_fields_dict(event, rule)
        if self._handle_missing_fields(event, rule, rule.source_fields, source_field_dict.values()):
            return
        if self._has_missing_values(event, rule, source_field_dict):
            return
        kwargs = self._template_kwargs(rule.kwargs, source_field_dict)
        response = self._request(event, rule, kwargs)
        if response is not None:
            self._handle_response(event, rule, response)

    def _handle_response(self, event, rule, response):
        conflicting_fields = []
        if rule.target_field:
            try:
                add_fields_to(
                    event,
                    fields={rule.target_field: self._get_result(response)},
                    rule=rule,
                    merge_with_target=rule.merge_with_target,
                    overwrite_target=rule.overwrite_target,
                )
            except FieldExistsWarning as error:
                conflicting_fields.extend(error.skipped_fields)
        if rule.target_field_mapping:
            source_fields = rule.target_field_mapping.keys()
            contents = self._get_field_values(self._get_result(response), source_fields)
            targets = rule.target_field_mapping.values()
            try:
                add_fields_to(
                    event,
                    dict(zip(targets, contents)),
                    rule,
                    rule.merge_with_target,
                    rule.overwrite_target,
                )
            except FieldExistsWarning as error:
                conflicting_fields.extend(error.skipped_fields)
        if conflicting_fields:
            raise FieldExistsWarning(rule, event, conflicting_fields)

    def _request(self, event, rule, kwargs):
        try:
            response = requests.request(**kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as error:
            self._handle_warning_error(event, rule, error)
        except requests.exceptions.ConnectTimeout as error:
            self._handle_warning_error(event, rule, error)
        return None

    @staticmethod
    def _get_result(response):
        try:
            result = json.loads(response.content)
        except json.JSONDecodeError:
            result = response.content.decode("utf-8")
        return result

    def _template_kwargs(self, kwargs: dict, source: dict):
        template_resolver = create_template_resolver(source)
        for key, value in kwargs.items():
            if key in TEMPLATE_KWARGS:
                kwargs[key] = transform_field_value(
                    transform_key=template_resolver,
                    transform_value=lambda d: template_resolver(d) if isinstance(d, str) else d,
                    data=value,
                )
        return kwargs
