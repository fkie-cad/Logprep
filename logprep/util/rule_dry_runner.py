#!/usr/bin/python3
"""
Dry Run
-------

Rules can be tested by executing them in a dry run of Logprep.
Instead of the connectors defined in the configuration file,
the dry run takes a path parameter to an input JSON (line) file that contains log messages.
The output is displayed in the console and changes made by Logprep are being highlighted:

..  code-block:: bash
    :caption: Directly with Python

    PYTHONPATH="." python3 logprep/run_logprep.py $CONFIG --dry-run $EVENTS

..  code-block:: bash
    :caption: With a PEX file

    logprep.pex $CONFIG --dry-run $EVENTS

Where :code:`$CONFIG` is the path to a configuration file
(see :doc:`configuration/configurationdata`).
The only required section in the configuration is :code:`pipeline`
(see tests/testdata/config/config-dry-run.yml for an example).
The remaining options are set internally or are being ignored.

:code:`$EVENTS` is the path to a file with one or multiple log messages.
A single log message can be provided with a file containing a plain json or wrapped in brackets
(beginning with `[` and ending with `]`).
For multiple events it must be a list wrapped inside brackets, while each log object separated by a
comma.
By specifying the parameter :code:`--dry-run-input-type jsonl` a list of JSON lines can be used
instead.
Additional output, like pseudonyms, will be printed if :code:`--dry-run-full-output` is added.

..  code-block:: bash
    :caption: Example for execution with a JSON lines file (dry-run-input-type jsonl) printing all results, including pseudonyms (dry-run-full-output)

    logprep.pex tests/testdata/config/config-dry-run.yml --dry-run tests/testdata/input_logdata/wineventlog_raw.jsonl --dry-run-input-type jsonl --dry-run-full-output
"""

import json
import shutil
import tempfile
from copy import deepcopy
from difflib import ndiff

from colorama import Fore, Back
from ruamel.yaml import YAML

from logprep.runner import Runner
from logprep.util.configuration import Configuration
from logprep.util.getter import GetterFactory
from logprep.util.helper import (
    color_print_line,
    recursive_compare,
    remove_file_if_exists,
    color_print_title,
)
from logprep.util.json_handling import parse_jsonl, parse_json

yaml = YAML(typ="safe", pure=True)


def get_runner_outputs(patched_runner) -> list:
    # pylint: disable=protected-access
    """
    Extracts the outputs of a patched logprep runner.

    Parameters
    ----------
    patched_runner : Runner
        The patched logprep runner

    Returns
    -------
    parsed_outputs : list
        A list of logprep outputs containing events, extra outputs like pre-detections or pseudonyms
        and errors
    """
    parsed_outputs = [None, None, None]
    output_config = list(patched_runner._configuration.get("output").values())[0]
    output_paths = [
        output_path for key, output_path in output_config.items() if "output_file" in key
    ]

    for output_path in output_paths:
        remove_file_if_exists(output_path)

    patched_runner.start()

    for index, output_path in enumerate(output_paths):
        parsed_outputs[index] = parse_jsonl(output_path)
        remove_file_if_exists(output_path)

    return parsed_outputs


def get_patched_runner(config_path, logger):
    """
    Creates a patched runner that bypasses check to obtain non singleton instance and the runner
    won't continue iterating on an empty pipeline.

    Parameters
    ----------
    config_path : str
        The logprep configuration that should be used for the patched runner
    logger : Logger
        The application logger the runner should use

    Returns
    -------
    runner : Runner
        The patched logprep runner
    """
    runner = Runner(bypass_check_to_obtain_non_singleton_instance=True)
    runner.set_logger(logger)
    runner.load_configuration(config_path)

    # patch runner to stop on empty pipeline
    def keep_iterating():
        """generator that stops on first iteration"""
        return  # nosemgrep
        yield

    runner._keep_iterating = keep_iterating  # pylint: disable=protected-access

    return runner


