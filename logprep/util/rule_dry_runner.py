#!/usr/bin/python3
"""This module runs the pipeline for specified events and shows how processing changed them."""

from os import path
from copy import deepcopy

from difflib import ndiff
import tempfile
import shutil
import json

from ruamel.yaml import YAML
from colorama import Fore, Back

from logprep.runner import Runner
from logprep.util.helper import print_color, recursive_compare, remove_file_if_exists
from logprep.util.json_handling import dump_config_as_file, parse_jsonl, parse_json

yaml = YAML(typ="safe", pure=True)


def get_test_output_multi(config_path, logger):
    patched_runner = get_patched_runner(config_path, logger)

    parsed_outputs = list()
    output_paths = list()
    output_paths.append(patched_runner._configuration["connector"].get("output_path", None))
    output_paths.append(patched_runner._configuration["connector"].get("output_path_custom", None))
    output_paths.append(patched_runner._configuration["connector"].get("output_path_errors", None))
    output_paths = [output_path for output_path in output_paths if output_path]

    for output_path in output_paths:
        remove_file_if_exists(output_path)

    patched_runner.start()

    for output_path in output_paths:
        parsed_outputs.append(parse_jsonl(output_path))
        remove_file_if_exists(output_path)

    return parsed_outputs


def get_patched_runner(config_path, logger):
    runner = Runner(bypass_check_to_obtain_non_singleton_instance=True)
    runner.set_logger(logger)
    runner.load_configuration(config_path)
    # patch runner to stop on empty pipeline
    runner._keep_iterating = lambda: False

    return runner


class DryRunner:
    """Used to run pipeline with given events and show changes made by processing."""

    def __init__(self, dry_run: str, config_path: str, full_output: str, use_json: bool, logger):
        with open(config_path, "r") as yaml_file:
            self._config_yml = yaml.load(yaml_file)

        self._full_output = full_output
        self._use_json = use_json

        self._config_yml["connector"] = {
            "type": "writer_json_input" if use_json else "writer",
            "input_path": dry_run,
        }
        self._config_yml["process_count"] = 1

        self._logger = logger

    def run(self):
        """Run the dry runner."""
        tmp_path = tempfile.mkdtemp()

        self._config_yml["connector"]["output_path"] = path.join(tmp_path, "output.jsonl")
        self._config_yml["connector"]["output_path_custom"] = path.join(
            tmp_path, "output_custom.jsonl"
        )
        self._config_yml["connector"]["output_path_errors"] = path.join(
            tmp_path, "output_errors.jsonl"
        )

        config_path = path.join(tmp_path, "generated_config.yml")
        dump_config_as_file(config_path, self._config_yml)

        test_output, test_output_custom, test_output_error = get_test_output_multi(
            config_path, self._logger
        )

        input_path = self._config_yml["connector"]["input_path"]
        input_data = parse_json(input_path) if self._use_json else parse_jsonl(input_path)

        if not test_output_error:
            transformed_cnt = 0
            for idx, test_item in enumerate(test_output):
                test_copy = deepcopy(test_item)
                input_copy = deepcopy(input_data[idx])
                difference = recursive_compare(test_copy, input_copy)
                if difference:
                    test_json = json.dumps(test_item, sort_keys=True, indent=4)
                    input_path_json = json.dumps(input_data[idx], sort_keys=True, indent=4)
                    diff = ndiff(input_path_json.splitlines(), test_json.splitlines())
                    print_color(Back.CYAN, Fore.BLACK, "------ PROCESSED EVENT ------")
                    for item in diff:
                        if item.startswith("- "):
                            print_color(Back.BLACK, Fore.RED, item)
                        elif item.startswith("+ "):
                            print_color(Back.BLACK, Fore.GREEN, item)
                        elif item.startswith("? "):
                            print_color(Back.BLACK, Fore.WHITE, item)
                        else:
                            print_color(Back.BLACK, Fore.CYAN, item)
                    transformed_cnt += 1

                for test_item_custom in test_output_custom:
                    detector_id = test_item_custom.get("pre_detection_id")
                    if detector_id and detector_id == test_item.get("pre_detection_id"):
                        print_color(
                            Back.YELLOW,
                            Fore.BLACK,
                            "------ PRE-DETECTION FOR PRECEDING EVENT ------",
                        )
                        test_json_custom = json.dumps(test_item_custom, sort_keys=True, indent=4)
                        print_color(Back.BLACK, Fore.YELLOW, test_json_custom)
            print_color(
                Back.WHITE,
                Fore.BLACK,
                f"------ TRANSFORMED EVENTS: {transformed_cnt}/{len(test_output)} ------",
            )

        if self._full_output and test_output_custom and not test_output_error:
            print_color(Back.MAGENTA, Fore.BLACK, "------ ALL PSEUDONYMS ------")
            for test_item in test_output_custom:
                if "pseudonym" in test_item.keys() and "origin" in test_item.keys():
                    test_json = json.dumps(test_item, sort_keys=True, indent=4)
                    print_color(Back.BLACK, Fore.MAGENTA, test_json)

            print_color(Back.YELLOW, Fore.BLACK, "------ ALL PRE-DETECTIONS ------")
            for test_item in test_output_custom:
                if "pre_detection_id" in test_item.keys():
                    test_json = json.dumps(test_item, sort_keys=True, indent=4)
                    print_color(Back.BLACK, Fore.YELLOW, test_json)

        if test_output_error:
            for test_items in test_output_error:
                print_color(Back.RED, Fore.YELLOW, "------ ERROR ------")

                json_message = json.dumps(test_items[0], sort_keys=True, indent=4)
                print_color(Back.BLACK, Fore.RED, json_message)

                json_original = json.dumps(test_items[1], sort_keys=True, indent=4)
                json_processed = json.dumps(test_items[2], sort_keys=True, indent=4)

                diff = ndiff(json_original.splitlines(), json_processed.splitlines())
                print_color(Back.YELLOW, Fore.RED, "------ PARTIALLY PROCESSED EVENT ------")
                for item in diff:
                    if item.startswith("- "):
                        print_color(Back.BLACK, Fore.RED, item)
                    elif item.startswith("+ "):
                        print_color(Back.BLACK, Fore.GREEN, item)
                    elif item.startswith("? "):
                        print_color(Back.BLACK, Fore.WHITE, item)
                    else:
                        print_color(Back.BLACK, Fore.YELLOW, item)

            print_color(
                Back.RED,
                Fore.WHITE,
                "^^^ COMPLETE PROCESSING RESULTS CAN NOT BE SHOWN UNTIL ALL ERRORS HAVE "
                "BEEN FIXED ^^^",
            )

        shutil.rmtree(tmp_path)
