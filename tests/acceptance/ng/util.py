#!/usr/bin/python3
# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=line-too-long
import contextlib
import http.server
import inspect
import json
import re
import socketserver
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager
from copy import deepcopy
from functools import partial
from importlib import import_module
from logging import DEBUG, basicConfig, getLogger
from os import makedirs, path
from pathlib import Path
from typing import Generator

import psutil

from logprep.ng.abc.processor import Processor
from logprep.ng.runner import Runner
from logprep.ng.util.configuration import Configuration
from logprep.ng.util.defaults import RULE_FILE_EXTENSIONS
from logprep.registry import Registry
from logprep.util.decorators import timeout
from logprep.util.helper import recursive_compare, remove_file_if_exists
from logprep.util.json_handling import parse_jsonl
from tests.unit.ng.processor.base import BaseProcessorTestCase

basicConfig(level=DEBUG, format="%(asctime)-15s %(name)-5s %(levelname)-8s: %(message)s")
logger = getLogger("Logprep-Test")


class HTTPServerForTesting(socketserver.TCPServer):
    allow_reuse_address = True

    @classmethod
    def run_http_server(cls, port=32000, directory=None):
        with HTTPServerForTesting(
            ("", port), partial(http.server.SimpleHTTPRequestHandler, directory=directory)
        ) as httpd:
            try:
                cls.httpd = httpd
                cls.httpd.serve_forever()
            finally:
                cls.httpd.server_close()

    @classmethod
    @contextlib.contextmanager
    def run_in_thread(cls, port=32000, directory=None):
        """Context manager to run the server in a separate thread"""
        cls.thread = threading.Thread(
            target=cls.run_http_server, kwargs={"port": port, "directory": directory}
        )
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


async def get_runner_outputs(
    runner: Runner,
) -> dict[str, dict]:
    config = runner._config  # pylint: disable=protected-access

    all_named_outputs = [*config.output.items(), *config.error_output.items()]

    output_paths_std = {
        name: output_config["output_file"]
        for name, output_config in all_named_outputs
        if "output_file" in output_config
    }

    output_paths_custom = {
        f"{name}_custom": output_config["output_file_custom"]
        for name, output_config in all_named_outputs
        if "output_file_custom" in output_config
    }

    output_paths = {**output_paths_std, **output_paths_custom}

    for output_path in output_paths.values():
        remove_file_if_exists(output_path)

    try:
        await runner.run()
    except SystemExit as error:
        assert not error.code, f"Runner exited with code {error.code}"

    return {name: parse_jsonl(path) for name, path in output_paths.items()}


async def get_test_outputs(
    config_path: str | Path,
) -> dict[str, dict]:
    runner = Runner(await Configuration.from_sources([str(config_path)]))
    return await get_runner_outputs(runner=runner)


class SingleMessageConsumerJsonMock:
    def __init__(self, record):
        self.record = json.dumps(record, separators=(",", ":"))

    # pylint: disable=unused-argument
    def poll(self, _):
        return RecordMock(self.record, None)

    # pylint: enable=unused-argument


class TmpFileProducerMock:
    def __init__(self, tmp_path):
        self.tmp_path = tmp_path

    def produce(self, target, value):
        with open(self.tmp_path, "a", encoding="utf-8") as tmp_file:
            tmp_file.write(f"{target} {value.decode()}\n")

    def poll(self, _): ...


def get_default_logprep_config(pipeline_config, with_hmac=True) -> Configuration:
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
                "output_file": tempfile.mkstemp(suffix="output.jsonl")[1],
                "output_file_custom": tempfile.mkstemp(suffix="custom.jsonl")[1],
            }
        },
    }

    if with_hmac:
        input = config_yml.get("input")
        assert input
        input_config = input.get("jsonl")
        input_config["preprocessing"] = {
            "hmac": {
                "target": "<RAW_MSG>",
                "key": "secret",
                "output_field": "hmac",
            }
        }

    return Configuration(**config_yml)


