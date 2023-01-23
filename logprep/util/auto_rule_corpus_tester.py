"""
This module can be used to test a full logprep pipeline against expected outputs.

To run this RuleCorpusTester you have to give it a logprep pipeline configuration as well as a
directory with test data. Each test case should contain one input event (*_in.json), one expected
output event (*_out.json) and expected extra outputs like predetections or pseudonyms
(*_out_extra.json). The expected extra data is optional. But if given it is a single json file,
where each output has a root key of the expected target. All files belonging to the same test case
have to start with the same name. In each event a value can be marked as <IGNORE_VALUE>, with that
the value won't be considered during the testing.

While executing the tests report print statements are collected which will be printed to the console
after the test run is completed. During the run itself only a short summary is given for each case.

If during the test run logprep has an error or warning it logs it to the console as well, which will
be printed inside the test cases summary and before the summary result of the test, which created
the log message.

If one or more test cases fail this module ends with an exit code of 1, otherwise 0.
"""
# pylint: disable=protected-access
import json
import logging
import math
import os
import re
import shutil
import sys
import tempfile
from json import JSONDecodeError

import yaml
from deepdiff import DeepDiff, grep
from rich.console import Console
from rich.pretty import pprint

from logprep.framework.pipeline import Pipeline, SharedCounter
from logprep.util.configuration import Configuration
from logprep.util.helper import get_dotted_field_value
from logprep.util.json_handling import parse_json, parse_jsonl


