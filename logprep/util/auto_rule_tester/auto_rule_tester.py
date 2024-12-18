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
This can be achieved by the field `target_rule_idx` - now mandatory.
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

    logprep test unit $CONFIG

Where :code:`$CONFIG` is the path to a configuration file
(see :ref:`configuration`).

Auto-testing does also perform a verification of the pipeline section of the Logprep configuration.
"""

import hashlib
import json
import re
import sys
import tempfile
from collections import OrderedDict, defaultdict
from collections.abc import Iterable
from difflib import ndiff
from logging import getLogger
from os import path
from pathlib import Path
from pprint import pprint
from typing import TYPE_CHECKING, Union

from colorama import Fore
from more_itertools import nth
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
class AutoRuleTesterException(Exception):
    """Base class for AutoRuleTester related exceptions."""

    def __init__(self, message: str):
        super().__init__(f"AutoRuleTester ({message}): ")


class ProcessorExtensions:
    """Used to handle special demands for PreDetector auto-tests."""

    @staticmethod
    def _get_errors(processor: "Processor", extra_output: list):
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

    def update_errors(self, processor: PreDetector, extra_output: list, problems: dict):
        """Create aggregating logger.

        Parameters
        ----------
        processor : PreDetector
            Processor that should be of type PreDetector.
        extra_output : dict
            Extra output containing MITRE information coming from PreDetector.
        problems : dict
            Warnings and errors.

        """
        mitre_errors, id_warnings = self._get_errors(processor, extra_output)
        problems["errors"].extend(mitre_errors)
        problems["warnings"].extend(id_warnings)

    def print_rules(self, rules, t_idx=None):
        """Iterate through every printable and assign right processing resulting in
        a coloured output

        Parameters
        ----------
        rules : dict
            key and rule
        t_idx : int, optional
            Optional index to print correct element of , by default None
        """
        print()
        for key, rule in rules.items():
            self.print_diff_test(key, rule, t_idx)

    @staticmethod
    def print_diff_test(key, rule, t_idx=None):
        """Determine right processing for printable: no iterable, indexed and non
        index queried iterable

        Parameters
        ----------
        key : str
            kind of message
        rule : str or list
            printable message
        t_idx : int, optional
            associated index with printable, by default None
        """
        if not isinstance(rule, Iterable):
            diff = f"{key}: {rule}"
            ProcessorExtensions.color_based_print(diff)
        else:
            if t_idx is not None:
                diff = f"{key}: {rule[t_idx]}"
                ProcessorExtensions.color_based_print(diff)
            else:
                for item in rule:
                    diff = f"{key}: {item}"
                    ProcessorExtensions.color_based_print(diff)

    @staticmethod
    def color_based_print(item):
        """Print coloured status based on tokens

        Parameters
        ----------
        item : str
            status message
        """
        item = item.replace("]", "").replace("[", "")
        if (
            item.startswith((": - ", "- "))
            or item.startswith("error")
            or item.startswith("without tests")
        ):
            print_fcolor(Fore.RED, item)
        elif item.startswith((": + ", "+ ")) or item.startswith("with tests"):
            print_fcolor(Fore.GREEN, item)
        elif item.startswith((": ? ", "? ")):
            print_fcolor(Fore.WHITE, "\n" + item)
        elif item.startswith("> "):
            print_fcolor(Fore.MAGENTA, "\n" + item)
        elif item.lstrip().startswith("~ ") or item.startswith("warning"):
            print_fcolor(Fore.YELLOW, item)
        else:
            print_fcolor(Fore.CYAN, item)

    def load_json_or_yaml(self, file_path) -> Union[list, dict]:
        """load json or yaml depending on suffix

        Parameters
        ----------
        file_path : str
            path to file

        Returns
        -------
        Union[list, dict]
            wether json or yaml

        Raises
        ------
        ValueError
            error when file cant be decoded
        """
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                if file_path.endswith(".yml"):
                    return list(yaml.load_all(file))
                else:
                    return json.load(file)

        except (json.JSONDecodeError, YAMLError) as error:
            raise ValueError(f"Error decoding {file_path}: {str(error)}") from error


class AutoRuleTester:
    """Used to perform auto-tests for rules."""

    def __init__(self, config_path: str):
        with open(config_path, "r", encoding="utf-8") as yaml_file:
            self._config_yml = yaml.load(yaml_file)

        self._empty_rules_dirs = [tempfile.mkdtemp()]

        self._config_yml["connector"] = {"type": "dummy"}
        self._config_yml["process_count"] = 1
        self._config_yml["timeout"] = 0.1

        self._enable_print_stack_trace = self._config_yml.get("print_auto_test_stack_trace", True)

        self._success = True

        self._result = {
            "+ Successful Tests": 0,
            "- Failed Tests": 0,
            "~ Warning": 0,
            "Rule Test Coverage": 0.0,
            "Total Tests": 0,
        }
        self._problems = {"warnings": [], "errors": []}

        self._pd_extra = ProcessorExtensions()
        self._gpr = GrokPatternReplacer(self._config_yml)

        self._filename_printed = False
        self._rule_cnt = 0

        self._logger = getLogger()
        self._logger.disabled = True

    def run(self):
        """Perform auto-tests. Main entry"""
        rules_dirs = self._get_rule_dirs_by_processor_name()
        rules_pn = self._get_rules_per_processor_name(rules_dirs)
        self._run_if_any_rules_exist(rules_pn)

    def _run_if_any_rules_exist(self, rules_pn: dict) -> None:
        """Check if any rules exist in given path, then start rule tests depending on that.

        Parameters
        ----------
        rules_pn : dict
            accumulated rules for each processor to operate on
        """
        if any(processor_test_cfg["rules"] for processor_test_cfg in rules_pn.values()):
            self._run_tests_for_rules(rules_pn)
        else:
            print_fcolor(Fore.YELLOW, "~\nThere are no rules within any of the rules directories!")

    def check_run_rule_tests(self, processor_cont, rules_pn) -> None:
        """Verify dependencies for every preproccessor and if fullfilled, start the real rule tests.

        Parameters
        ----------
        processor_cont : dict
            proc object and name
        rules_pn : dict
            accumulated rules for each processor to operate on
        """
        for processor, processor_name in processor_cont.items():
            for rule_test in rules_pn[processor_name]["rules"]:
                if processor and rule_test["tests"]:
                    self._run_rule_tests(processor, rule_test)

    def _run_tests_for_rules(self, rules_pn: dict) -> None:
        """Run various check and collect warnings, if not Successful exit.

        Parameters
        ----------
        rules_pn : dict
            accumulated rules for each processor to operate on
        """
        self._check_which_rule_files_miss_tests(rules_pn)
        processors_no_ct = self._get_processors()
        self.check_run_rule_tests(processors_no_ct, rules_pn)
        self._result["~ Warning"] += len(self._problems.get("warnings"))
        self._pd_extra.print_rules(self._result)

        if not self._success:
            sys.exit(1)

    def _run_rule_tests(self, processor: "Processor", rule_test: dict):
        """Run various evaluations for the rules given

        Parameters
        ----------
        processor : Processor
            name
        rule_test : dict
            the rules to test
        """
        temp_rule_path = path.join(
            self._empty_rules_dirs[0], f"{hashlib.sha256().hexdigest()}.json"
        )
        rules = self._get_rules(processor, rule_test)

        for idx, rule_dict in enumerate(rules):
            self._prepare_test_eval(processor, rule_dict, temp_rule_path)
            self._eval_file_rule_test(rule_test, processor, idx)
            remove_file_if_exists(temp_rule_path)

    def _get_processors(self) -> OrderedDict:
        """Get processors in k/v-pairs

        Returns
        -------
        OrderedDict
            returns processors with meta data
        """
        processors_without_custom_test = OrderedDict()
        for processor_in_pipeline in self._config_yml["pipeline"]:
            name, processor_cfg = next(iter(processor_in_pipeline.items()))
            processor = self._get_processor_instance(name, processor_cfg)
            processors_without_custom_test[processor] = name
        return processors_without_custom_test

    @staticmethod
    def _get_rules(processor: "Processor", rule_test: dict) -> list:
        """Assign and get rule

        Parameters
        ----------
        processor : Processor
            name
        rule_test : dict
            unassigned rules

        Returns
        -------
        list
            ruleset

        Raises
        ------
        AutoRuleTesterException
            empty ruleset
        """
        if rule_test.get("rules"):
            return rule_test.get("rules", [])
        raise AutoRuleTesterException(
            f"No rules provided for processor of type {processor.describe()}"
        )

    def _load_rules(self, processor: "Processor"):
        """Load each type of rules for each processor and set it up

        Parameters
        ----------
        processor : Processor
            proc obj
        rule_type : str
            type
        """
        processor.load_rules(self._empty_rules_dirs)
        processor.setup()

    def _prepare_test_eval(
        self, processor: "Processor", rule_dict: dict, temp_rule_path: str
    ) -> None:
        """Prepare test eval: Create rule file, then reset tree of processor and then load
         the rules for the processor

        Parameters
        ----------
        processor : Processor
            processor
        rule_dict : dict
            rules for proc
        temp_rule_path : str
            temporary path to rules
        """
        self._create_rule_file(rule_dict, temp_rule_path)
        self._reset(processor)
        self._load_rules(processor)

    def _eval_file_rule_test(self, rule_test: dict, processor: "Processor", r_idx: int):
        """Main logic to check each rule file, compare and validate it, then print out results.
         For each processor a process is spawned.

        Parameters
        ----------
        rule_test : dict
            rules to test
        processor : Processor
            processor object to base start process on
        r_idx : int
            rule index in file

        Raises
        ------
        Exception
            spawned process caught in exception
        """
        self._filename_printed = False
        for t_idx, test in enumerate(rule_test["tests"]):

            if test.get("target_rule_idx") is not None and test.get("target_rule_idx") != r_idx:
                continue
            try:
                result = processor.process(test["raw"])
                if not result and processor.name == "pre_detector":
                    self._pd_extra.color_based_print(
                        f"- Can't process RULE FILE {rule_test['file']}. No extra output generated"
                    )
                    sys.exit(1)
            except Exception:
                self._success = False
                self._result["- Failed Tests"] += 1
                continue

            diff = self._get_diff_raw_test(test)
            print_diff = self._check_if_different(diff)

            if isinstance(processor, PreDetector):
                self._pd_extra.update_errors(processor, result.data, self._problems)

            if (
                print_diff
                or nth(self._problems.get("warnings"), self._rule_cnt) is not None
                or nth(self._problems.get("errors"), self._rule_cnt) is not None
            ):
                self._pd_extra.color_based_print(
                    f"> RULE FILE {rule_test['file']} & "
                    f"RULE TEST {t_idx + 1}/{len(rule_test['tests'])}:"
                )
                if nth(self._problems.get("warnings"), self._rule_cnt) is not None:
                    self._pd_extra.color_based_print(
                        f"~ {self._problems.get('warnings')[self._result['~ Warning']]}"
                    )

                if print_diff or nth(self._problems.get("errors"), self._rule_cnt) is not None:
                    if nth(self._problems.get("errors"), self._rule_cnt) is not None:
                        self._pd_extra.color_based_print(
                            f"- {self._problems.get('errors')[self._result['- Failed Tests']]}"
                        )
                    self._pd_extra.print_diff_test("", diff)  # print_rules({"DIFF": diff})
                    self._success = False
                    self._result["- Failed Tests"] += 1

            else:
                self._result["+ Successful Tests"] += 1

            self._rule_cnt += 1
        self._result["Total Tests"] = (
            self._result["+ Successful Tests"] + self._result["- Failed Tests"]
        )

    @staticmethod
    def _reset(processor: "Processor"):
        """Reset the rule tree

        Parameters
        ----------
        processor : Processor
            processor to reset tree on
        """
        if hasattr(processor, "rules"):
            processor.rules.clear()
        if hasattr(processor, "_rule_tree"):
            processor._rule_tree = RuleTree()

    @staticmethod
    def _create_rule_file(rule_dict: dict, rule_path: str):
        with open(rule_path, "w", encoding="utf8") as temp_file:
            json.dump([rule_dict], temp_file)

    @staticmethod
    def _check_if_different(diff):
        """Check result of comparison (diff)

        Parameters
        ----------
        diff : list
            result of comparison

        Returns
        -------
        bool
            any(thing) found reference
        """
        return any((item for item in diff if item.startswith(("+", "-", "?"))))

    @staticmethod
    def _get_processor_instance(name, processor_cfg):
        cfg = {name: processor_cfg}
        processor = Factory.create(cfg)
        return processor

    def _check_which_rule_files_miss_tests(self, rules_pn) -> None:
        """Calculate quota on coverage of tests for (processor) ruleset

        Parameters
        ----------
        rules_pn : dict
            accumulated rules for each processor to operate on
        """
        rule_tests = {"with tests": [], "without tests": []}
        for _, processor_test_cfg in rules_pn.items():
            rules = processor_test_cfg["rules"]

            for rule in rules:
                if rule["tests"]:
                    rule_tests["with tests"].append(rule["file"])
                else:
                    rule_tests["without tests"].append(rule["file"])

        self._result["Rule Test Coverage"] = (
            len(rule_tests["with tests"])
            / (len(rule_tests["without tests"]) + len(rule_tests["with tests"]))
            * 100
        )

        self._pd_extra.print_rules(rule_tests)

    def _sort_lists_in_nested_dict(self, nested_dict):
        for key, value in nested_dict.items():
            if isinstance(value, dict):
                self._sort_lists_in_nested_dict(value)
            elif isinstance(value, list):
                nested_dict[key] = sorted(nested_dict[key])

    def _get_diff_raw_test(self, test: dict) -> list:
        """Compare tests

        Parameters
        ----------
        test : dict
            each test in rule file

        Returns
        -------
        list
            found differences
        """
        self._gpr.replace_grok_keywords(test["processed"], test)

        self._sort_lists_in_nested_dict(test)

        raw = json.dumps(test["raw"], sort_keys=True, indent=4)
        processed = json.dumps(test["processed"], sort_keys=True, indent=4)

        diff = ndiff(raw.splitlines(), processed.splitlines())
        return list(diff)

    def _set_rules_dirs_to_empty(self) -> None:
        """Set each rule type to empty"""
        for processor in self._config_yml["pipeline"]:
            processor_cfg = next(iter(processor.values()))

            if processor_cfg.get("rules"):
                processor_cfg["rules"] = self._empty_rules_dirs

    def _get_rules_per_processor_name(self, rules_dirs: dict) -> defaultdict:
        rules_pn = defaultdict(dict)

        for processor_name, proc_rules_dirs in rules_dirs.items():
            self._get_rules_for_processor(processor_name, proc_rules_dirs, rules_pn)
        if self._problems["errors"]:
            self._pd_extra.print_rules(self._problems["errors"])
            sys.exit(1)
        return rules_pn

    def _get_rules_for_processor(self, processor_name, proc_rules_dirs, rules_pn):
        """Read out rules and populate dict with processor: rules

        Parameters
        ----------
        processor_name : str
            name of proc
        proc_rules_dirs : dict
            all directories for proc
        rules_pn : dict
            accumulated rules for each processor to operate on
        """
        if not rules_pn[processor_name]:
            rules_pn[processor_name] = defaultdict(dict)
        processor_type = proc_rules_dirs["type"]
        rules_pn[processor_name]["type"] = processor_type
        rules_pn[processor_name]["rules"] = []
        directories = {"Rules Directory": [f"{processor_name} ({processor_type}):"], "Path": []}

        for rules_dir in proc_rules_dirs["rule_dirs"]:
            directories["Path"].append(f"    - {'rule_type'}")
            for file_path in Path(rules_dir).rglob("*"):
                if file_path.is_file() and self._is_valid_rule_name(file_path.name):
                    self._get_rule_dict(
                        file_path.name, str(file_path.parent), processor_name, rules_pn
                    )

        self._pd_extra.print_rules(directories)

    def _get_rule_dict(self, file, root, processor_name, rules_pn) -> None:
        """Read out (multi-)rules and realize mapping via dict for further processing

        Parameters
        ----------
        file : str
            each rule file
        root : str
            base path
        processor_name : str
            name
        rules_pn : dict
            mapping of procs to rules

        Raises
        ------
        Exception
            Target_rule_idx is now mandatory, throw exception if not found for each rule
        """
        rule_tests = []
        test_path = path.join(root, "".join([file.rsplit(".", maxsplit=1)[0], "_test.json"]))

        if path.isfile(test_path):
            try:
                rule_tests = self._pd_extra.load_json_or_yaml(test_path)
            except ValueError as error:
                self._problems["errors"].append(str(error))
                return

        file_path = path.join(root, file)
        try:
            multi_rule = self._pd_extra.load_json_or_yaml(file_path)
            if (
                processor_name == "pre_detector"
                and not all(d.get("target_rule_idx") is not None for d in rule_tests)
                and len(rule_tests) > 1
            ):
                self._pd_extra.color_based_print(
                    f"- Not all dictionaries in {file_path} "
                    f"contain the mandatory key target_rule_idx: "
                    f"Can't build correct test set for rules."
                )
                sys.exit(1)
        except ValueError as error:
            self._problems["errors"].append(str(error))
            return

        rules_pn[processor_name]["rules"].append(
            {
                "rules": multi_rule,
                "tests": rule_tests,
                "file": file_path,
            }
        )

    @staticmethod
    def _is_valid_rule_name(file_name: str) -> bool:
        return (file_name.endswith(".json") or file_name.endswith(".yml")) and not (
            file_name.endswith("_test.json")
        )

    def _get_rule_dirs_by_processor_name(self) -> defaultdict:
        rules_dirs = defaultdict(dict)
        for processor in self._config_yml["pipeline"]:
            processor_name, processor_cfg = next(iter(processor.items()))

            print("\nProcessor Config:")
            pprint(processor_cfg)

            rules_to_add = self._get_rules_to_add(processor_cfg)

            if not rules_dirs[processor_name]:
                rules_dirs[processor_name] = defaultdict(dict)

            rules_dirs[processor_name]["type"] = processor_cfg["type"]

            if not rules_dirs[processor_name]["rule_dirs"]:
                rules_dirs[processor_name]["rule_dirs"] = []

            for rule_to_add in rules_to_add:
                rules_dirs[processor_name]["rule_dirs"].append(rule_to_add)

        return rules_dirs

    @staticmethod
    def _get_rules_to_add(processor_cfg) -> list:
        """Accumulate rules depending on processor (config)

        Parameters
        ----------
        processor_cfg : dict
            config

        Returns
        -------
        list
            rules
        """
        rules_to_add = []

        rule_path_lists = processor_cfg.get("rules")
        if rule_path_lists:
            for rule_path_list in rule_path_lists:
                rules_to_add.append(rule_path_list)
        return rules_to_add
