#!/usr/bin/python3
"""
Rule Tests
----------

It is possible to write tests for rules.
In those tests it is possible to define inputs and expected outputs for these inputs.
Only one test file can exist per rule file.
The tests must be located in the same directory as the rule files.
They are identified by naming them like the rule, but ending with `_test.json`.
For example `rule_one.json` and `rule_one_test.json`.

The rule file must contain a JSON list of JSON objects.
Each object corresponds to a test.
They must have the fields `raw` and `processed`.
`raw` contains an input log message and `processed` the corresponding processed result.

When using multi-rules it may be necessary to restrict tests to specific rules in the file.
This can be achieved by the field `target_rule_idx`.
The value of that field corresponds to the index of the rule in the JSON list of multi-rules
(starting with 0).

Logprep gets the events in `raw` as input.
The result will be compared with the content of `processed`.

Fields with variable results can be matched via regex expressions by appending `|re` to a field
name and using a regex expression as value.
It is furthermore possible to use GROK patterns.
Some patterns are pre-defined, but others can be added by adding a directory with GROK patterns to
the configuration file.

The rules get automatically validated if an auto-test is being executed.
The rule tests will be only performed if the validation was successful.

The output is printed to the console, highlighting differences between `raw` and `processed`:

..  code-block:: bash
    :caption: Directly with Python

    PYTHONPATH="." python3 logprep/run_logprep.py test unit $CONFIG

..  code-block:: bash
    :caption: With PEX file

    logprep.pex test unit $CONFIG

Where :code:`$CONFIG` is the path to a configuration file
(see :ref:`configuration`).

Auto-testing does also perform a verification of the pipeline section of the Logprep configuration.
"""

import hashlib
import json
import re
import sys
import tempfile
import traceback
from collections import OrderedDict, defaultdict
from contextlib import redirect_stdout
from difflib import ndiff
from io import StringIO
from logging import getLogger
from os import path, walk
from pprint import pprint
from typing import TYPE_CHECKING, TextIO, Tuple

from colorama import Fore
from ruamel.yaml import YAML, YAMLError

from logprep.factory import Factory
from logprep.framework.rule_tree.rule_tree import RuleTree
from logprep.processor.pre_detector.processor import PreDetector
from logprep.util.auto_rule_tester.grok_pattern_replacer import GrokPatternReplacer
from logprep.util.helper import print_fcolor, remove_file_if_exists

if TYPE_CHECKING:
    from logprep.abc.processor import Processor


yaml = YAML(typ="safe", pure=True)


# pylint: disable=protected-access
class AutoRuleTesterException(BaseException):
    """Base class for AutoRuleTester related exceptions."""

    def __init__(self, message: str):
        super().__init__(f"AutoRuleTester ({message}): ")


class PreDetectionExtraHandler:
    """Used to handle special demands for PreDetector auto-tests."""

    @staticmethod
    def _get_errors(processor: "Processor", extra_output: tuple):
        pd_errors = []
        pd_warnings = []
        if isinstance(processor, PreDetector):
            if not extra_output:
                return pd_errors, pd_warnings

            pre_detection_extra_out = extra_output[0][0]
            mitre_out = pre_detection_extra_out.get("mitre")
            id_out = pre_detection_extra_out.get("id")

            mitre_pattern = r"^.*\.(t|T)\d{4}(\.\d{3})?$"
            uuid_pattern = r"^[a-fA-F0-9]{8}-(?:[a-fA-F0-9]{4}-){3}[a-fA-F0-9]{12}$"

            if not re.search(uuid_pattern, id_out):
                pd_warnings.append(f'Warning in extra output: "id: {id_out}" is not a valid UUID!')

            if "pre_detection_id" not in pre_detection_extra_out:
                pd_errors.append('Error in extra output: "id" field does not exist!')

            if "mitre" not in pre_detection_extra_out:
                pd_errors.append('Error in extra output: "mitre" field does not exist!')
            elif not any(
                (technique for technique in mitre_out if re.search(mitre_pattern, technique))
            ):
                pd_errors.append(
                    f'Error in extra output: "mitre: {mitre_out}" does not include a valid mitre '
                    f"attack technique! "
                )
        return pd_errors, pd_warnings

    def update_errors(
        self, processor: PreDetector, extra_output: tuple, errors: list, warnings: list
    ):
        """Create aggregating logger.

        Parameters
        ----------
        processor : PreDetector
            Processor that should be of type PreDetector.
        extra_output : dict
            Extra output containing MITRE information coming from PreDetector.
        errors : list
            List of errors.
        warnings : list
            List of warnings.

        """
        mitre_errors, id_warnings = self._get_errors(processor, extra_output)
        errors += mitre_errors
        warnings += id_warnings