class DryRunner:
    """Used to run pipeline with given events and show changes made by processing."""

    def __init__(self, dry_run: str, config_path: str, full_output: bool, use_json: bool, logger):
        self._tmp_path = tempfile.mkdtemp()
        self.patched_config_path = Configuration.patch_yaml_with_json_connectors(
            original_config_path=config_path, output_dir=self._tmp_path, input_file_path=dry_run
        )
        self._full_output = full_output
        self._use_json = use_json
        self._logger = logger

    def run(self):
        """Run the dry runner."""
        patched_runner = get_patched_runner(self.patched_config_path, self._logger)
        test_output, test_output_custom, test_output_error = get_runner_outputs(patched_runner)
        config_yaml = GetterFactory.from_string(self.patched_config_path).get_yaml()
        input_path = config_yaml.get("input", {}).get("patched_input", {}).get("documents_path")
        input_data = parse_json(input_path) if self._use_json else parse_jsonl(input_path)
        self._print_output_results(input_data, test_output, test_output_custom, test_output_error)
        shutil.rmtree(self._tmp_path)

    def _print_output_results(self, input_data, test_output, test_output_custom, test_output_error):
        """Call the print methods that correspond to the output type"""
        if not test_output_error:
            self._print_transformed_events(input_data, test_output, test_output_custom)
        if self._full_output and test_output_custom and not test_output_error:
            self._print_pseudonyms(test_output_custom)
            self._print_predetections(test_output_custom)
        if test_output_error:
            self._print_errors(test_output_error)

    def _print_transformed_events(self, input_data, test_output, test_output_custom):
        """
        Print the differences between input and output event as well as corresponding pre-detections
        """
        transformed_cnt = 0
        for idx, test_item in enumerate(test_output):
            test_copy = deepcopy(test_item)
            input_copy = deepcopy(input_data[idx])
            difference = recursive_compare(test_copy, input_copy)
            if difference:
                test_json = json.dumps(test_item, sort_keys=True, indent=4)
                input_path_json = json.dumps(input_data[idx], sort_keys=True, indent=4)
                diff = ndiff(input_path_json.splitlines(), test_json.splitlines())
                color_print_title(Back.CYAN, "PROCESSED EVENT")
                self._print_ndiff_items(diff)
                transformed_cnt += 1

            for test_item_custom in test_output_custom:
                detector_id = test_item_custom.get("pre_detection_id")
                if detector_id and detector_id == test_item.get("pre_detection_id"):
                    color_print_title(Back.YELLOW, "PRE-DETECTION FOR PRECEDING EVENT")
                    test_json_custom = json.dumps(test_item_custom, sort_keys=True, indent=4)
                    color_print_line(Back.BLACK, Fore.YELLOW, test_json_custom)
        color_print_title(Back.WHITE, f"TRANSFORMED EVENTS: {transformed_cnt}/{len(test_output)}")

    def _print_ndiff_items(self, diff):
        """
        Print the results from the ndiff library with colored lines, depending on the diff type
        """
        for item in diff:
            if item.startswith("- "):
                color_print_line(Back.BLACK, Fore.RED, item)
            elif item.startswith("+ "):
                color_print_line(Back.BLACK, Fore.GREEN, item)
            elif item.startswith("? "):
                color_print_line(Back.BLACK, Fore.WHITE, item)
            else:
                color_print_line(Back.BLACK, Fore.CYAN, item)

    def _print_pseudonyms(self, test_output_custom):
        """Print only the pseudonyms from all custom outputs"""
        color_print_title(Back.MAGENTA, "ALL PSEUDONYMS")
        for test_item in test_output_custom:
            if "pseudonym" in test_item.keys() and "origin" in test_item.keys():
                test_json = json.dumps(test_item, sort_keys=True, indent=4)
                color_print_line(Back.BLACK, Fore.MAGENTA, test_json)

    def _print_predetections(self, test_output_custom):
        """Print only the pre-detections from all custom outputs"""
        color_print_title(Back.YELLOW, "ALL PRE-DETECTIONS")
        for test_item in test_output_custom:
            if "pre_detection_id" in test_item.keys():
                test_json = json.dumps(test_item, sort_keys=True, indent=4)
                color_print_line(Back.BLACK, Fore.YELLOW, test_json)

    def _print_errors(self, test_output_error):
        """Print all errors"""
        for test_items in test_output_error:
            color_print_title(Back.RED, "ERROR")

            json_message = test_items.get("error_message")
            color_print_line(Back.BLACK, Fore.RED, json_message)

            json_original = test_items.get("document_received")
            json_processed = test_items.get("document_processed")

            diff = ndiff(str(json_original), str(json_processed))
            color_print_title(Back.YELLOW, "PARTIALLY PROCESSED EVENT")
            self._print_ndiff_items(diff)
        log_message = "^^^ RESULTS CAN NOT BE SHOWN UNTIL ALL ERRORS HAVE BEEN FIXED ^^^"
        color_print_line(Back.RED, Fore.WHITE, log_message)