def _start_logprep(config_path: str | Path, env: dict | None = None) -> subprocess.Popen[bytes]:
    if env is None:
        env = {}
    env.update({"PYTHONPATH": "."})

    return subprocess.Popen(
        [sys.executable, "logprep/run_ng.py", "run", str(config_path)],
        shell=False,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        close_fds=True,
    )


def _stop_logprep(proc: subprocess.Popen) -> None:
    if proc is None or not psutil.pid_exists(proc.pid):
        return

    main_process = psutil.Process(proc.pid)

    to_terminate: list[psutil.Process] = [main_process, *main_process.children(recursive=True)]

    logger.debug("terminating pids [%s]", ", ".join([str(p.pid) for p in to_terminate]))

    for p in to_terminate:
        try:
            if p.is_running():
                p.terminate()
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            pass

    _, still_alive = psutil.wait_procs(to_terminate, timeout=5)

    logger.debug("killing pids [%s]", ", ".join([str(p.pid) for p in still_alive]))

    for p in still_alive:
        try:
            if p.is_running():
                p.kill()
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            pass

    _, still_alive = psutil.wait_procs(to_terminate, timeout=5)

    if still_alive:
        logger.warning(
            "failed to kill processes [%s]", ", ".join([str(p.pid) for p in still_alive])
        )


@contextmanager
def run_logprep(
    config_path: str | Path, env: dict | None = None
) -> Generator[subprocess.Popen, None, None]:
    process = _start_logprep(config_path, env)
    try:
        yield process
    except Exception as error:
        print(error)
    finally:
        _stop_logprep(process)


def wait_for_output(
    proc: subprocess.Popen[bytes],
    expected_output: str,
    test_timeout: int = 10,
    forbidden_outputs: tuple[str, ...] = ("Invalid", "Exception", "Critical", "Error", "ERROR"),
) -> re.Match[str]:
    @timeout(test_timeout)
    def wait_for_output_inner() -> re.Match[str]:
        assert proc.stdout
        output_line = proc.stdout.readline()
        while True:
            decoded_line = output_line.decode("utf8")
            match = re.search(expected_output, decoded_line)
            if match:
                return match
            for forbidden_output in forbidden_outputs:
                assert not re.search(forbidden_output, decoded_line), output_line
            output_line = proc.stdout.readline()

    return wait_for_output_inner()


def get_full_pipeline(exclude=None):
    processors = [
        processor_name
        for processor_name, class_type in Registry.get_classes().items()
        if issubclass(class_type, Processor)
    ]
    if exclude:
        processors = filter(lambda x: x not in exclude, processors)
    processor_test_modules = []
    for processor in processors:
        processor_test_modules.append(
            import_module(f"tests.unit.ng.processor.{processor}.test_{processor}")  # nosemgrep
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


async def convert_to_http_config(config: Configuration, endpoint) -> Configuration:
    config_path = Path(tempfile.gettempdir() + "/config.yml")
    config_path.write_text(config.as_yaml(), encoding="utf-8")
    config = await Configuration.from_sources([str(config_path)])
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
    for processor_config in config.pipeline:
        name, value = processor_config.popitem()
        rules = []
        for rule in value["rules"]:
            match rule:
                case str():
                    rule_path = Path(rule)
                    if rule_path.is_file():
                        rules.append(str(rule_path))
                    if rule_path.is_dir():
                        files = (
                            str(p)
                            for p in Path(rule_path).glob("**/*")
                            if p.suffix in RULE_FILE_EXTENSIONS
                        )
                        rules.extend(files)
        value["rules"] = [f"{endpoint}/{rule}" for rule in rules]
        for config_key, config_value in value.items():
            if config_key in http_fields:
                value.update({config_key: f"{endpoint}/{config_value}"})
        processor_config.update({name: value})
        assert True
    return config
