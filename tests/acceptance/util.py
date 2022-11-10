#!/usr/bin/python3
# pylint: disable=protected-access
# pylint: disable=missing-docstring
import json
from copy import deepcopy
from logging import getLogger, basicConfig, DEBUG
from os import path, makedirs

from logprep.util.helper import recursive_compare
from logprep.util.rule_dry_runner import get_patched_runner, get_runner_outputs

basicConfig(level=DEBUG, format="%(asctime)-15s %(name)-5s %(levelname)-8s: %(message)s")
logger = getLogger("Logprep-Test")


class RecordMock:
    def __init__(self, record_value, record_error):
        self.record_value = record_value
        self.record_error = record_error

    @staticmethod
    def partition():
        return 0

    def value(self):
        if self.record_value is None:
            return None
        return self.record_value.encode("utf-8")

    def error(self):
        if self.record_error is None:
            return None
        return self.record_error

    @staticmethod
    def offset():
        return -1


def get_difference(test_output, expected_output):
    for idx, _ in enumerate(test_output):
        test_event = deepcopy(test_output[idx])
        expected_event = deepcopy(expected_output[idx])
        difference = recursive_compare(test_event, expected_event)
        if difference:
            return {"event_line_no": idx, "difference": difference}
    return {"event_line_no": None, "difference": (None, None)}


def store_latest_test_output(target_output_identifier, output_of_test):
    """Store output for test.

    This can be used to create expected outputs for new rules.
    The resulting file can be used as it is.

    """

    output_dir = "tests/testdata/out"
    latest_output_path = path.join(output_dir, f"latest_{target_output_identifier}.out")

    if not path.exists(output_dir):
        makedirs(output_dir)

    with open(latest_output_path, "w", encoding="utf-8") as latest_output:
        for test_output_line in output_of_test:
            latest_output.write(json.dumps(test_output_line) + "\n")


def get_test_output(config_path):
    patched_runner = get_patched_runner(config_path, logger)
    return get_runner_outputs(patched_runner=patched_runner)


class SingleMessageConsumerJsonMock:
    def __init__(self, record):
        self.record = json.dumps(record, separators=(",", ":"))

    # pylint: disable=unused-argument
    def poll(self, timeout):
        return RecordMock(self.record, None)

    # pylint: enable=unused-argument


class TmpFileProducerMock:
    def __init__(self, tmp_path):
        self.tmp_path = tmp_path

    def produce(self, target, value):
        with open(self.tmp_path, "a", encoding="utf-8") as tmp_file:
            tmp_file.write(f"{target} {value.decode()}\n")

    def poll(self, _):
        ...


def get_default_logprep_config(pipeline_config, with_hmac=True):
    config_yml = {
        "version": "1",
        "process_count": 1,
        "timeout": 0.1,
        "profile_pipelines": False,
        "pipeline": pipeline_config,
        "input": {
            "jsonl": {
                "type": "jsonl_input",
                "documents_path": "tests/testdata/input_logdata/kafka_raw_event_for_pre_detector.jsonl",
            }
        },
        "output": {
            "jsonl": {
                "type": "jsonl_output",
                "output_file": "tests/testdata/acceptance/test_kafka_data_processing_acceptance.out",
                "output_file_custom": "tests/testdata/acceptance/test_kafka_data_processing_acceptance_custom.out",
                "output_file_error": "tests/testdata/acceptance/test_kafka_data_processing_acceptance_error.out",
            }
        },
    }

    if with_hmac:
        input_config = config_yml.get("input").get("jsonl")
        input_config["preprocessing"] = {
            "hmac": {
                "target": "<RAW_MSG>",
                "key": "secret",
                "output_field": "hmac",
            }
        }

    return config_yml
