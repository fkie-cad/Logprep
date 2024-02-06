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

    PYTHONPATH="." python3 logprep/run_logprep.py test dry-run $CONFIG $EVENTS

..  code-block:: bash
    :caption: With a PEX file

    logprep.pex test dry-run $CONFIG $EVENTS

Where :code:`$CONFIG` is the path to a configuration file
(see :ref:`configuration`).
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
from functools import cached_property
from pathlib import Path

from colorama import Back, Fore
from ruamel.yaml import YAML

from logprep.framework.pipeline import Pipeline
from logprep.util.auto_rule_tester.auto_rule_corpus_tester import (
    align_extra_output_formats,
)
from logprep.util.configuration import Configuration
from logprep.util.getter import GetterFactory
from logprep.util.helper import color_print_line, color_print_title, recursive_compare

yaml = YAML(typ="safe", pure=True)


class DryRunner:
    """Used to run pipeline with given events and show changes made by processing."""

    @cached_property
    def _tmp_path(self):
        return tempfile.mkdtemp()

    @cached_property
    def _pipeline(self):
        patched_config = Configuration()
        patched_config.input = {
            "patched_input": {
                "type": f"{'json' if self._use_json else 'jsonl'}_input",
                "documents_path": str(self._input_file_path),
            }
        }
        input_config = self._config.input
        connector_name = list(input_config.keys())[0]
        if "preprocessing" in input_config[connector_name]:
            patched_config.input["patched_input"] |= {
                "preprocessing": input_config[connector_name]["preprocessing"]
            }
        patched_config.pipeline = self._config.pipeline
        pipeline = Pipeline(config=patched_config)
        return pipeline

    @cached_property
    def _input_documents(self):
        document_getter = GetterFactory.from_string(self._input_file_path)
        if self._use_json:
            return [document_getter.get_json()]
        return document_getter.get_jsonl()

    def __init__(
        self, input_file_path: str, config: Configuration, full_output: bool, use_json: bool, logger
    ):
        self._input_file_path = input_file_path
        self._config = config
        self._full_output = full_output
        self._use_json = use_json
        self._logger = logger

    def run(self):
        """Run the dry runner."""
        transformed_cnt = 0
        output_count = 0
        for input_document in self._input_documents:
            test_output, test_output_custom = self._pipeline.process_pipeline()
            test_output_custom = align_extra_output_formats(test_output_custom)
            if test_output:
                output_count += 1
            diff = self._print_output_results(input_document, test_output, test_output_custom)
            if diff:
                transformed_cnt += 1
        color_print_title(Back.WHITE, f"TRANSFORMED EVENTS: {transformed_cnt}/{output_count}")
        shutil.rmtree(self._tmp_path)

    def _print_output_results(self, input_document, test_output, test_output_custom):
        test_copy = deepcopy(test_output)
        input_copy = deepcopy(input_document)
        difference = recursive_compare(test_copy, input_copy)
        if difference:
            test_json = json.dumps(test_output, sort_keys=True, indent=4)
            input_path_json = json.dumps(input_document, sort_keys=True, indent=4)
            diff = ndiff(input_path_json.splitlines(), test_json.splitlines())
            color_print_title(Back.CYAN, "PROCESSED EVENT")
            self._print_ndiff_items(diff)
        if self._full_output and test_output_custom:
            self._print_custom_outputs(test_output_custom)
        return difference

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

    def _print_custom_outputs(self, test_output_custom):
        color_print_title(Back.MAGENTA, "CUSTOM OUTPUTS")
        for custom_output in test_output_custom:
            output_target, output = list(custom_output.items())[0]
            color_print_title(Back.YELLOW, f"Output Target: {output_target}")
            test_json = json.dumps(output, sort_keys=True, indent=4)
            color_print_line(Back.BLACK, Fore.YELLOW, test_json)
