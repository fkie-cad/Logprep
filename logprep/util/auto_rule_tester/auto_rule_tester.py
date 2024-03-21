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
from collections.abc import Iterable

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


class PorcessorExtensions:
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
        self, processor: PreDetector, extra_output: tuple, problems: dict
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
        problems["errors"].extend(mitre_errors) 
        problems["warnings"].extend(id_warnings) 

    def print_rules(self, rules, t_idx=None):       
        print()
        for key, rule in rules.items():
            self._print_diff_test(key, rule, t_idx)
        #else:
        #        print_fcolor(Fore.LIGHTRED_EX, "None")

    @staticmethod
    def _print_diff_test( key, rule, t_idx=None):
        if not isinstance(rule, Iterable):  
            diff = f"{key}: {rule}"
            PorcessorExtensions.color_based_print(diff)
        else:
            if t_idx is not None:
                diff = f"{key}: {rule[t_idx]}"
                PorcessorExtensions.color_based_print(diff)
            else:
                for item in rule:
                    diff = f"{key}: {item}"
                    PorcessorExtensions.color_based_print(diff)

    @staticmethod
    def color_based_print(item):
        item = item.replace("]", "").replace("[", "")
        if item.startswith("- ") or item.startswith("error") or item.startswith("without tests"):
            print_fcolor(Fore.RED, item) #+ "\n")
        elif item.startswith("+ ") or item.startswith("with tests"):
            print_fcolor(Fore.GREEN,  item)
        elif item.startswith("? "):
            print_fcolor(Fore.WHITE, "\n" + item)
        elif item.lstrip().startswith("~ ") or item.startswith("warning"):
            print_fcolor(Fore.YELLOW, item)
        else:
            print_fcolor(Fore.CYAN, item)

    def _load_json_or_yaml(self, file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                if file_path.endswith(".yml"):
                    return list(yaml.load_all(file))
                else:
                    return json.load(file)
                    
        except (json.JSONDecodeError, YAMLError) as error:
            raise ValueError(f"Error decoding {file_path}: {str(error)}")


class AutoRuleTester:
    """Used to perform auto-tests for rules."""

    _original_config_paths: tuple[str]
    """ Path to the original configuration that should be tested """

    def __init__(self, config_paths: tuple[str])
        self._original_config_paths = config_paths
        
        with open(config_paths, "r", encoding="utf8") as yaml_file:
            self._config_yml = yaml.load(yaml_file)

        self._empty_rules_dirs = [tempfile.mkdtemp()]

        self._config_yml["connector"] = {"type": "dummy"}
        self._config_yml["process_count"] = 1
        self._config_yml["timeout"] = 0.1

        self._enable_print_stack_trace = self._config_yml.get("print_auto_test_stack_trace", True)

        self._success = True

        self._result = {"+ successful_rule_tests_cnt": 0, "- failed_rule_tests_cnt": 0, "~ warning_cnt": 0, "rule_test_coverage": 0, "total_tests": 0} 
        self._problems = {"warnings": [], "errors": []}

        self._pd_extra = PorcessorExtensions()
        self._gpr = GrokPatternReplacer(self._config_yml)

        self._filename_printed = False
        self._rule_cnt = 0

        self._logger = getLogger()
        self._logger.disabled = True

    def run(self):
        """Perform auto-tests."""
        rules_dirs = self._get_rule_dirs_by_processor_name()
        rules_pn = self._get_rules_per_processor_name(rules_dirs)
        self._run_if_any_rules_exist(rules_pn)

    def _run_if_any_rules_exist(self, rules_pn: dict):
        if any(processor_test_cfg["rules"] for processor_test_cfg in rules_pn.values()):
            self._run_tests_for_rules(rules_pn)
            return
        else:
            print_fcolor(Fore.YELLOW, "~\nThere are no rules within any of the rules directories!")

    def check_run_rule_tests(self, processor_cont, rules_pn, test_type):
        for processor, processor_name in processor_cont.items():
            for rule_test in rules_pn[processor_name]["rules"]:
                if processor and rule_test["tests"]:
                    self._run_rule_tests(processor, rule_test, test_type)

    def _run_tests_for_rules(self, rules_pn: dict):
        self._check_which_rule_files_miss_tests(rules_pn)
        #self._set_rules_dirs_to_empty()

        processors_no_ct = self._get_processors()

        self.check_run_rule_tests(processors_no_ct, rules_pn, "file")

        self._result["~ warning_cnt"] += len(self._problems.get("warnings") )
        self._pd_extra.print_rules(self._result) 

        if not self._success:
            sys.exit(1)

    def _run_rule_tests(self, processor: "Processor", rule_test: dict, test_type: str):
            temp_rule_path = path.join(self._empty_rules_dirs[0], f"{hashlib.sha256()}.json")
            rules = self._get_rules(processor, rule_test)

            for rule_type, rules in rules.items():
                for idx, rule_dict in enumerate(rules):
                    self._prepare_test_eval(processor, rule_dict, rule_type, temp_rule_path)
                    self._eval_file_rule_test(rule_test, processor, idx)
                    remove_file_if_exists(temp_rule_path)

    def _get_processors(self) -> Tuple[OrderedDict, OrderedDict]:
        processors_without_custom_test = OrderedDict()
        for processor_in_pipeline in self._config_yml["pipeline"]:
            name, processor_cfg = next(iter(processor_in_pipeline.items()))
            processor = self._get_processor_instance(name, processor_cfg, self._logger)
            processors_without_custom_test[processor] = name
        return processors_without_custom_test

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
        self._reset_(processor)
        self._load_rules(processor, rule_type)

    def _eval_file_rule_test(self, rule_test: dict, processor: "Processor", r_idx: int):
        self._filename_printed = False
        for t_idx, test in enumerate(rule_test["tests"]):
            if test.get("target_rule_idx") is not None and test.get("target_rule_idx") != r_idx:
                continue
            try:
                extra_output = processor.process(test["raw"])
            except BaseException as error:
                self._print_error_on_exception(error, rule_test, self._rule_cnt)
                self._success = False
                self._result["- failed_rule_tests_cnt"] += 1
                return

            diff = self._get_diff_raw_test(test)
            print_diff = self._check_if_different(diff)

            if isinstance(processor, PreDetector):
                self._pd_extra.update_errors(processor, extra_output, self._problems)

            if print_diff or self._problems.get("warnings") or self._problems.get("errors"):
                print_fcolor(Fore.MAGENTA, f"RULE FILE {rule_test['file']} & RULE {t_idx}:")

            if print_diff or self._problems.get("errors"):
                self._pd_extra.print_rules({"DIFF": diff})
                self._success = False
                self._result["- failed_rule_tests_cnt"] += 1
            else:
                self._result["+ successful_rule_tests_cnt"] += 1 

            self._pd_extra.print_rules(self._problems, self._rule_cnt)

        self._rule_cnt += 1 
        self._result["total_tests"] = self._result["+ successful_rule_tests_cnt"] + self._result["- failed_rule_tests_cnt"]

    @staticmethod
    def _reset_(processor: "Processor"):
        if hasattr(processor, "_rules"):
            processor.rules.clear()
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
        print_fcolor(Fore.MAGENTA, f"RULE FILE {rule_test['file']} & RULE {t_idx}:")
        print_fcolor(Fore.RED, f"Exception: {error}")
        self._print_stack_trace(error)

    def _print_stack_trace(self, error: BaseException):
        if self._enable_print_stack_trace:
            print("Stack Trace:")
            tbk = traceback.format_tb(error.__traceback__)
            for line in tbk:
                print(line)

    @staticmethod
    def _check_if_different(diff):
        return any((item for item in diff if item.startswith(("+", "-", "?"))))

    @staticmethod
    def _get_processor_instance(name, processor_cfg, logger_):
        cfg = {name: processor_cfg}
        processor = Factory.create(cfg, logger_)
        return processor

    def _check_which_rule_files_miss_tests(self, rules_pn):

        rule_tests = {"with tests": [], "without tests": []}
        for _, processor_test_cfg in rules_pn.items():
            processor_type = processor_test_cfg["type"]
            rules = processor_test_cfg["rules"]
            
            for rule in rules:
                if rule["tests"]:
                    rule_tests["with tests"].append(rule["file"])
                else:
                    rule_tests["without tests"].append(rule["file"])

        self._result["rule_test_coverage"] = (
            len(rule_tests["with tests"]) / (len(rule_tests["without tests"]) + len(rule_tests["without tests"])) * 100
        )

        self._pd_extra.print_rules(rule_tests)

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

    def _get_rules_per_processor_name(self, rules_dirs: dict) -> defaultdict:
        rules_pn = defaultdict(dict)

        for processor_name, proc_rules_dirs in rules_dirs.items():
            self._get_rules_for_processor(processor_name, proc_rules_dirs, rules_pn)
        if self._problems["errors"]:
            self._pd_extra.print_rules(self._problems["errors"])
            sys.exit(1)
        return rules_pn

    def _get_rules_for_processor(self, processor_name, proc_rules_dirs, rules_pn):
        if not rules_pn[processor_name]:
            rules_pn[processor_name] = defaultdict(dict)
        processor_type = proc_rules_dirs["type"]
        rules_pn[processor_name]["type"] = processor_type
        rules_pn[processor_name]["rules"] = []
        directories = {"Rules Directory" : [f"{processor_name} ({processor_type}):"], "Path": []}

        for type_count, rules_dir in enumerate(proc_rules_dirs["rule_dirs"].values()):
            rule_dirs_type = list(proc_rules_dirs['rule_dirs'].keys())[type_count]
            directories["Path"].append(f"    - {rule_dirs_type}")
            for root, _, files in walk(str(rules_dir)): 
                rule_files = [file for file in files if self._is_valid_rule_name(file)]
                for file in rule_files:
                    
                    test_path = path.join(
                        root, "".join([file.rsplit(".", maxsplit=1)[0], "_test.json"])
                    )

                    self._get_rule_dict(file, root, test_path, processor_name, rules_pn, rule_dirs_type)
        
        self._pd_extra.print_rules(directories)

    def _get_rule_dict(self, file, root, test_path, processor_name, rules_pn, rule_dirs_type):
        rule_tests = []

        if path.isfile(test_path):
            try:
                rule_tests = self._pd_extra._load_json_or_yaml(test_path)
            except ValueError as error:
                self._problems["errors"].append(str(error))
                return

        file_path = path.join(root, file)
        try:
            multi_rule = self._pd_extra._load_json_or_yaml(file_path)
            if  not all(d.get("target_rule_idx") is not None for d in rule_tests) and len(rule_tests) > 1:
                raise Exception(f"Not all dictionaries in {file_path} contain the mandatory key target_rule_idx: Cant build corret test set for rules.")
        except ValueError as error:
            self._problems["errors"].append(str(error))
            return

        rules_pn[processor_name]["rules"].append({
            rule_dirs_type: multi_rule,
            "tests": rule_tests,
            "file": file_path,
        })

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
                rules_to_add.append(("generic_rules", processor_cfg["generic_rules"][0]))
                rules_to_add.append(("specific_rules", processor_cfg["specific_rules"][0]))

            if not rules_dirs[processor_name]:
                rules_dirs[processor_name] = defaultdict(dict)

            rules_dirs[processor_name]["type"] = processor_cfg["type"]

            if not rules_dirs[processor_name]["rule_dirs"]:
                rules_dirs[processor_name]["rule_dirs"] = defaultdict(str)
            
            for rule_to_add in rules_to_add:
                rules_dirs[processor_name]["rule_dirs"][rule_to_add[0]] += rule_to_add[1]

        return rules_dirs
