# pylint: disable=anomalous-backslash-in-string
"""
Rule Corpus Tests
-----------------

The rule corpus tester can be used to test a full logprep pipeline and configuration against
a set of expected outputs.

To start the tester call:

..  code-block:: bash
    :caption: Run rule corpus test

    logprep test integration $CONFIG $CORPUS_TEST_DATA

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

As sometimes test could have cases where you don't want to test for a specific value of a key it is
possible to test only for the key and ignore the value.
In order to achieve this just set a field in an expected output as :code:`<IGNORE_VALUE>`, with that
the value won't be considered during the testing.
Furthermore, it is possible to set an entire field as optional with :code:`<OPTIONAL_KEY>`.
This way fields can be testet for their presents when they exist, and will be ignored when they do
not exist.
This can for example be the case for the geo ip enricher, which sometimes finds city information
about an ip and sometimes not.

While executing the tests report print statements are collected which will be printed to the console
after the test run is completed.
During the run itself only a short summary is given for each case.

If during the test run logprep has an error or warning it logs it to the console as well, which will
be printed inside the test cases summary and before the summary result of the test, which created
the log message.

If one or more test cases fail this tester ends with an exit code of 1, otherwise 0.
"""
import io

# pylint: enable=anomalous-backslash-in-string
# pylint: disable=protected-access
import json
import logging
import os
import re
import shutil
import sys
import tempfile
from functools import cached_property
from json import JSONDecodeError
from logging import getLogger
from pathlib import Path
from pprint import pprint
from typing import List

from attr import Factory, define, field, validators
from colorama import Fore, Style
from deepdiff import DeepDiff, grep

from logprep.framework.pipeline import Pipeline
from logprep.util.configuration import Configuration
from logprep.util.helper import get_dotted_field_value
from logprep.util.json_handling import parse_json


