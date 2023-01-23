# pylint: disable=missing-docstring
# pylint: disable=line-too-long
import time
from logging import DEBUG, basicConfig, getLogger

import pytest
import requests

from logprep.util.json_handling import dump_config_as_file
from tests.acceptance.util import (
    get_default_logprep_config,
    start_logprep,
    wait_for_output,
    stop_logprep,
)

basicConfig(level=DEBUG, format="%(asctime)-15s %(name)-5s %(levelname)-8s: %(message)s")
logger = getLogger("Logprep-Test")


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


def setup_function():
    stop_logprep()


def teardown_function():
    stop_logprep()


def test_http_input_accepts_message_for_single_pipeline(tmp_path, config):
    output_path = tmp_path / "output.jsonl"
    config["output"] = {"testoutput": {"type": "jsonl_output", "output_file": str(output_path)}}
    config_path = str(tmp_path / "generated_config.yml")
    dump_config_as_file(config_path, config)
    proc = start_logprep(config_path)
    wait_for_output(proc, "Uvicorn running on https://127.0.0.1:9000")
    # nosemgrep
    requests.post("https://127.0.0.1:9000/plaintext", data="my message", verify=False, timeout=5)
    time.sleep(0.5)  # nosemgrep
    assert "my message" in output_path.read_text()


def test_http_input_accepts_message_for_two_pipelines(tmp_path, config):
    config["process_count"] = 2
    output_path = tmp_path / "output.jsonl"
    config["output"] = {"testoutput": {"type": "jsonl_output", "output_file": str(output_path)}}
    config_path = str(tmp_path / "generated_config.yml")
    dump_config_as_file(config_path, config)
    proc = start_logprep(config_path)
    wait_for_output(proc, "Uvicorn running on https://127.0.0.1:9001")
    # nosemgrep
    requests.post(
        "https://127.0.0.1:9000/plaintext",
        data="my first message",
        verify=False,
        timeout=5,
    )
    # nosemgrep
    requests.post(
        "https://127.0.0.1:9001/plaintext",
        data="my second message",
        verify=False,
        timeout=5,
    )
    time.sleep(0.5)  # nosemgrep
    output_content = output_path.read_text()
    assert "my first message" in output_content
    assert "my second message" in output_content


def test_http_input_accepts_message_for_three_pipelines(tmp_path, config):
    config["process_count"] = 3
    output_path = tmp_path / "output.jsonl"
    config["output"] = {"testoutput": {"type": "jsonl_output", "output_file": str(output_path)}}
    config_path = str(tmp_path / "generated_config.yml")
    dump_config_as_file(config_path, config)
    proc = start_logprep(config_path)
    wait_for_output(proc, "Uvicorn running on https://127.0.0.1:9002", test_timeout=10)
    # nosemgrep
    requests.post(
        "https://127.0.0.1:9000/plaintext",
        data="my first message",
        verify=False,
        timeout=5,
    )
    # nosemgrep
    requests.post(
        "https://127.0.0.1:9001/plaintext",
        data="my second message",
        verify=False,
        timeout=5,
    )
    # nosemgrep
    requests.post(
        "https://127.0.0.1:9002/plaintext",
        data="my third message",
        verify=False,
        timeout=5,
    )
    time.sleep(0.5)  # nosemgrep
    output_content = output_path.read_text()
    assert "my first message" in output_content
    assert "my second message" in output_content
    assert "my third message" in output_content
