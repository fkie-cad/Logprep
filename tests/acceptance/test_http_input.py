# pylint: disable=missing-docstring
# pylint: disable=line-too-long
import os
import re
import signal
import subprocess
import sys
import time
import requests
from logging import DEBUG, basicConfig, getLogger
import pytest
from tests.acceptance.util import get_default_logprep_config
from logprep.util.json_handling import dump_config_as_file

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
    return get_default_logprep_config(pipeline, with_hmac=False)


def teardown_function():
    # cleanup processes
    output = subprocess.check_output("ps -x | grep run_logprep", shell=True)
    for line in output.decode("utf8").splitlines():
        process_id = re.match(r"^\s+(\d+)\s.+", line).group(1)
        try:
            os.kill(int(process_id), signal.SIGKILL)
        except ProcessLookupError:
            pass


def test_http_input_accepts_message_for_single_pipeline(tmp_path, config):
    output_path = tmp_path / "output.jsonl"
    config["input"] = {"testinput": {"type": "http_input", "host": "127.0.0.1", "port": 9000}}
    config["output"] = {"testoutput": {"type": "jsonl_output", "output_file": str(output_path)}}
    config_path = str(tmp_path / "generated_config.yml")
    dump_config_as_file(config_path, config)
    environment = {"PYTHONPATH": "."}
    process = subprocess.Popen(
        f"{sys.executable} logprep/run_logprep.py {config_path}",
        shell=True,
        env=environment,
    )
    time.sleep(2)  # nosemgrep
    requests.post("http://127.0.0.1:9000/plaintext", data="my message")
    process.send_signal(signal.SIGINT)
    process.kill()
    assert "my message" in output_path.read_text()


def test_http_input_accepts_message_for_multiple_pipelines(tmp_path, config):
    config["process_count"] = 2
    output_path = tmp_path / "output.jsonl"
    config["input"] = {"testinput": {"type": "http_input", "host": "127.0.0.1", "port": 9000}}
    config["output"] = {"testoutput": {"type": "jsonl_output", "output_file": str(output_path)}}
    config_path = str(tmp_path / "generated_config.yml")
    dump_config_as_file(config_path, config)
    environment = {"PYTHONPATH": "."}
    process = subprocess.Popen(
        f"{sys.executable} logprep/run_logprep.py {config_path}",
        shell=True,
        env=environment,
    )
    time.sleep(2)  # nosemgrep
    requests.post("http://127.0.0.1:9000/plaintext", data="my first message")
    requests.post("http://127.0.0.1:9001/plaintext", data="my second message")
    process.send_signal(signal.SIGINT)
    process.kill()
    output_content = output_path.read_text()
    assert "my first message" in output_content
    assert "my second message" in output_content