class RuleCorpusTester:
    """This class can test a rule corpus against expected outputs"""

    def __init__(self, config_path, input_test_data_path):
        self.tmp_dir = tempfile.mkdtemp()
        self.console = Console(color_system="256")
        self.input_test_data_path = input_test_data_path
        self.path_to_original_config = config_path
        self.pipeline = None
        self.test_cases = {}
        self.at_least_one_failed = False

    def run(self):
        """
        Starts the test routine by reading all input files, patching the logprep pipline, executing
        the pipeline for each input event, comparing the generated output with the expected output
        and printing out the test results.
        """
        self._read_files()
        self._create_patched_pipeline()
        self._run_logprep_per_test_case()
        self._compare_with_expected_outputs()
        self._print_detailed_reports()
        self._print_test_statistics()
        shutil.rmtree(self.tmp_dir)
        if self.at_least_one_failed:
            sys.exit(1)
        else:
            sys.exit(0)

    def _read_files(self):
        """Traverse the given input directory and find all test cases."""
        data_directory = self.input_test_data_path
        file_paths = self._collect_test_case_file_paths(data_directory)
        test_cases = self._group_path_by_test_case(data_directory, file_paths)
        self.test_cases = dict(sorted(test_cases.items()))

    def _group_path_by_test_case(self, data_directory, file_paths):
        test_cases = {}
        for filename in file_paths:
            test_case_name = self._strip_input_file_type(filename)
            if test_case_name not in test_cases:
                test_cases[test_case_name] = {
                    "test_data_path": {"in": "", "out": "", "out_extra": ""},
                    "report_print_statements": [],
                }
            data_path = test_cases.get(test_case_name, {}).get("test_data_path", {})
            if "_in.json" in filename:
                data_path.update({"in": os.path.join(data_directory, filename)})
            if "_out.json" in filename:
                data_path.update({"out": os.path.join(data_directory, filename)})
            if "_out_extra.json" in filename:
                data_path.update({"out_extra": os.path.join(data_directory, filename)})
            test_cases.update({test_case_name: {"test_data_path": data_path}})
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
        for current_test_case in self.test_cases.items():
            if not current_test_case[1].get("test_data_path", {}).get("in"):
                raise ValueError(
                    f"The test case '{current_test_case[0]}' is missing an input file."
                )
            self._prepare_connector_files(current_test_case)
            self.pipeline._process_pipeline()
            output = self._retrieve_pipeline_output()
            current_test_case[1].update({"logprep_output": output})

    def _compare_with_expected_outputs(self):
        """Compare the generated logprep output with the current test case"""
        self.console.print("[b]# Test Cases Summary:")
        for test_case_id, test_case_data in self.test_cases.items():
            self._compare_and_collect_report_print_statements(test_case_data)
            self._print_short_test_result(test_case_id, test_case_data)
            if len(test_case_data.get("report_print_statements", [])) > 0:
                self.at_least_one_failed = True

    def _compare_and_collect_report_print_statements(self, test_case_data):
        event_output, extra_output, logprep_errors = test_case_data.get("logprep_output")
        expected_parsed_event_path = test_case_data.get("test_data_path", {}).get("out")
        expected_extra_data_path = test_case_data.get("test_data_path", {}).get("out_extra")
        print_statements = test_case_data.get("report_print_statements", [])
        if logprep_errors:
            print_statements.extend(["[red]Following errors happened:", logprep_errors])
        if expected_parsed_event_path:
            print_statements += self._parse_and_compare(expected_parsed_event_path, event_output)
        if expected_extra_data_path:
            print_statements += self._parse_and_compare_extras(
                expected_extra_data_path, extra_output
            )
        test_case_data["report_print_statements"] = print_statements

    def _print_detailed_reports(self):
        """If test case reports exist print out each report"""
        has_failed_reports = any(
            case[1].get("report_print_statements", False) for case in self.test_cases.items()
        )
        if not has_failed_reports:
            return
        self.console.print()
        self.console.print("[b]# Test Cases Detailed Reports:")
        for test_case_id, test_case_data in self.test_cases.items():
            if test_case_data.get("report_print_statements"):
                self._print_long_test_result(test_case_id, test_case_data)
                self.console.print()

    def _print_test_statistics(self):
        """Print minimal statistics of the test run"""
        self.console.print("[b]# Test Overview")
        total_cases = len(self.test_cases)
        failed_cases = len(
            [case for case in self.test_cases.items() if case[1].get("report_print_statements")]
        )
        self.console.print(f"Failed tests: {failed_cases}")
        self.console.print(f"Total test cases: {total_cases}")
        if total_cases:
            success_rate = (total_cases - failed_cases) / total_cases * 100
            self.console.print(f"Success rate: {success_rate:.2f}%")

    def _strip_input_file_type(self, filename):  # pylint: disable=no-self-use
        """Remove the input file suffix to identify the case name"""
        filename = filename.replace("_in", "")
        filename = filename.replace("_out_extra", "")
        filename = filename.replace("_out", "")
        filename = filename.replace(".json", "*")
        return filename

    def _create_patched_pipeline(self):
        """Patch the logprep config by changing the connector paths."""
        with open(self.path_to_original_config, "r", encoding="utf8") as config_file:
            pipeline = yaml.load(config_file, Loader=yaml.FullLoader)
        configured_input = pipeline.get("input", {})
        input_name = list(configured_input.keys())[0]
        preprocessors = configured_input.get(input_name, {}).get("preprocessing", {})
        pipeline["input"] = {
            "test_input": {
                "type": "jsonl_input",
                "documents_path": f"{self.tmp_dir}/input.json",
                "preprocessing": preprocessors,
            }
        }
        pipeline["output"] = {
            "test_output": {
                "type": "jsonl_output",
                "output_file": f"{self.tmp_dir}/output.out",
                "output_file_custom": f"{self.tmp_dir}/output_custom.out",
                "output_file_error": f"{self.tmp_dir}/output_error.out",
            }
        }
        pipeline["process_count"] = 1
        if "metrics" in pipeline:
            del pipeline["metrics"]
        config = Configuration()
        config.update(pipeline)
        log_handler = logging.StreamHandler()
        self.pipeline = Pipeline(0, config, SharedCounter(), log_handler, None, {}, {})
        self.pipeline._setup()

    def _parse_and_compare(self, expected_parsed_event_path, logprep_event_output):
        """Parses the expected logprep output and starts the comparison"""
        prints = []
        try:
            logprep_expected_output = parse_json(expected_parsed_event_path)
            prints += self._compare_outputs(logprep_event_output[0], logprep_expected_output[0])
        except JSONDecodeError as error:
            filename = os.path.basename(expected_parsed_event_path)
            prints.append(f"[red]Json-Error decoding file {filename}:[/red]\n{error}")
        return prints

    def _parse_and_compare_extras(self, expected_extra_data_path, logprep_extra_output):
        """Parses the expected extra data and starts the comparison"""
        prints = []
        try:
            expected_extra_output = parse_json(expected_extra_data_path)
            prints += self._compare_extra_data_output(logprep_extra_output, expected_extra_output)
        except JSONDecodeError as error:
            filename = os.path.basename(expected_extra_data_path)
            prints.append(f"[red]Json-Error decoding file {filename}:[/red]\n{error}")
        return prints

    def _compare_extra_data_output(self, logprep_extra_outputs, expected_extra_outputs):
        """
        Check if a generated extra output matches an expected extra output. If no match is found
        then the expected output is reported.
        """
        print_statements = []
        if len(logprep_extra_outputs) > len(expected_extra_outputs):
            print_statements.append(
                "[red]There is at least one generated extra output that is unexpected"
            )
        if len(logprep_extra_outputs) < len(expected_extra_outputs):
            print_statements.append("[red]There is at least one expected extra output missing")
        for expected_extra_output in expected_extra_outputs:
            expected_extra_output_key = list(expected_extra_output.keys())[0]
            has_matching_output = self._has_matching_logprep_output(
                expected_extra_output, expected_extra_output_key, logprep_extra_outputs
            )
            if not has_matching_output:
                print_statements.append(
                    "[red]For the following extra output, no matching extra output was generated by logprep",
                )
                print_statements.append(expected_extra_output)
        return print_statements

    def _has_matching_logprep_output(
        self, expected_extra_output, expected_extra_output_key, logprep_extra_outputs
    ):
        """
        Iterate over all logprep extra outputs and search for an output that matches the
        expected output
        """
        has_matching_output = False
        for logprep_extra_output in logprep_extra_outputs:
            logprep_extra_output_key = list(logprep_extra_output.keys())[0]
            if expected_extra_output_key == logprep_extra_output_key:
                diff_print_statements = self._compare_outputs(
                    logprep_extra_output[logprep_extra_output_key],
                    expected_extra_output[expected_extra_output_key],
                )
                if not diff_print_statements:
                    has_matching_output = True
        return has_matching_output

    def _print_short_test_result(self, test_case_id, test_case_data):
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

    def _compare_outputs(self, logprep_output, expected_output):
        """
        Compares a generated output with an expected output, by also ignoring keys that are marked
        as <IGNORE_VALUE>. For each difference a corresponding print statement is collected.
        """
        search_results = expected_output | grep("<IGNORE_VALUE>")
        missing_keys = self._check_keys_of_ignored_values(
            logprep_output, search_results.get("matched_values")
        )
        ignore_paths = []
        if "matched_values" in search_results:
            ignore_paths = list(search_results["matched_values"])
            ignore_paths = [re.escape(path) for path in ignore_paths]
        diff = DeepDiff(
            expected_output,
            logprep_output,
            ignore_order=True,
            report_repetition=True,
            exclude_regex_paths=ignore_paths,
        )

        print_statements = []
        if missing_keys:
            diff.update({"dictionary_item_removed": missing_keys})
        if diff:
            if "dictionary_item_removed" in diff.keys():
                print_statements.append(
                    "[red]Following expected items are missing in the generated logprep output:",
                )
                for item in diff["dictionary_item_removed"]:
                    print_statements.append(f" - {item}")
            if "dictionary_item_added" in diff.keys():
                print_statements.append(
                    "[red]Following unexpected values were generated by logprep"
                )
                for item in diff["dictionary_item_added"]:
                    print_statements.append(f" - {item}")
            if "values_changed" in diff.keys():
                print_statements.append(
                    "[red]Following values differ between generated and expected output",
                )
                for key, value in diff["values_changed"].items():
                    print_statements.append(f" - {key}: {self._rewrite_output(str(value))}")
        return print_statements

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

    def _rewrite_output(self, statement):  # pylint: disable=no-self-use
        statement = statement.replace("new_value", "generated")
        statement = statement.replace("old_value", "expected")
        return statement

    def _prepare_connector_files(self, current_test_case):  # pylint: disable=no-self-use
        """
        Between every test case the connectors are rewritten such that only one event is tested with
        every logprep step.
        """
        # remove version_information from previous run
        if self.pipeline._logprep_config.get("input", {}).get("version_information"):
            del self.pipeline._logprep_config["input"]["version_information"]
        self.pipeline._create_connectors()

        _, test_case_data = current_test_case
        test_case_input_file = test_case_data.get("test_data_path", {}).get("in")
        with open(test_case_input_file, "r", encoding="utf8") as test_case_input:
            input_json = json.load(test_case_input)
        with open(
            self.pipeline._input._config.documents_path, "w", encoding="utf8"
        ) as logprep_input:
            logprep_input.write(json.dumps(input_json))

        # pylint: disable=consider-using-with
        open(self.pipeline._output._config.output_file, "w", encoding="utf8").close()
        open(self.pipeline._output._config.output_file_custom, "w", encoding="utf8").close()
        open(self.pipeline._output._config.output_file_error, "w", encoding="utf8").close()
        # pylint: enable=consider-using-with

    def _retrieve_pipeline_output(self):  # pylint: disable=no-self-use
        """Returns the generated logprep outputs by reading the corresponding connector files."""
        parsed_outputs = [None, None, None]
        output_paths = [
            self.pipeline._output._config.output_file,
            self.pipeline._output._config.output_file_custom,
            self.pipeline._output._config.output_file_error,
        ]
        for index, output_path in enumerate(output_paths):
            parsed_outputs[index] = parse_jsonl(output_path)
        return parsed_outputs
