# pylint: disable=missing-docstring
# pylint: disable=line-too-long
import time
from logging import DEBUG, basicConfig, getLogger
from pathlib import Path

import pytest
import requests

from logprep.util.configuration import Configuration
from tests.acceptance.util import (
    get_default_logprep_config,
    start_logprep,
    stop_logprep,
    wait_for_output,
)

basicConfig(level=DEBUG, format="%(asctime)-15s %(name)-5s %(levelname)-8s: %(message)s")
logger = getLogger("Logprep-Test")


@pytest.fixture(name="config")
def config_fixture():
    pipeline = [
        {
            "dissector": {
                "type": "dissector",
                "rules": ["tests/testdata/acceptance/dissector/rules"],
            }
        }
    ]
    config = get_default_logprep_config(pipeline, with_hmac=False)
    config.input = {
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


@pytest.mark.filterwarnings("ignore:Unverified HTTPS request is being made to host '127.0.0.1'")
def test_http_input_accepts_message_for_single_pipeline(tmp_path: Path, config: Configuration):
    output_path = tmp_path / "output.jsonl"
    config.output = {"testoutput": {"type": "jsonl_output", "output_file": str(output_path)}}
    config_path = tmp_path / "generated_config.yml"
    config_path.write_text(config.as_yaml())
    proc = start_logprep(config_path)
    wait_for_output(proc, "Uvicorn running on https://127.0.0.1:9000", test_timeout=15)

    requests.post("https://127.0.0.1:9000/plaintext", data="my message", verify=False, timeout=5)
    time.sleep(0.5)
    assert "my message" in output_path.read_text()
    stop_logprep(proc)


@pytest.mark.filterwarnings("ignore:Unverified HTTPS request is being made to host '127.0.0.1'")
def test_http_input_accepts_message_for_multiple_pipelines(tmp_path: Path, config: Configuration):
    config.process_count = 4
    output_path = tmp_path / "output.jsonl"
    config.output = {"testoutput": {"type": "jsonl_output", "output_file": str(output_path)}}
    config_path = tmp_path / "generated_config.yml"
    config_path.write_text(config.as_yaml())
    proc = start_logprep(config_path)
    wait_for_output(proc, "Uvicorn running on https://127.0.0.1:9000", test_timeout=15)

    requests.post("https://127.0.0.1:9000/plaintext", data="my message", verify=False, timeout=5)
    time.sleep(0.5)
    assert "my message" in output_path.read_text()
    stop_logprep(proc)
