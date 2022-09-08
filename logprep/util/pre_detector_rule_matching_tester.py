#!/usr/bin/python3
"""This module is used to test if PreDetector rules match depending on a naming scheme."""

import json
import logging
import sys
import tempfile
from argparse import ArgumentParser
from os import path, sep, walk
from typing import Any, List, Tuple

import regex as re
from colorama import Fore
from ruamel.yaml import YAML, YAMLError
from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.processor.pre_detector.processor import PreDetector
from logprep.processor.pre_detector.rule import PreDetectorRule
from logprep.factory import Factory
from logprep.util.helper import print_fcolor

logger = logging.getLogger()
logger.disabled = True

yaml = YAML(typ="safe", pure=True)


# pylint: disable=protected-access
class MatchingRuleTesterException(BaseException):
    """Base class for MatchingRuleTester related exceptions."""

    def __init__(self, message: str):
        super().__init__(f"MatchingRuleTester ({message}): ")


class TestCollector:
    """Used to collect PreDetector tests for evasion and matching."""

    def __init__(self):
        self.rule_tests = dict()

    def get_rule_tests(self, data_dir: str) -> dict:
        """Get rule test and corresponding input events.

        Parameters
        ----------
        data_dir : str
            Path to directory with files containing rule tests and test inputs.

        Returns
        -------
        rules_with_events : dict
            Rules with corresponding events.

        """
        for root, _, files in walk(data_dir):
            valid_files = [file for file in files if re.search(r"\.(json|jsonl|yml)$", file)]
            for file_name in valid_files:
                self._update_rule_tests(file_name, root)

        rules_with_events = {k: v for k, v in self.rule_tests.items() if v["evasion"] or v["match"]}
        return rules_with_events

    def _update_rule_tests(self, file_name: str, root: str):
        split_path = path.normpath(root).split(sep)
        for idx, part in enumerate(split_path):
            if part == "events":
                self._add_event(file_name, split_path[idx:], root)
                break
            if part == "rules":
                self._add_rule(file_name, split_path[idx:], root)
                break

    def _add_rule(self, file_name: str, rel_path_parts: list, root: str):
        rule_name = file_name.split(".")[0]
        rule_identifier = "/".join(rel_path_parts[1:] + [rule_name])
        abs_path = path.join(root, file_name)

        if rule_identifier not in self.rule_tests:
            self.rule_tests[rule_identifier] = {"rule": None, "match": [], "evasion": []}
        self.rule_tests[rule_identifier]["rule"] = abs_path

    def _add_event(self, file_name: str, rel_path_parts: list, root: str):
        rule_identifier = "/".join(rel_path_parts[1:])
        abs_path = path.join(root, file_name)

        if rule_identifier not in self.rule_tests:
            self.rule_tests[rule_identifier] = {"rule": None, "match": [], "evasion": []}
        if "_Match_" in file_name:
            self.rule_tests[rule_identifier]["match"].append(abs_path)
        elif "_Evasion_" in file_name:
            self.rule_tests[rule_identifier]["evasion"].append(abs_path)


