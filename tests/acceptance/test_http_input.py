# pylint: disable=missing-docstring
# pylint: disable=line-too-long
import os
import re
import signal
import subprocess
import sys
import time
from logging import DEBUG, basicConfig, getLogger

import pytest
import requests
from logprep.util.json_handling import dump_config_as_file
from tests.acceptance.util import get_default_logprep_config

basicConfig(level=DEBUG, format="%(asctime)-15s %(name)-5s %(levelname)-8s: %(message)s")
logger = getLogger("Logprep-Test")


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


def wait_for_output(proc, expected_output):
    output = proc.stdout.readline()
    while not expected_output in output.decode("utf8"):
        output = proc.stdout.readline()
        time.sleep(0.1)  # nosemgrep


@pytest.fixture(name="config")
def config_fixture():
    pipeline = [
        {
            "normalizername": {
                "type": "normalizer",
                "specific_rules": ["tests/testdata/acceptance/normalizer/rules_static/specific"],
                "generic_rules": ["tests/testdata/acceptance/normalizer/rules_static/generic"],
                "regex_mapping": "tests/testdata/acceptance/normalizer/rules_static/regex_mapping.yml",
            }
        },
        {
            "selective_extractor": {
                "type": "selective_extractor",
                "specific_rules": ["tests/testdata/acceptance/selective_extractor/rules/specific"],
                "generic_rules": ["tests/testdata/acceptance/selective_extractor/rules/generic"],
            }
        },
    ]
    config = get_default_logprep_config(pipeline, with_hmac=False)
    config["input"] = {
        "testinput": {
            "type": "http_input",
            "uvicorn_config": {
                "host": "127.0.0.1",
                "port": 9000,
                "ssl_certfile": "tests/testdata/acceptance/http_input/cert.crt",
                "ssl_keyfile": "tests/testdata/acceptance/http_input/cert.key",
            },
            "endpoints": {"/json": "json", "/jsonl": "jsonl", "/plaintext": "plaintext"},
        }
    }
    return config


def teardown_function():
    # cleanup processes
    output = subprocess.check_output("ps -x | grep run_logprep", shell=True)  # nosemgrep
    for line in output.decode("utf8").splitlines():
        process_id = re.match(r"^\s+(\d+)\s.+", line).group(1)
        try:
            os.kill(int(process_id), signal.SIGKILL)
        except ProcessLookupError:
            pass


@pytest.mark.skipif(sys.version_info.minor < 7, reason="not supported for python 3.6")
def test_http_input_accepts_message_for_single_pipeline(tmp_path, config):
    output_path = tmp_path / "output.jsonl"
    config["output"] = {"testoutput": {"type": "jsonl_output", "output_file": str(output_path)}}
    config_path = str(tmp_path / "generated_config.yml")
    dump_config_as_file(config_path, config)
    proc = start_logprep(config_path)
    wait_for_output(proc, "Uvicorn running on https://127.0.0.1:9000")
    requests.post("https://127.0.0.1:9000/plaintext", data="my message", verify=False)  # nosemgrep
    time.sleep(0.5)  # nosemgrep
    assert "my message" in output_path.read_text()


@pytest.mark.skipif(sys.version_info.minor < 7, reason="not supported for python 3.6")
def test_http_input_accepts_message_for_two_pipelines(tmp_path, config):
    config["process_count"] = 2
    output_path = tmp_path / "output.jsonl"
    config["output"] = {"testoutput": {"type": "jsonl_output", "output_file": str(output_path)}}
    config_path = str(tmp_path / "generated_config.yml")
    dump_config_as_file(config_path, config)
    proc = start_logprep(config_path)
    wait_for_output(proc, "Uvicorn running on https://127.0.0.1:9001")
    requests.post(  # nosemgrep
        "https://127.0.0.1:9000/plaintext", data="my first message", verify=False
    )
    requests.post(  # nosemgrep
        "https://127.0.0.1:9001/plaintext", data="my second message", verify=False
    )
    time.sleep(0.5)  # nosemgrep
    output_content = output_path.read_text()
    assert "my first message" in output_content
    assert "my second message" in output_content


@pytest.mark.skipif(sys.version_info.minor < 7, reason="not supported for python 3.6")
def test_http_input_accepts_message_for_three_pipelines(tmp_path, config):
    config["process_count"] = 3
    output_path = tmp_path / "output.jsonl"
    config["output"] = {"testoutput": {"type": "jsonl_output", "output_file": str(output_path)}}
    config_path = str(tmp_path / "generated_config.yml")
    dump_config_as_file(config_path, config)
    proc = start_logprep(config_path)
    wait_for_output(proc, "Uvicorn running on https://127.0.0.1:9002")
    requests.post(  # nosemgrep
        "https://127.0.0.1:9000/plaintext", data="my first message", verify=False
    )
    requests.post(  # nosemgrep
        "https://127.0.0.1:9001/plaintext", data="my second message", verify=False
    )
    requests.post(  # nosemgrep
        "https://127.0.0.1:9002/plaintext", data="my third message", verify=False
    )
    time.sleep(0.5)  # nosemgrep
    output_content = output_path.read_text()
    assert "my first message" in output_content
    assert "my second message" in output_content
    assert "my third message" in output_content