def align_extra_output_formats(extra_outputs):
    """
    Aligns the different output formats into one common format of the selective_extractor,
    predetector and pseudonymizer.
    """
    reformatted_extra_outputs = []
    for extra_output in extra_outputs:
        if isinstance(extra_output, tuple):
            documents, target = extra_output
            for document in documents:
                reformatted_extra_outputs.append({str(target): document})
        else:
            for output in extra_output:
                reformatted_extra_outputs.append({str(output[1]): output[0][0]})
    return reformatted_extra_outputs


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

    @define(kw_only=True)
    class TestCase:
        input_document: dict = field(validator=validators.instance_of(dict), default={})
        expected_output: dict = field(validator=validators.instance_of(dict), default={})
        expected_extra_output: dict = field(validator=validators.instance_of(list), default=[])
        generated_output: dict = field(validator=validators.instance_of(dict), default={})
        generated_extra_output: dict = field(validator=validators.instance_of(list), default=[])
        failed: bool = field(validator=validators.instance_of(bool), default=False)
        report: List = Factory(list)
        warnings: str = field(default="")

    def __init__(self, config_path, input_test_data_path):
        self._original_config_path = config_path
        self._input_test_data_path = input_test_data_path
        self.log_capture_string = None

    @cached_property
    def _tmp_dir(self):
        return tempfile.mkdtemp()

    @cached_property
    def _test_cases(self):
        file_paths = []
        for root, _, files in os.walk(self._input_test_data_path):
            for filename in files:
                file_paths.append(os.path.abspath(os.path.join(root, filename)))
        test_cases = self._group_path_by_test_case(self._input_test_data_path, file_paths)
        parsing_errors = [case.report for case in test_cases.values() if case.report]
        if parsing_errors:
            raise ValueError(f"Following parsing errors were found: {parsing_errors}")
        no_input_files = [case for case in test_cases if not test_cases[case].input_document]
        if no_input_files:
            raise ValueError(f"The following TestCases have no input documents: {no_input_files}")
        return dict(sorted(test_cases.items()))

    @cached_property
    def _logprep_logger(self):
        logprep_logger = getLogger("logprep-rule-corpus-tester")
        logprep_logger.propagate = False
        logprep_logger.setLevel(logging.WARNING)
        self.log_capture_string = io.StringIO()
        self.stream_handler = logging.StreamHandler(self.log_capture_string)
        self.stream_handler.setLevel(logging.WARNING)
        logprep_logger.addHandler(self.stream_handler)
        return logprep_logger

    @cached_property
    def _pipeline(self):
        merged_input_file_path = Path(self._tmp_dir) / "input.json"
        inputs = [test_case.input_document for test_case in self._test_cases.values()]
        merged_input_file_path.write_text(json.dumps(inputs), encoding="utf8")
        patched_config = Configuration()
        patched_config.input = {
            "patched_input": {"type": "json_input", "documents_path": str(merged_input_file_path)}
        }
        config = Configuration.from_sources([self._original_config_path])
        input_config = config.input
        connector_name = list(input_config.keys())[0]
        if "preprocessing" in input_config[connector_name]:
            patched_config.input["patched_input"] |= {
                "preprocessing": input_config[connector_name]["preprocessing"]
            }
        patched_config.pipeline = config.pipeline
        pipeline = Pipeline(config=patched_config)
        pipeline.logger = self._logprep_logger
        return pipeline

    def run(self):
        """
        Starts the test routine by reading all input files, patching the logprep pipline, executing
        the pipeline for each input event, comparing the generated output with the expected output
        and printing out the test results.
        """
        self._run_pipeline_per_test_case()
        self._print_test_reports()
        self._print_test_summary()
        shutil.rmtree(self._tmp_dir)
        if any(case.failed for case in self._test_cases.values()):
            sys.exit(1)
        else:
            sys.exit(0)

    def _run_pipeline_per_test_case(self):
        """
        For each test case the logprep connector files are rewritten (only the current test case
        will be added to the input file), the pipline is run and the outputs are compared.
        """
        print(Style.BRIGHT + "# Test Cases Summary:" + Style.RESET_ALL)
        for test_case_id, test_case in self._test_cases.items():
            _ = [processor.setup() for processor in self._pipeline._pipeline]
            parsed_event, extra_outputs = self._pipeline.process_pipeline()
            test_case.warnings = self._retrieve_log_capture()
            extra_outputs = align_extra_output_formats(extra_outputs)
            test_case.generated_output = parsed_event
            test_case.generated_extra_output = extra_outputs
            self._compare_logprep_outputs(test_case_id, parsed_event)
            self._compare_extra_data_output(test_case_id, extra_outputs)
            self._print_pass_fail_statements(test_case_id)

    def _retrieve_log_capture(self):
        log_capture = self.log_capture_string.getvalue()
        # set new log_capture to clear previous entries
        self.log_capture_string = io.StringIO()
        self.stream_handler = logging.StreamHandler(self.log_capture_string)
        self.stream_handler.setLevel(logging.WARNING)
        self._logprep_logger.handlers.clear()
        self._logprep_logger.addHandler(self.stream_handler)
        return log_capture

    def _compare_logprep_outputs(self, test_case_id, logprep_output):
        test_case = self._test_cases.get(test_case_id, {})
        if test_case.expected_output:
            diff = self._compare_events(logprep_output, test_case.expected_output)
            self._extract_print_statements_from_diff(test_case_id, diff)

    def _compare_extra_data_output(self, test_case_id, logprep_extra_outputs):
        test_case = self._test_cases.get(test_case_id, {})
        prints = []
        if len(logprep_extra_outputs) > len(test_case.expected_extra_output):
            prints.append(
                f"{Fore.RED}There is at least one generated extra output that is unexpected"
            )
        if len(logprep_extra_outputs) < len(test_case.expected_extra_output):
            prints.append(f"{Fore.RED}There is at least one expected extra output missing")
        for expected_extra_output in test_case.expected_extra_output:
            expected_extra_output_key = list(expected_extra_output.keys())[0]
            has_matching_output = self._has_matching_logprep_output(
                expected_extra_output,
                expected_extra_output_key,
                logprep_extra_outputs,
            )
            if not has_matching_output:
                prints.append(
                    f"{Fore.RED}For the following extra output, "
                    "no matching extra output was generated by logprep",
                )
                prints.append(expected_extra_output)
        if prints:
            self._test_cases[test_case_id].failed = True
            self._test_cases[test_case_id].report.extend(prints)

    def _compare_events(self, generated, expected):
        ignore_value_search_results = expected | grep("<IGNORE_VALUE>")
        optional_keys_search_results = expected | grep("<OPTIONAL_KEY>")
        missing_keys = self._check_keys_of_ignored_values(
            generated, ignore_value_search_results.get("matched_values")
        )
        ignore_paths = []
        if "matched_values" in ignore_value_search_results:
            path = list(ignore_value_search_results["matched_values"])
            ignore_paths.extend([re.escape(path) for path in path])
        if "matched_values" in optional_keys_search_results:
            path = list(optional_keys_search_results["matched_values"])
            ignore_paths.extend([re.escape(path) for path in path])
        diff = DeepDiff(
            expected,
            generated,
            ignore_order=True,
            report_repetition=True,
            exclude_regex_paths=ignore_paths,
        )
        if missing_keys:
            diff.update({"dictionary_item_removed": missing_keys})
        return diff

    def _extract_print_statements_from_diff(self, test_case_id, diff):
        if not diff:
            return
        prints = []
        if "dictionary_item_removed" in diff:
            prints.append(
                f"{Fore.RED}Following expected items are missing in the generated logprep output:",
            )
            for item in diff["dictionary_item_removed"]:
                prints.append(f" - {item}")
        if "dictionary_item_added" in diff:
            prints.append(f"{Fore.RED}Following unexpected values were generated by logprep")
            for item in diff["dictionary_item_added"]:
                prints.append(f" - {item}")
        if "values_changed" in diff:
            prints.append(
                f"{Fore.RED}Following values differ between generated and expected output",
            )
            for key, value in diff["values_changed"].items():
                prints.append(f" - {key}: {self._rewrite_output(str(value))}")
        if prints:
            self._test_cases[test_case_id].failed = True
            self._test_cases[test_case_id].report.extend(prints)

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
                diff = self._compare_events(
                    logprep_extra_output[logprep_extra_output_key],
                    expected_extra_output[expected_extra_output_key],
                )
                if diff is not None:
                    has_matching_output = True
        return has_matching_output

    def _print_pass_fail_statements(self, test_case_id):
        test_case = self._test_cases.get(test_case_id, {})
        status = f"{Style.BRIGHT}{Fore.GREEN} PASSED"
        if not test_case.expected_output:
            status = f"{Style.BRIGHT}{Fore.RESET} SKIPPED - (no expected output given)"
        elif len(test_case.report) > 0:
            status = f"{Style.BRIGHT}{Fore.RED} FAILED"
        elif test_case.warnings:
            status = f"{Style.BRIGHT}{Fore.YELLOW} PASSED - (with warnings)"

        print(f"{Fore.BLUE} Test Case: {Fore.CYAN}{test_case_id} {status}{Style.RESET_ALL}")

    def _print_test_reports(self):
        if not any(case.failed for case in self._test_cases.values()):
            return
        print(Style.BRIGHT + "# Test Cases Detailed Reports:" + Style.RESET_ALL)
        for test_case_id, test_case in self._test_cases.items():
            if (test_case.warnings or test_case.report) and test_case.expected_output:
                self._print_long_test_result(test_case_id, test_case)
                print()

    def _print_long_test_result(self, test_case_id, test_case):
        report_title = f"test report for '{test_case_id}'"
        print(f"{Fore.RED}{Style.BRIGHT}↓ {report_title} ↓ {Style.RESET_ALL}")
        print_logprep_output = True
        if test_case.warnings and not test_case.report:
            print(Fore.GREEN + "Test passed, but with following warnings:" + Fore.RESET)
            print(test_case.warnings)
            print_logprep_output = False
        if test_case.warnings and test_case.report:
            print(Fore.RED + "Logprep Warnings:" + Fore.RESET)
            print(test_case.warnings)
        for statement in test_case.report:
            if isinstance(statement, (dict, list)):
                pprint(statement)
            else:
                print(statement)
        if print_logprep_output:
            print(Fore.RED + "Logprep Event Output:" + Fore.RESET)
            pprint(test_case.generated_output)
            print(Fore.RED + "Logprep Extra Data Output:" + Fore.RESET)
            pprint(test_case.generated_extra_output)
        print(f"{Fore.RED}{Style.BRIGHT}↑ {report_title} ↑ {Style.RESET_ALL}")

    def _print_test_summary(self):
        print(Fore.RESET + Style.BRIGHT + "# Test Overview" + Style.RESET_ALL)
        total_cases = len(self._test_cases)
        failed_cases = sum(case.failed for case in self._test_cases.values())
        print(f"Failed tests: {failed_cases}")
        print(f"Total test cases: {total_cases}")
        if total_cases:
            success_rate = (total_cases - failed_cases) / total_cases * 100
            print(f"Success rate: {success_rate:.2f}%")

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

    def _group_path_by_test_case(self, data_directory, file_paths):
        test_cases = {}
        for filename in file_paths:
            test_case_id = self._strip_input_file_type(filename)
            if test_case_id not in test_cases:
                test_cases[test_case_id] = self.TestCase()
            document = [{}]
            try:
                document = parse_json(os.path.join(data_directory, filename))
            except JSONDecodeError as error:
                test_cases[test_case_id].failed = True
                error_print = f"Json-Error decoding file {filename}: {error}"
                test_cases[test_case_id].report.append(error_print)
            if "_in.json" in filename:
                test_cases[test_case_id].input_document = document[0]
            if "_out.json" in filename:
                test_cases[test_case_id].expected_output = document[0]
            if "_out_extra.json" in filename:
                test_cases[test_case_id].expected_extra_output = document
        return test_cases

    def _strip_input_file_type(self, filename):
        """Remove the input file suffix to identify the case name"""
        filename = filename.replace("_in", "")
        filename = filename.replace("_out_extra", "")
        filename = filename.replace("_out", "")
        filename = filename.replace(".json", "*")
        return filename

    def _rewrite_output(self, statement):
        statement = statement.replace("new_value", "generated")
        statement = statement.replace("old_value", "expected")
        return statement