class RuleMatchingTester:
    """Used to test rules for test inputs and to present the results."""

    def __init__(self, rule_tests: dict):
        self._rule_tests = rule_tests
        self._empty_rules_dirs = [tempfile.mkdtemp()]

        self._success = True

        self._errors = []

        self._successful_rule_tests_cnt = 0
        self._failed_rule_tests_cnt = 0

        self._successful_events_cnt = 0
        self._failed_events_cnt = 0

        self._failed_tests = dict()

    def run(self):
        """Begin the test process."""
        try:
            rules = self._get_rules()
            pre_detector = self._get_pre_detector()
            self._run_rule_tests_from_file(pre_detector, rules)
            self._print_results()
        except MatchingRuleTesterException as error:
            print_fcolor(Fore.RED, "Error:")
            print_fcolor(Fore.RED, str(error))

        if not self._success:
            sys.exit(1)

    @staticmethod
    def _get_pre_detector() -> PreDetector:
        # Only needed so processor starts
        processor_cfg = {
            "type": "pre_detector",
            "generic_rules": [],
            "specific_rules": [],
            "tree_config": "",
            "pre_detector_topic": "",
        }

        processor = Factory.create(processor_cfg, logger)
        return processor

    def _print_results(self):
        print_fcolor(Fore.RED, "---- Failed tests ----")
        for failed_test, values in self._failed_tests.items():
            print_fcolor(Fore.RED, "Rule:")
            print_fcolor(Fore.RESET, failed_test)
            if values["match"]:
                print_fcolor(Fore.RED, "Match Events:")
                for event, indices in values["match"].items():
                    print(event)
                    if event.endswith(".jsonl"):
                        self._print_event_numbers(indices)
            if values["evasion"]:
                print_fcolor(Fore.RED, "Evasion Events:")
                for event, indices in values["evasion"].items():
                    print(event)
                    if event.endswith(".jsonl"):
                        self._print_event_numbers(indices)
            print()
        print()

        print_fcolor(Fore.WHITE, "---- Results ----")
        print_fcolor(Fore.RED, f"Failed tests: {self._failed_rule_tests_cnt}")
        print_fcolor(Fore.GREEN, f"Successful tests: {self._successful_rule_tests_cnt}")
        print_fcolor(
            Fore.CYAN,
            f"Total tests: " f"{self._successful_rule_tests_cnt + self._failed_rule_tests_cnt}",
        )
        print_fcolor(Fore.RED, f"Failed events: {self._failed_events_cnt}")
        print_fcolor(Fore.GREEN, f"Successful events: {self._successful_events_cnt}")
        print_fcolor(
            Fore.CYAN, f"Total events: " f"{self._successful_events_cnt + self._failed_events_cnt}"
        )

    @staticmethod
    def _print_event_numbers(indices: List[int]):
        event_numbers = [[]]
        for idx in indices:
            if not event_numbers[-1] or (event_numbers[-1] and idx - event_numbers[-1][-1] == 1):
                event_numbers[-1].append(idx)
            else:
                event_numbers.append([idx])
        event_numbers_compact = ""
        for idx, event_sequence in enumerate(event_numbers):
            if len(event_sequence) == 1:
                event_numbers_compact += str(event_sequence[0] + 1)
            elif len(event_sequence) > 1:
                event_numbers_compact += f"{event_sequence[0] + 1}-{event_sequence[-1] + 1}"
            if idx < len(event_numbers) - 1:
                event_numbers_compact += ", "
        print("Event#:", event_numbers_compact)

    def _run_rule_tests_from_file(self, pre_detector: PreDetector, rules: List[dict]):
        for rule_test in rules:
            if pre_detector and rule_test["rules"] and (rule_test["match"] or rule_test["evasion"]):
                for rule_dict in rule_test["rules"]:
                    rule = PreDetectorRule._create_from_dict(rule_dict)
                    pre_detector._tree.add_rule(rule)
                self._eval_rule_test(rule_test, pre_detector)
                pre_detector._tree = RuleTree()

    def _eval_rule_test(self, rule_test: dict, processor: PreDetector):
        any_match_failed = self._update_test_results("match", processor, rule_test)
        any_evasion_failed = self._update_test_results("evasion", processor, rule_test)

        if any_match_failed or any_evasion_failed:
            self._failed_rule_tests_cnt += 1
        else:
            self._successful_rule_tests_cnt += 1

    def _update_test_results(
        self, event_type: str, processor: PreDetector, rule_test: dict
    ) -> bool:
        index = 0
        any_failed = False
        for to_test, name, event_src in rule_test[event_type]:
            if event_src == "json":
                index = 0

            extra_output = processor.process(to_test)

            if (event_type == "evasion" and extra_output) or (
                event_type == "match" and extra_output is None
            ):
                failed = True
                any_failed = True
            else:
                failed = False

            if failed:
                if rule_test["file"] not in self._failed_tests:
                    self._failed_tests[rule_test["file"]] = {"match": {}, "evasion": {}}
                if name not in self._failed_tests[rule_test["file"]][event_type]:
                    self._failed_tests[rule_test["file"]][event_type][name] = []
                self._failed_tests[rule_test["file"]][event_type][name].append(index)
                self._success = False
                self._failed_events_cnt += 1
            else:
                self._successful_events_cnt += 1
            if event_src == "jsonl":
                index += 1
        return any_failed

    def _get_rules(self) -> List[dict]:
        print_fcolor(Fore.YELLOW, "\nRULES WITH EVENTS:")
        for rule_test in self._rule_tests.values():
            print_fcolor(Fore.YELLOW, rule_test["rule"])
        print()

        rules = list()
        for test in self._rule_tests.values():
            if test["rule"] is None:
                continue

            multi_rule = self._get_multi_rule(test)

            match_events = self._get_test_events("match", test)
            evasion_events = self._get_test_events("evasion", test)

            rules.append(
                {
                    "rules": multi_rule,
                    "match": match_events,
                    "evasion": evasion_events,
                    "file": test["rule"],
                }
            )

        if self._errors:
            for error in self._errors:
                print_fcolor(Fore.RED, error)
            sys.exit(1)
        return rules

    @staticmethod
    def _get_multi_rule(test: dict) -> List[dict]:
        with open(test["rule"], "r", encoding="utf8") as rules_file:
            try:
                if test["rule"].endswith(".yml"):
                    multi_rule = list(yaml.load_all(rules_file))
                else:
                    multi_rule = json.load(rules_file)
            except json.decoder.JSONDecodeError as error:
                raise MatchingRuleTesterException(
                    f'JSON decoder error in rule "{rules_file.name}": "{str(error)}"'
                ) from error
            except YAMLError as error:
                raise MatchingRuleTesterException(
                    'YAML error in rule "{rules_file.name}": "{str(error)}"'
                ) from error
        return multi_rule

    def _get_test_events(self, event_type: str, test: dict) -> List[Tuple[Any, Any, str]]:
        match_events = []
        for match_event in test[event_type]:
            if path.isfile(match_event):
                with open(match_event, "r", encoding="utf8") as test_file:
                    try:
                        if match_event.endswith(".json"):
                            match_events.append((json.load(test_file), match_event, "json"))
                        elif match_event.endswith(".jsonl"):
                            for json_line in test_file:
                                match_events.append((json.loads(json_line), match_event, "jsonl"))
                    except json.decoder.JSONDecodeError as error:
                        self._errors.append(
                            f'JSON decoder error in test "{test_file.name}": "{error}"'
                        )
                        continue
        return match_events

    @staticmethod
    def _is_valid_rule_name(file_name: str) -> bool:
        return (
            file_name.endswith(".json") or file_name.endswith(".yml")
        ) and not file_name.endswith("_test.json")


def _parse_arguments():
    argument_parser = ArgumentParser()
    argument_parser.add_argument("daten", help="Pfad zu den Daten")

    arguments = argument_parser.parse_args()

    return arguments


def main():
    """Starts rule tester for PreDetector rules."""
    args = _parse_arguments()
    data_dir = args.daten

    rule_tester = TestCollector()
    rule_tests = rule_tester.get_rule_tests(data_dir)
    mrt = RuleMatchingTester(rule_tests)
    mrt.run()


if __name__ == "__main__":
    main()
