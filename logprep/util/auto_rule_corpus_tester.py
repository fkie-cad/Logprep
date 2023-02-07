# pylint: disable=anomalous-backslash-in-string
"""
Rule Corpus Tests
-----------------

The rule corpus tester can be used to test a full logprep pipeline and configuration against
a set of expected outputs.

To start the tester call:

..  code-block:: bash
    :caption: Run rule corpus test

    logprep $CONFIG --auto-corpus-test --corpus-testdata $CORPUS_TEST_DATA

Where in the parameter :code:`CONFIG` should point to a valid logprep configuration and
:code:`CORPUS_TEST_DATA` to a directory containing the test data with the different test cases.
The test cases can be organized into subdirectories.
Each test case should contain one input event (\*_in.json), one expected output event (\*_out.json)
and an expected extra outputs like predetections or pseudonyms (\*_out_extra.json).
The expected extra data is optional though, but if given, it is a single json file, where each
output has a root key of the expected target.
All files belonging to the same test case have to start with the same name, like the following
example:

..  code-block:: bash
    :caption: Test data setup

    - test_one_in.json
    - test_one_out.json
    - test_one_out_extra.json
    - test_two_in.json
    - test_two_out.json

..  code-block:: json
    :caption: Content of test_one_in.json - Logprep input

    {
        "test": "event"
    }

..  code-block:: json
    :caption: Content of test_one_out.json - Expected Logprep Output

    {
        "processed": ["test", "event"]
        "with": "<IGNORE_VALUE>"
    }

..  code-block:: json
    :caption: Content of test_one_out_extra.json - Expected Logprep Extra Output

    [
        {
            "predetection_target": {
                "id": "..."
            }
        }
    ]

As sometimes test have cases where you don't want to test for a specific value of a key it is
possible to test only for the key and ignore the value.
In order to achieve this just set a filed in an expected output as :code:`<IGNORE_VALUE>`, with that
the value won't be considered during the testing.

While executing the tests report print statements are collected which will be printed to the console
after the test run is completed.
During the run itself only a short summary is given for each case.

If during the test run logprep has an error or warning it logs it to the console as well, which will
be printed inside the test cases summary and before the summary result of the test, which created
the log message.

If one or more test cases fail this tester ends with an exit code of 1, otherwise 0.
"""
# pylint: enable=anomalous-backslash-in-string
# pylint: disable=protected-access
import math
import os
import re
import shutil
import sys
import tempfile
from functools import cached_property
from json import JSONDecodeError
from logging import getLogger

from deepdiff import DeepDiff, grep
from rich.console import Console
from rich.pretty import pprint

from logprep.util.configuration import Configuration
from logprep.util.helper import get_dotted_field_value
from logprep.util.json_handling import parse_json
from logprep.util.rule_dry_runner import get_patched_runner, get_runner_outputs


