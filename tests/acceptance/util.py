#!/usr/bin/python3
# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=line-too-long
import contextlib
import threading
import socketserver
import http.server
import inspect
import json
import os
import re
import signal
import subprocess
import sys
import time
from copy import deepcopy
from importlib import import_module
from logging import DEBUG, basicConfig, getLogger
from os import makedirs, path

from logprep.abc.processor import Processor
from logprep.registry import Registry
from logprep.util.decorators import timeout
from logprep.util.helper import recursive_compare
from logprep.util.rule_dry_runner import get_patched_runner, get_runner_outputs
from tests.unit.processor.base import BaseProcessorTestCase

basicConfig(level=DEBUG, format="%(asctime)-15s %(name)-5s %(levelname)-8s: %(message)s")
logger = getLogger("Logprep-Test")


class TestingHTTPServer(socketserver.TCPServer):
    allow_reuse_address = True

    @classmethod
    def run_http_server(cls, port=32000):
        with TestingHTTPServer(("", port), http.server.SimpleHTTPRequestHandler) as httpd:
            try:
                cls.httpd = httpd
                cls.httpd.serve_forever()
            finally:
                cls.httpd.server_close()

    @classmethod
    @contextlib.contextmanager
    def run_in_thread(cls):
        """Context manager to run the server in a separate thread"""
        cls.thread = threading.Thread(target=cls.run_http_server)
        cls.thread.start()
        yield
        cls.stop()

    @classmethod
    def stop(cls):
        if hasattr(cls, "httpd"):
            cls.httpd.shutdown()
        if hasattr(cls, "thread"):
            cls.thread.join()


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


def start_logprep(config_path: str) -> subprocess.Popen:
    environment = {"PYTHONPATH": "."}
    return subprocess.Popen(  # nosemgrep
        f"{sys.executable} logprep/run_logprep.py {config_path}",
        shell=True,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        close_fds=True,
    )


def wait_for_output(proc, expected_output, test_timeout=10):
    @timeout(test_timeout)
    def wait_for_output_inner(proc, expected_output):
        output = proc.stdout.readline()
        while expected_output not in output.decode("utf8"):
            output = proc.stdout.readline()
            time.sleep(0.1)  # nosemgrep

    wait_for_output_inner(proc, expected_output)


def stop_logprep(proc=None):
    if proc:
        proc.send_signal(signal.SIGINT)
        try:
            wait_for_output(proc, "Shutdown complete", test_timeout=10)
        except TimeoutError:
            proc.kill()

    output = subprocess.check_output("ps -x | grep run_logprep", shell=True)  # nosemgrep
    for line in output.decode("utf8").splitlines():
        process_id = re.match(r"^(\s+)?(\d+)\s.+", line)
        process_id = process_id.group(2) if process_id else None
        try:
            if process_id is not None:
                os.kill(int(process_id), signal.SIGKILL)
        except ProcessLookupError:
            pass


def get_full_pipeline():
    processors = [
        processor_name
        for processor_name, value in Registry.mapping.items()
        if issubclass(value, Processor)
    ]
    processor_test_modules = []
    for processor in processors:
        processor_test_modules.append(
            import_module(f"tests.unit.processor.{processor}.test_{processor}")  # nosemgrep
        )
    processor_configs = []
    for test_module in processor_test_modules:
        processor_configs.append(
            [
                (test_class[1].CONFIG.get("type"), test_class[1].CONFIG)
                for test_class in inspect.getmembers(test_module, inspect.isclass)
                if issubclass(test_class[1], BaseProcessorTestCase)
            ][1]
        )
    return [{processor_name: config} for processor_name, config in processor_configs if config]


def convert_to_http_config(config: dict, endpoint) -> dict:
    config = deepcopy(config)
    http_fields = [
        "regex_mapping",
        "html_replace_fields",
        "tree_config",
        "pubkey_analyst",
        "pubkey_depseudo",
        "alert_ip_list_path",
        "schema",
        "template",
    ]
    for processor_config in config.get("pipeline"):
        name, value = processor_config.popitem()
        for rule_kind in ("specific_rules", "generic_rules"):
            rules = Processor.resolve_directories(value.get(rule_kind))
            value[rule_kind] = [f"{endpoint}/{rule}" for rule in rules]
        for config_key, config_value in value.items():
            if config_key in http_fields:
                value.update({config_key: f"{endpoint}/{config_value}"})
        processor_config.update({name: value})
        assert True
    return config
