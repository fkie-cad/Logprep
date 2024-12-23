"""
Clusterer
=========

The log clustering is mainly developed for Syslogs, unstructured and semi-structured logs.
The clusterer calculates a log signature based on the message field.
The log signature is calculated with heuristic and deterministic rules.
The idea of a log signature is to extract a subset of the constant parts of a log and
to delete the dynamic parts.
If the fields syslog.facility and event.severity are in the log, then they are prefixed
to the log signature.

Logs are only clustered if at least one of the following criteria is fulfilled:

..  code-block:: yaml

    Criteria 1: { "message": "A sample message", "tags": ["clusterable", ...], ... }
    Criteria 2: { "message": "A sample message", "clusterable": true, ... }
    Criteria 3: { "message": "A sample message", "syslog": { "facility": <number> }, "event": { "severity": <string> }, ... }

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - clusterername:
        type: clusterer
        rules:
            - tests/testdata/rules/rules
        output_field_name: target_field

.. autoclass:: logprep.processor.clusterer.processor.Clusterer.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.clusterer.rule
"""

import math
from typing import Tuple

from attrs import define, field, validators

from logprep.abc.processor import Processor
from logprep.processor.clusterer.rule import ClustererRule
from logprep.processor.clusterer.signature_calculation.signature_phase import (
    LogRecord,
    SignatureEngine,
    SignaturePhaseStreaming,
)
from logprep.processor.field_manager.processor import FieldManager
from logprep.util.helper import add_fields_to, get_dotted_field_value


class Clusterer(FieldManager):
    """Cluster log events using a heuristic."""

    @define(kw_only=True)
    class Config(Processor.Config):
        """Clusterer Configuration"""

        output_field_name: str = field(validator=validators.instance_of(str))
        """defines in which field results of the clustering should be stored."""

    __slots__ = ["sps"]

    sps: SignaturePhaseStreaming

    rule_class = ClustererRule

    def __init__(self, name: str, configuration: Processor.Config):
        super().__init__(name=name, configuration=configuration)
        self.sps = SignaturePhaseStreaming()

        self._last_rule_id = math.inf
        self._last_non_extracted_signature = None

    def _apply_rules(self, event, rule):
        source_field_values = self._get_field_values(event, rule.source_fields)
        self._handle_missing_fields(event, rule, rule.source_fields, source_field_values)
        if self._is_clusterable(event, rule.source_fields[0]):
            self._cluster(event, rule)

    def _is_clusterable(self, event: dict, source_field: str) -> bool:
        # The following blocks have not been extracted into functions for performance reasons
        # A message can only be clustered if it exists or if a clustering step exists
        message = get_dotted_field_value(event, source_field)
        if message is None and self._last_non_extracted_signature is None:
            return False

        # Return clusterable state if it exists, since it can be true or false
        clusterable = get_dotted_field_value(event, "clusterable")
        if clusterable is not None:
            return clusterable

        # Alternatively, check for a clusterable tag
        tags = get_dotted_field_value(event, "tags")
        if tags and "clusterable" in tags:
            return True

        # It is clusterable if a syslog with PRI exists even if no clusterable field exists
        # has_facility = 'syslog' in event and 'facility' in event['syslog']
        # has_severity = 'event' in event and 'severity' in event['event']
        if self._syslog_has_pri(event):
            return True

        return False

    @staticmethod
    def _syslog_has_pri(event: dict):
        syslog_value = get_dotted_field_value(event, "syslog")
        event_value = get_dotted_field_value(event, "event")
        return not (syslog_value is None or event_value is None)

    def _cluster(self, event: dict, rule: ClustererRule):
        raw_text, sig_text = self._get_text_to_cluster(rule, event)
        if raw_text is None:
            return

        record = (
            LogRecord(raw_text=raw_text, sig_text=sig_text)
            if sig_text
            else LogRecord(raw_text=raw_text)
        )

        cluster_signature_based_on_message, sig_text = self.sps.run(record, rule)
        if self._syslog_has_pri(event):
            cluster_signature = " , ".join(
                [
                    str(get_dotted_field_value(event, "syslog.facility")),
                    str(get_dotted_field_value(event, "event.severity")),
                    cluster_signature_based_on_message,
                ]
            )
        else:
            cluster_signature = cluster_signature_based_on_message
        add_fields_to(
            event,
            fields={self._config.output_field_name: cluster_signature},
            merge_with_target=rule.merge_with_target,
            overwrite_target=rule.overwrite_target,
        )
        self._last_non_extracted_signature = sig_text

    def _is_new_tree_iteration(self, rule: ClustererRule) -> bool:
        rule_id = self._rule_tree.get_rule_id(rule)
        if rule_id is None:
            return True
        is_new_iteration = rule_id <= self._last_rule_id
        self._last_rule_id = rule_id
        return is_new_iteration

    def _get_text_to_cluster(self, rule: ClustererRule, event: dict) -> Tuple[str, str]:
        sig_text = None
        if self._is_new_tree_iteration(rule):
            self._last_non_extracted_signature = None
        else:
            sig_text = self._last_non_extracted_signature
        if sig_text is None:
            raw_text = get_dotted_field_value(event, rule.source_fields[0])
        else:
            raw_text = sig_text
        return raw_text, sig_text

    def test_rules(self):
        results = {}
        for _, rule in enumerate(self.rules):
            rule_repr = rule.__repr__()
            results[rule_repr] = []
            try:
                for test in rule.tests:
                    result = SignatureEngine.apply_signature_rule(test["raw"], rule)
                    expected_result = test["result"]
                    results[rule_repr].append((result, expected_result))
            except AttributeError:
                results[rule_repr].append(None)
        return results
