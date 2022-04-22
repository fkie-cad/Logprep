"""This module contains a Clusterer that clusters events using a heuristic approach."""

from logging import DEBUG, Logger
from multiprocessing import current_process
from typing import List

from logprep.processor.base.processor import RuleBasedProcessor
from logprep.processor.base.rule import Rule
from logprep.processor.clusterer.rule import ClustererRule
from logprep.processor.clusterer.signature_calculation.signature_phase import (
    LogRecord,
    SignatureEngine,
    SignaturePhaseStreaming,
)
from logprep.util.processor_stats import ProcessorStats


class Clusterer(RuleBasedProcessor):
    """Cluster log events using a heuristic."""

    matching_rules: list[Rule] = []

    def __init__(self, name: str, logger: Logger, **configuration):
        tree_config = configuration.get("tree_config")
        specific_rules_dirs = configuration.get("specific_rules")
        generic_rules_dirs = configuration.get("generic_rules")
        super().__init__(name, tree_config, logger)
        self.ps = ProcessorStats()

        self._name = name

        self.sps = SignaturePhaseStreaming()
        self._output_field_name = configuration.get("output_field_name")

        self.has_custom_tests = True

        self.add_rules_from_directory(specific_rules_dirs, generic_rules_dirs)

    def describe(self) -> str:
        return f"Clusterer ({self._name})"

    # pylint: disable=arguments-differ
    def add_rules_from_directory(
        self, specific_rules_dirs: List[str], generic_rules_dirs: List[str]
    ):
        for specific_rules_dir in specific_rules_dirs:
            rule_paths = self._list_json_files_in_directory(specific_rules_dir)
            for rule_path in rule_paths:
                rules = ClustererRule.create_rules_from_file(rule_path)
                for rule in rules:
                    self._specific_tree.add_rule(rule, self._logger)
        for generic_rules_dir in generic_rules_dirs:
            rule_paths = self._list_json_files_in_directory(generic_rules_dir)
            for rule_path in rule_paths:
                rules = ClustererRule.create_rules_from_file(rule_path)
                for rule in rules:
                    self._generic_tree.add_rule(rule, self._logger)
        if self._logger.isEnabledFor(DEBUG):
            self._logger.debug(
                f"{self.describe()} loaded {self._specific_tree.rule_counter} "
                f"specific rules ({current_process().name})"
            )
            self._logger.debug(
                f"{self.describe()} loaded {self._generic_tree.rule_counter} generic rules "
                f"({current_process().name})"
            )
        self.ps.setup_rules(
            [None] * self._generic_tree.rule_counter + [None] * self._specific_tree.rule_counter
        )

    # pylint: enable=W0221

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