class RuleCorpusTester:
    """This class can test a rule corpus against expected outputs"""

    _tmp_dir: str
    """ Temporary directory where test files will be saved temporarily """

    _original_config_path: str
    """ Path to the original configuration that should be tested """

    _input_test_data_path: str
    """ Path to the directory that contains the test data (in, out, extra_outs) """

    _test_cases: dict
    """ Dictionary that contains the test cases, their input data and their results """

    _at_least_one_test_failed: bool
    """ Flag that indicates that at least one test has failed """

    def __init__(self, config_path, input_test_data_path):
        self._original_config_path = config_path
        self._input_test_data_path = input_test_data_path
        self._test_cases = {}
        self._at_least_one_test_failed = False
        self.console = Console(color_system="256")

    @cached_property
    def _tmp_dir(self):
        return tempfile.mkdtemp()

    def run(self):
        """
        Starts the test routine by reading all input files, patching the logprep pipline, executing
        the pipeline for each input event, comparing the generated output with the expected output
        and printing out the test results.
        """
        self._read_files()
        self._run_logprep_per_test_case()
        self._compare_with_expected_outputs()
        self._print_detailed_reports()
        self._print_test_statistics()
        shutil.rmtree(self._tmp_dir)
        if self._at_least_one_test_failed:
            sys.exit(1)
        else:
            sys.exit(0)

    def _read_files(self):
        """Traverse the given input directory and find all test cases."""
        data_directory = self._input_test_data_path
        file_paths = self._collect_test_case_file_paths(data_directory)
        test_cases = self._group_path_by_test_case(data_directory, file_paths)
        self._test_cases = dict(sorted(test_cases.items()))

    def _group_path_by_test_case(self, data_directory, file_paths):
        test_cases = {}
        for filename in file_paths:
            test_case_id = self._strip_input_file_type(filename)
            if test_case_id not in test_cases:
                test_cases[test_case_id] = {
                    "test_data_path": {"in": "", "out": "", "out_extra": ""},
                    "report_print_statements": [],
                }
            data_path = test_cases.get(test_case_id, {}).get("test_data_path", {})
            if "_in.json" in filename:
                data_path.update({"in": os.path.join(data_directory, filename)})
            if "_out.json" in filename:
                data_path.update({"out": os.path.join(data_directory, filename)})
            if "_out_extra.json" in filename:
                data_path.update({"out_extra": os.path.join(data_directory, filename)})
            test_cases[test_case_id]["test_data_path"].update(data_path)
        return test_cases

    def _collect_test_case_file_paths(self, data_directory):
        file_paths = []
        for root, _, files in os.walk(data_directory):
            for filename in files:
                file_paths.append(os.path.abspath(os.path.join(root, filename)))
        return file_paths

    def _run_logprep_per_test_case(self):
        """
        For each test case the logprep connector files are rewritten (only the current test case
        will be added to the input file), the pipline is run and the outputs are compared.
        """
        for current_test_case in self._test_cases.items():
            input_file_path = current_test_case[1].get("test_data_path", {}).get("in")
            if not input_file_path:
                raise ValueError(
                    f"The test case '{current_test_case[0]}' is missing an input file."
                )
            path_to_patched_config = Configuration.patch_yaml_with_json_connectors(
                self._original_config_path, self._tmp_dir, input_file_path
            )
            test_runner = get_patched_runner(path_to_patched_config, logger=getLogger())
            outputs = get_runner_outputs(test_runner)
            current_test_case[1].update({"logprep_output": outputs})

    def _compare_with_expected_outputs(self):
        """Compare the generated logprep output with the current test case"""
        self.console.print("[b]# Test Cases Summary:")
        for test_case_id in self._test_cases:
            self._compare_and_collect_report_print_statements(test_case_id)
            self._print_short_test_result(test_case_id)
            if len(self._test_cases.get(test_case_id, {}).get("report_print_statements", [])) > 0:
                self._at_least_one_test_failed = True

    def _compare_and_collect_report_print_statements(self, test_case_id):
        test_case_data = self._test_cases.get(test_case_id, {})
        _, _, logprep_errors = test_case_data.get("logprep_output")
        if logprep_errors:
            self._test_cases[test_case_id]["report_print_statements"].extend(
                ["[red]Following errors happened:", logprep_errors]
            )
        if test_case_data.get("test_data_path", {}).get("out"):
            self._compare_logprep_outputs(test_case_id)
        if test_case_data.get("test_data_path", {}).get("out_extra"):
            self._compare_extra_data_output(test_case_id)

    def _print_detailed_reports(self):
        """If test case reports exist print out each report"""
        has_failed_reports = any(
            case[1].get("report_print_statements", False) for case in self._test_cases.items()
        )
        if not has_failed_reports:
            return
        self.console.print()
        self.console.print("[b]# Test Cases Detailed Reports:")
        for test_case_id, test_case_data in self._test_cases.items():
            if test_case_data.get("report_print_statements"):
                self._print_long_test_result(test_case_id, test_case_data)
                self.console.print()

    def _print_test_statistics(self):
        """Print minimal statistics of the test run"""
        self.console.print("[b]# Test Overview")
        total_cases = len(self._test_cases)
        failed_cases = len(
            [case for case in self._test_cases.items() if case[1].get("report_print_statements")]
        )
        self.console.print(f"Failed tests: {failed_cases}")
        self.console.print(f"Total test cases: {total_cases}")
        if total_cases:
            success_rate = (total_cases - failed_cases) / total_cases * 100
            self.console.print(f"Success rate: {success_rate:.2f}%")

    def _strip_input_file_type(self, filename):
        """Remove the input file suffix to identify the case name"""
        filename = filename.replace("_in", "")
        filename = filename.replace("_out_extra", "")
        filename = filename.replace("_out", "")
        filename = filename.replace(".json", "*")
        return filename

    def _parse_json_with_error_handling(self, test_case_id, path):
        try:
            parsed_json = parse_json(path)
            return parsed_json
        except JSONDecodeError as error:
            filename = os.path.basename(path)
            self._test_cases[test_case_id]["report_print_statements"].append(
                f"[red]Json-Error decoding file {filename}:[/red]\n{error}"
            )
        return None

    def _compare_extra_data_output(self, test_case_id):
        """
        Check if a generated extra output matches an expected extra output. If no match is found
        then the expected output is reported.
        """
        test_case_data = self._test_cases.get(test_case_id, {})
        _, logprep_extra_outputs, _ = test_case_data.get("logprep_output")
        expected_extra_outputs_path = test_case_data.get("test_data_path", {}).get("out_extra")
        expected_extra_outputs = self._parse_json_with_error_handling(
            test_case_id, expected_extra_outputs_path
        )
        if expected_extra_outputs is None:
            return
        prints = []
        if len(logprep_extra_outputs) > len(expected_extra_outputs):
            prints.append("[red]There is at least one generated extra output that is unexpected")
        if len(logprep_extra_outputs) < len(expected_extra_outputs):
            prints.append("[red]There is at least one expected extra output missing")
        for expected_extra_output in expected_extra_outputs:
            expected_extra_output_key = list(expected_extra_output.keys())[0]
            has_matching_output = self._has_matching_logprep_output(
                test_case_id,
                expected_extra_output,
                expected_extra_output_key,
                logprep_extra_outputs,
            )
            if not has_matching_output:
                prints.append(
                    "[red]For the following extra output, "
                    "no matching extra output was generated by logprep",
                )
                prints.append(expected_extra_output)
        self._test_cases[test_case_id]["report_print_statements"].extend(prints)

    def _has_matching_logprep_output(
        self, test_case_id, expected_extra_output, expected_extra_output_key, logprep_extra_outputs
    ):
        """
        Iterate over all logprep extra outputs and search for an output that matches the
        expected output
        """
        has_matching_output = False
        for logprep_extra_output in logprep_extra_outputs:
            logprep_extra_output_key = list(logprep_extra_output.keys())[0]
            if expected_extra_output_key == logprep_extra_output_key:
                diff = self._compare_events(
                    test_case_id,
                    logprep_extra_output[logprep_extra_output_key],
                    expected_extra_output[expected_extra_output_key],
                )
                if diff is not None:
                    has_matching_output = True
        return has_matching_output

    def _print_short_test_result(self, test_case_id):
        test_case_data = self._test_cases.get(test_case_id, {})
        status = "[b green] PASSED"
        if not test_case_data.get("test_data_path", {}).get("out"):
            status = "[b grey53] SKIPPED[/b grey53] [grey53](no expected output given)[grey53]"
        if len(test_case_data.get("report_print_statements", [])) > 0:
            status = "[b red] FAILED"
        self.console.print(
            f"[b blue]Test Case: [not bold slate_blue1]{test_case_id} {status}",
            overflow="ignore",
            crop=False,
        )

    def _print_long_test_result(self, test_case_id, test_case_data):
        """
        Prints out the collected print statements of a test case, resulting in a test
        case reports
        """
        parsed_event, extra_data, _ = test_case_data.get("logprep_output")
        report_title = f"test report for '{test_case_id}'"
        report_title_length = len(report_title) + 4
        title_target_length = 120
        padding_length = (title_target_length - report_title_length) / 2
        padding = f"{'#' * math.floor(padding_length)}"
        self.console.print(
            f"[red]{padding} [bold]↓ {report_title} ↓[/bold] {padding}",
            overflow="ignore",
            crop=False,
        )
        for statement in test_case_data.get("report_print_statements"):
            if isinstance(statement, (dict, list)):
                pprint(statement, console=self.console, expand_all=True, indent_guides=False)
            else:
                self.console.print(statement, overflow="ignore", crop=False)
        self.console.print()
        self.console.print("[red]Logprep Event Output:")
        pprint(parsed_event[0], console=self.console, expand_all=True, indent_guides=False)
        self.console.print("[red]Logprep Extra Data Output:")
        pprint(extra_data, console=self.console, expand_all=True, indent_guides=False)
        self.console.print(
            f"[red]{padding} [bold]↑ {report_title} ↑[/bold] {padding}",
            overflow="ignore",
            crop=False,
        )

    def _compare_logprep_outputs(self, test_case_id):
        """
        Compares a generated output with an expected output, by also ignoring keys that are marked
        as <IGNORE_VALUE>. For each difference a corresponding print statement is collected.
        """
        test_case_data = self._test_cases.get(test_case_id, {})
        logprep_output, _, _ = test_case_data.get("logprep_output")
        expected_parsed_event_path = test_case_data.get("test_data_path", {}).get("out")
        expected_output = self._parse_json_with_error_handling(
            test_case_id, expected_parsed_event_path
        )
        if expected_output is None:
            return
        self._compare_events(test_case_id, logprep_output[0], expected_output[0])

    def _compare_events(self, test_case_id, generated, expected):
        search_results = expected | grep("<IGNORE_VALUE>")
        missing_keys = self._check_keys_of_ignored_values(
            generated, search_results.get("matched_values")
        )
        ignore_paths = []
        if "matched_values" in search_results:
            ignore_paths = list(search_results["matched_values"])
            ignore_paths = [re.escape(path) for path in ignore_paths]
        diff = DeepDiff(
            expected,
            generated,
            ignore_order=True,
            report_repetition=True,
            exclude_regex_paths=ignore_paths,
        )
        if missing_keys:
            diff.update({"dictionary_item_removed": missing_keys})
        self._create_and_append_print_statements(test_case_id, diff)
        return diff

    def _create_and_append_print_statements(self, test_case_id, diff):
        if not diff:
            return
        prints = []
        if "dictionary_item_removed" in diff:
            prints.append(
                "[red]Following expected items are missing in the generated logprep output:",
            )
            for item in diff["dictionary_item_removed"]:
                prints.append(f" - {item}")
        if "dictionary_item_added" in diff:
            prints.append("[red]Following unexpected values were generated by logprep")
            for item in diff["dictionary_item_added"]:
                prints.append(f" - {item}")
        if "values_changed" in diff:
            prints.append(
                "[red]Following values differ between generated and expected output",
            )
            for key, value in diff["values_changed"].items():
                prints.append(f" - {key}: {self._rewrite_output(str(value))}")
        self._test_cases[test_case_id]["report_print_statements"].extend(prints)

    def _check_keys_of_ignored_values(self, logprep_output, field_paths) -> list:
        if not field_paths:
            return []
        missing_keys = []
        for path in field_paths:
            dotted_path = ".".join(re.findall(r"\['([^'|.*]*)'\]", path))
            field_value = get_dotted_field_value(logprep_output, dotted_path)
            if field_value is None:
                missing_keys.append(path)
        return missing_keys

    def _rewrite_output(self, statement):
        statement = statement.replace("new_value", "generated")
        statement = statement.replace("old_value", "expected")
        return statement