class AutoRuleTester:
    """Used to perform auto-tests for rules."""

    def __init__(self, config):
        with open(config, "r", encoding="utf8") as yaml_file:
            self._config_yml = yaml.load(yaml_file)

        self._empty_rules_dirs = [tempfile.mkdtemp()]

        self._config_yml["connector"] = {"type": "dummy"}
        self._config_yml["process_count"] = 1
        self._config_yml["timeout"] = 0.1

        self._enable_print_stack_trace = self._config_yml.get("print_auto_test_stack_trace", True)

        self._success = True

        self._successful_rule_tests_cnt = 0
        self._failed_rule_tests_cnt = 0
        self._warning_cnt = 0

        self._pd_extra = PreDetectionExtraHandler()

        self._filename_printed = False

        self._gpr = GrokPatternReplacer(self._config_yml)

        self._custom_tests_output = ""
        self._custom_tests = []
        self._missing_custom_tests = []

        self._logger = getLogger()
        self._logger.disabled = True

    def run(self):
        """Perform auto-tests."""
        rules_dirs = self._get_rule_dirs_by_processor_name()
        rules_pn = self._get_rules_per_processor_name(rules_dirs)
        self._run_if_any_rules_exist(rules_pn)

    def _run_if_any_rules_exist(self, rules_pn: dict):
        if not self._has_rules(rules_pn):
            print_fcolor(Fore.YELLOW, "\nThere are no rules within any of the rules directories!")
        else:
            self._run_tests_for_rules(rules_pn)

    def _run_tests_for_rules(self, rules_pn: dict):
        rule_test_coverage = self._check_which_rule_files_miss_tests(rules_pn)
        self._set_rules_dirs_to_empty()

        processors_ct, processors_no_ct = self._get_processors_split_by_custom_tests_existence()

        for processor, processor_name in processors_ct.items():
            for rule_test in rules_pn[processor_name]["rules"]:
                if processor and rule_test["tests"] or processor.has_custom_tests:
                    self._run_custom_rule_tests(processor, rule_test)

        if self._custom_tests:
            print_fcolor(Fore.GREEN, "\nRULES WITH CUSTOM TESTS:")
            for file_name in self._custom_tests:
                print_fcolor(Fore.GREEN, file_name)

        if self._missing_custom_tests:
            print_fcolor(Fore.RED, "\nRULES WITHOUT CUSTOM TESTS:")
            for file_name in self._missing_custom_tests:
                print_fcolor(Fore.RED, file_name)

        print(self._custom_tests_output)

        for processor, processor_name in processors_no_ct.items():
            for rule_test in rules_pn[processor_name]["rules"]:
                if processor and rule_test["tests"]:
                    self._run_file_rule_tests(processor, rule_test)

        print_fcolor(Fore.WHITE, "\nResults:")
        print_fcolor(Fore.RED, f"Failed tests: {self._failed_rule_tests_cnt}")
        print_fcolor(Fore.GREEN, f"Successful tests: {self._successful_rule_tests_cnt}")
        print_fcolor(
            Fore.CYAN,
            f"Total tests: " f"{self._successful_rule_tests_cnt + self._failed_rule_tests_cnt}",
        )
        print_fcolor(Fore.BLUE, f"Rule Test Coverage: {rule_test_coverage:.2f}%")
        print_fcolor(Fore.YELLOW, f"Warnings: {self._warning_cnt}")

        if not self._success:
            sys.exit(1)

    @staticmethod
    def _has_rules(rules_pn: dict) -> bool:
        for processor_test_cfg in rules_pn.values():
            if processor_test_cfg["rules"]:
                return True
        return False

    def _get_processors_split_by_custom_tests_existence(self) -> Tuple[OrderedDict, OrderedDict]:
        processors_with_custom_test = OrderedDict()
        processors_without_custom_test = OrderedDict()
        for processor_in_pipeline in self._config_yml["pipeline"]:
            name, processor_cfg = next(iter(processor_in_pipeline.items()))
            processor = self._get_processor_instance(name, processor_cfg, self._logger)
            if processor.has_custom_tests:
                processors_with_custom_test[processor] = name
            else:
                processors_without_custom_test[processor] = name
        return processors_with_custom_test, processors_without_custom_test

    def _get_custom_test_mapping(self) -> dict:
        processor_uses_own_tests = {}
        for processor_in_pipeline in self._config_yml["pipeline"]:
            name, processor_cfg = next(iter(processor_in_pipeline.items()))
            processor = self._get_processor_instance(name, processor_cfg, self._logger)
            processor_uses_own_tests[processor_cfg["type"]] = processor.has_custom_tests
        return processor_uses_own_tests

    @staticmethod
    def _get_rules(processor: "Processor", rule_test: dict) -> dict:
        if rule_test.get("rules"):
            return {"rules": rule_test.get("rules", [])}
        if rule_test.get("specific_rules") or rule_test.get("generic_rules"):
            result = {}
            if rule_test.get("specific_rules"):
                result["specific_rules"] = rule_test.get("specific_rules", [])
            if rule_test.get("generic_rules"):
                result["generic_rules"] = rule_test.get("generic_rules", [])
            return result
        raise AutoRuleTesterException(
            f"No rules provided for processor of type {processor.describe()}"
        )

    def _load_rules(self, processor: "Processor", rule_type: str):
        if rule_type == "rules":
            processor.load_rules(self._empty_rules_dirs)
        elif rule_type == "specific_rules":
            processor.load_rules(self._empty_rules_dirs, [])
        elif rule_type == "generic_rules":
            processor.load_rules([], self._empty_rules_dirs)
        processor.setup()

    def _prepare_test_eval(
        self, processor: "Processor", rule_dict: dict, rule_type: str, temp_rule_path: str
    ):
        self._create_rule_file(rule_dict, temp_rule_path)
        self._reset_trees(processor)
        self._clear_rules(processor)
        self._load_rules(processor, rule_type)

    def _run_custom_rule_tests(self, processor: "Processor", rule_test: dict):
        temp_rule_path = path.join(self._empty_rules_dirs[0], f"{hashlib.sha256()}.json")
        rules = self._get_rules(processor, rule_test)

        for rule_type, rules in rules.items():
            for rule_dict in rules:
                self._prepare_test_eval(processor, rule_dict, rule_type, temp_rule_path)
                self._eval_custom_rule_test(rule_test, processor)
                remove_file_if_exists(temp_rule_path)

    def _run_file_rule_tests(self, processor: "Processor", rule_test: dict):
        temp_rule_path = path.join(self._empty_rules_dirs[0], f"{hashlib.sha256()}.json")
        rules = self._get_rules(processor, rule_test)

        for rule_type, rules in rules.items():
            for idx, rule_dict in enumerate(rules):
                self._prepare_test_eval(processor, rule_dict, rule_type, temp_rule_path)
                self._eval_file_rule_test(rule_test, processor, idx)
                remove_file_if_exists(temp_rule_path)

    @staticmethod
    def _clear_rules(processor: "Processor"):
        if hasattr(processor, "_rules"):
            processor.rules.clear()

    @staticmethod
    def _reset_trees(processor: "Processor"):
        if hasattr(processor, "_tree"):
            processor._tree = RuleTree()
        if hasattr(processor, "_specific_tree"):
            processor._specific_tree = RuleTree()
        if hasattr(processor, "_generic_tree"):
            processor._generic_tree = RuleTree()

    @staticmethod
    def _create_rule_file(rule_dict: dict, rule_path: str):
        with open(rule_path, "w", encoding="utf8") as temp_file:
            json.dump([rule_dict], temp_file)

    def _print_error_on_exception(self, error: BaseException, rule_test: dict, t_idx: int):
        self._print_filename(rule_test)
        print_fcolor(Fore.MAGENTA, f"RULE {t_idx}:")
        print_fcolor(Fore.RED, f"Exception: {error}")
        self._print_stack_trace(error)

    def _print_stack_trace(self, error: BaseException):
        if self._enable_print_stack_trace:
            print("Stack Trace:")
            tbk = traceback.format_tb(error.__traceback__)
            for line in tbk:
                print(line)

    def _print_filename(self, rule_test: dict):
        if not self._filename_printed:
            print_fcolor(Fore.LIGHTMAGENTA_EX, f'\nRULE FILE {rule_test["file"]}')
            self._filename_printed = True

    def _eval_custom_rule_test(self, rule_test: dict, processor: "Processor"):
        self._filename_printed = False
        with StringIO() as buf, redirect_stdout(buf):
            self._run_custom_tests(processor, rule_test)
            self._custom_tests_output += buf.getvalue()

    def _eval_file_rule_test(self, rule_test: dict, processor: "Processor", r_idx: int):
        self._filename_printed = False

        for t_idx, test in enumerate(rule_test["tests"]):
            if test.get("target_rule_idx") is not None and test.get("target_rule_idx") != r_idx:
                continue

            try:
                extra_output = processor.process(test["raw"])
            except BaseException as error:
                self._print_error_on_exception(error, rule_test, t_idx)
                self._success = False
                self._failed_rule_tests_cnt += 1
                return

            diff = self._get_diff_raw_test(test)
            print_diff = self._check_if_different(diff)

            errors = []
            warnings = []

            if isinstance(processor, PreDetector):
                self._pd_extra.update_errors(processor, extra_output, errors, warnings)

            if print_diff or warnings or errors:
                self._print_filename(rule_test)
                print_fcolor(Fore.MAGENTA, f"RULE {t_idx}:")

            if print_diff:
                self._print_filename(rule_test)
                self._print_diff_test(diff)

            if print_diff or errors:
                self._success = False
                self._failed_rule_tests_cnt += 1
            else:
                self._successful_rule_tests_cnt += 1

            self._warning_cnt += len(warnings)

            self._print_errors_and_warnings(errors, warnings)

    def _run_custom_tests(self, processor, rule_test):
        results_for_all_rules = processor.test_rules()
        results = results_for_all_rules.get(processor.rules[0].__repr__(), [])
        if not results:
            self._missing_custom_tests.append(rule_test["file"])
        else:
            self._custom_tests.append(rule_test["file"])
        for idx, result in enumerate(results):
            diff = list(ndiff([result[0]], [result[1]]))
            if self._check_if_different(diff):
                if not self._filename_printed:
                    self._print_filename(rule_test)
                print(f"{processor.__class__.__name__.upper()} SPECIFIC TEST #{idx}:")
                self._print_diff_test(diff)
                self._failed_rule_tests_cnt += 1
                self._success = False
            else:
                self._successful_rule_tests_cnt += 1

    @staticmethod
    def _print_errors_and_warnings(errors, warnings):
        for error in errors:
            print_fcolor(Fore.RED, error)

        for warning in warnings:
            print_fcolor(Fore.YELLOW, warning)

    @staticmethod
    def _check_if_different(diff):
        return any((item for item in diff if item.startswith(("+", "-", "?"))))

    def _check_which_rule_files_miss_tests(self, rules_pn):
        custom_test_mapping = self._get_custom_test_mapping()
        rules_with_tests = []
        rules_without_tests = []
        for _, processor_test_cfg in rules_pn.items():
            processor_type = processor_test_cfg["type"]
            rules = processor_test_cfg["rules"]

            has_custom_tests = custom_test_mapping.get(processor_type, False)
            if has_custom_tests:
                continue

            for rule in rules:
                if rule["tests"]:
                    rules_with_tests.append(rule["file"])
                else:
                    rules_without_tests.append(rule["file"])

        rule_test_coverage = (
            len(rules_with_tests) / (len(rules_with_tests) + len(rules_without_tests)) * 100
        )

        print_fcolor(Fore.LIGHTGREEN_EX, "\nRULES WITH TESTS:")
        for rule in rules_with_tests:
            print_fcolor(Fore.LIGHTGREEN_EX, f"  {rule}")
        if not rules_with_tests:
            print_fcolor(Fore.LIGHTGREEN_EX, "None")
        print_fcolor(Fore.LIGHTRED_EX, "\nRULES WITHOUT TESTS:")
        for rule in rules_without_tests:
            print_fcolor(Fore.LIGHTRED_EX, f"  {rule}")
        if not rules_without_tests:
            print_fcolor(Fore.LIGHTRED_EX, "None")

        return rule_test_coverage

    @staticmethod
    def _get_processor_instance(name, processor_cfg, logger_):
        cfg = {name: processor_cfg}
        processor = Factory.create(cfg, logger_)
        return processor

    @staticmethod
    def _print_diff_test(diff):
        for item in diff:
            if item.startswith("- "):
                print_fcolor(Fore.RED, item)
            elif item.startswith("+ "):
                print_fcolor(Fore.GREEN, item)
            elif item.startswith("? "):
                print_fcolor(Fore.WHITE, item)
            else:
                print_fcolor(Fore.CYAN, item)

    def _sort_lists_in_nested_dict(self, nested_dict):
        for key, value in nested_dict.items():
            if isinstance(value, dict):
                self._sort_lists_in_nested_dict(value)
            elif isinstance(value, list):
                nested_dict[key] = sorted(nested_dict[key])

    def _get_diff_raw_test(self, test: dict) -> list:
        self._gpr.replace_grok_keywords(test["processed"], test)

        self._sort_lists_in_nested_dict(test)

        raw = json.dumps(test["raw"], sort_keys=True, indent=4)
        processed = json.dumps(test["processed"], sort_keys=True, indent=4)

        diff = ndiff(raw.splitlines(), processed.splitlines())
        return list(diff)

    def _set_rules_dirs_to_empty(self):
        for processor in self._config_yml["pipeline"]:
            processor_cfg = next(iter(processor.values()))

            if processor_cfg.get("rules"):
                processor_cfg["rules"] = self._empty_rules_dirs
            elif processor_cfg.get("generic_rules") and processor_cfg.get("specific_rules"):
                processor_cfg["generic_rules"] = self._empty_rules_dirs
                processor_cfg["specific_rules"] = self._empty_rules_dirs

    @staticmethod
    def _check_test_validity(errors: list, rule_tests: list, test_file: TextIO) -> bool:
        has_errors = False
        for rule_test in rule_tests:
            rule_keys = set(rule_test.keys())
            valid_keys = {"raw", "processed", "target_rule_idx"}
            required_keys = {"raw", "processed"}
            invalid_keys = rule_keys.difference(valid_keys)
            has_error = False

            if invalid_keys.difference({"target_rule_idx"}):
                errors.append(
                    f'Schema error in test "{test_file.name}": "Remove keys: {invalid_keys}"'
                )
                has_error = True

            available_required_keys = rule_keys.intersection(required_keys)
            if available_required_keys != required_keys:
                errors.append(
                    f'Schema error in test "{test_file.name}": "The following required keys are '
                    f'missing: {required_keys.difference(available_required_keys)}"'
                )
                has_error = True

            if not has_error:
                if not isinstance(rule_test.get("raw"), dict) or not isinstance(
                    rule_test.get("processed"), dict
                ):
                    errors.append(
                        f'Schema error in test "{test_file.name}": "Values of raw and processed '
                        f'must be dictionaries"'
                    )
                    has_error = True
                if {"target_rule_idx"}.intersection(rule_keys):
                    if not isinstance(rule_test.get("target_rule_idx"), int):
                        errors.append(
                            f'Schema error in test "{test_file.name}": "Value of target_rule_idx '
                            f'must be an integer"'
                        )
                        has_error = True
            has_errors = has_errors or has_error
        return has_errors

    def _get_rules_per_processor_name(self, rules_dirs: dict) -> defaultdict:
        print_fcolor(Fore.YELLOW, "\nRULES DIRECTORIES:")
        rules_pn = defaultdict(dict)
        errors = []

        for processor_name, proc_rules_dirs in rules_dirs.items():
            self._get_rules_for_processor(processor_name, proc_rules_dirs, rules_pn, errors)
        if errors:
            for error in errors:
                print_fcolor(Fore.RED, error)
            sys.exit(1)
        return rules_pn

    def _get_rules_for_processor(self, processor_name, proc_rules_dirs, rules_pn, errors):
        if not rules_pn[processor_name]:
            rules_pn[processor_name] = defaultdict(dict)
        processor_type = proc_rules_dirs["type"]
        rules_pn[processor_name]["type"] = processor_type
        rules_pn[processor_name]["rules"] = []
        print_fcolor(Fore.YELLOW, f"  {processor_name} ({processor_type}):")
        for rule_dirs_type, rules_dirs_by_type in proc_rules_dirs["rule_dirs"].items():
            print_fcolor(Fore.YELLOW, f"    {rule_dirs_type}:")
            for rules_dir in rules_dirs_by_type:
                print_fcolor(Fore.YELLOW, f"      {rules_dir}:")
                for root, _, files in walk(rules_dir):
                    rule_files = [file for file in files if self._is_valid_rule_name(file)]
                    for file in rule_files:
                        multi_rule = self._get_multi_rule_dict(file, root)
                        test_path = path.join(
                            root, "".join([file.rsplit(".", maxsplit=1)[0], "_test.json"])
                        )
                        if path.isfile(test_path):
                            with open(test_path, "r", encoding="utf8") as test_file:
                                try:
                                    rule_tests = json.load(test_file)
                                except json.decoder.JSONDecodeError as error:
                                    errors.append(
                                        f"JSON decoder error in test "
                                        f'"{test_file.name}": "{str(error)}" '
                                    )
                                    continue
                                has_errors = self._check_test_validity(
                                    errors, rule_tests, test_file
                                )
                                if has_errors:
                                    continue
                        else:
                            rule_tests = []
                        rules_pn[processor_name]["rules"].append(
                            {
                                rule_dirs_type: multi_rule,
                                "tests": rule_tests,
                                "file": path.join(root, file),
                            }
                        )

    @staticmethod
    def _get_multi_rule_dict(file, root):
        with open(path.join(root, file), "r", encoding="utf8") as rules_file:
            try:
                multi_rule = (
                    list(yaml.load_all(rules_file))
                    if file.endswith(".yml")
                    else json.load(rules_file)
                )
            except json.decoder.JSONDecodeError as error:
                raise AutoRuleTesterException(
                    f'JSON decoder error in rule "{rules_file.name}": ' f'"{str(error)}"'
                ) from error
            except YAMLError as error:
                raise AutoRuleTesterException(
                    f"YAML error in rule " f'"{rules_file.name}": ' f'"{error}"'
                ) from error
        return multi_rule

    @staticmethod
    def _is_valid_rule_name(file_name: str) -> bool:
        return (file_name.endswith(".json") or file_name.endswith(".yml")) and not (
            file_name.endswith("_test.json")
        )

    def _get_rule_dirs_by_processor_name(self) -> defaultdict:
        rules_dirs = defaultdict(dict)
        for processor in self._config_yml["pipeline"]:
            processor_name, processor_cfg = next(iter(processor.items()))

            rules_to_add = []
            print("\nProcessor Config:")
            pprint(processor_cfg)

            if processor_cfg.get("rules"):
                rules_to_add.append(("rules", processor_cfg["rules"]))
            elif processor_cfg.get("generic_rules") and processor_cfg.get("specific_rules"):
                rules_to_add.append(("generic_rules", processor_cfg["generic_rules"]))
                rules_to_add.append(("specific_rules", processor_cfg["specific_rules"]))

            if not rules_dirs[processor_name]:
                rules_dirs[processor_name] = defaultdict(dict)

            rules_dirs[processor_name]["type"] = processor_cfg["type"]

            if not rules_dirs[processor_name]["rule_dirs"]:
                rules_dirs[processor_name]["rule_dirs"] = defaultdict(list)

            for rule_to_add in rules_to_add:
                rules_dirs[processor_name]["rule_dirs"][rule_to_add[0]] += rule_to_add[1]

        return rules_dirs
