"""This module contains a Clusterer that clusters events using a heuristic approach."""

from logging import DEBUG, Logger
from multiprocessing import current_process
from typing import List
from logprep.abc.processor import Processor

from logprep.processor.base.rule import Rule
from logprep.processor.clusterer.rule import ClustererRule
from logprep.processor.clusterer.signature_calculation.signature_phase import (
    LogRecord,
    SignatureEngine,
    SignaturePhaseStreaming,
)


class Clusterer(Processor):
    """Cluster log events using a heuristic."""

    matching_rules: List[Rule] = []

    rule_class = ClustererRule

    def __init__(self, name: str, configuration: dict, logger: Logger):
        super().__init__(name=name, configuration=configuration, logger=logger)
        self.sps = SignaturePhaseStreaming()
        self._output_field_name = configuration.get("output_field_name")
        self.has_custom_tests = True

    def process(self, event: dict):
        super().process(event)
        if self._is_clusterable(event):
            self._cluster(event, self.matching_rules)

    def _apply_rules(self, event, rule):
        self.matching_rules.append(rule)

    def _is_clusterable(self, event: dict):
        # The following blocks have not been extracted into functions for performance reasons
        # A message can only be clustered if it exists, despite any other condition
        if "message" not in event:
            return False
        if event["message"] is None:
            return False

        # Return clusterable state if it exists, since it can be true or false
        if "clusterable" in event:
            return event["clusterable"]

        # Alternatively, check for a clusterable tag
        if "tags" in event and "clusterable" in event["tags"]:
            return True

        # It is clusterable if a syslog with PRI exists even if no clusterable field exists
        # has_facility = 'syslog' in event and 'facility' in event['syslog']
        # has_severity = 'event' in event and 'severity' in event['event']
        if self._syslog_has_pri(event):
            return True

        return False

    @staticmethod
    def _syslog_has_pri(event: dict):
        return (
            "syslog" in event
            and "facility" in event["syslog"]
            and "event" in event
            and "severity" in event["event"]
        )

    def _cluster(self, event: dict, rules: List[ClustererRule]):
        cluster_signature_based_on_message = self.sps.run(
            LogRecord(raw_text=event["message"]), rules
        )
        if self._syslog_has_pri(event):
            cluster_signature = " , ".join(
                [
                    str(event["syslog"]["facility"]),
                    str(event["event"]["severity"]),
                    cluster_signature_based_on_message,
                ]
            )
        else:
            cluster_signature = cluster_signature_based_on_message
        event[self._output_field_name] = cluster_signature

    def test_rules(self):
        results = {}
        for _, rule in enumerate(self._rules):
            rule_repr = rule.__repr__()
            results[rule_repr] = []
            try:
                for test in rule.tests:
                    result = SignatureEngine.apply_signature_rule(rule, test["raw"])
                    expected_result = test["result"]
                    results[rule_repr].append((result, expected_result))
            except AttributeError:
                results[rule_repr].append(None)
        return results
