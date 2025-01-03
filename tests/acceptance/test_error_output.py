#!/usr/bin/env python3
# pylint: disable=not-an-iterable
# pylint: disable=missing-docstring

import json
import tempfile
import time
import uuid
from logging import DEBUG, basicConfig, getLogger
from pathlib import Path

import pytest

from logprep.util.configuration import Configuration
from tests.acceptance.util import start_logprep, stop_logprep, wait_for_output

basicConfig(level=DEBUG, format="%(asctime)-15s %(name)-5s %(levelname)-8s: %(message)s")
logger = getLogger("Logprep-Test")


@pytest.fixture(name="config")
def get_config():
    config_dict = {
        "process_count": 1,
        "timeout": 0.1,
        "profile_pipelines": False,
        "pipeline": [],
        "input": {
            "jsonl_input": {
                "type": "jsonl_input",
                "documents_path": tempfile.mktemp(suffix=".input.jsonl"),
                "preprocessing": {
                    "hmac": {
                        "target": "doesnotexist.never.ever",
                        "key": "thisisasecureandrandomkey",
                        "output_field": "Full_event",
                    },
                },
            }
        },
        "output": {
            "jsonl_output": {
                "type": "dummy_output",
            }
        },
        "error_output": {
            "jsonl": {
                "type": "jsonl_output",
                "output_file": tempfile.mktemp(suffix=".error.jsonl"),
            }
        },
    }

    return Configuration(**config_dict)


def teardown_function():
    Path("generated_config.yml").unlink(missing_ok=True)
    stop_logprep()


def test_error_output_for_critical_input_error_with_missing_hmac_target_field(
    tmp_path, config: Configuration
):
    input_path = Path(config.input["jsonl_input"]["documents_path"])
    error_output_path = Path(config.error_output["jsonl"]["output_file"])
    content = str(uuid.uuid4())
    event = {"something": content}
    input_path.write_text(json.dumps(event), encoding="utf8")
    config.output.update({"kafka": {"type": "dummy_output", "default": False}})
    config_path = tmp_path / "generated_config.yml"
    config_path.write_text(config.as_yaml(), encoding="utf-8")
    proc = start_logprep(config_path)
    output = proc.stdout.readline().decode("utf8")
    # exclude error from forbidden_outputs as the config file path has the word error in it
    wait_for_output(
        proc, "Couldn't find the hmac target field", forbidden_outputs=["Invalid", "Exception"]
    )
    start = time.time()
    while not error_output_path.read_text(encoding="utf8"):
        output = proc.stdout.readline().decode("utf8")
        assert "not JSON serializable" not in output
        if time.time() - start > 10:
            assert False, "Timeout reached"
    error_content = error_output_path.read_text(encoding="utf8")
    assert content in error_content


def test_error_output_errors_are_logged_if_error_output_has_an_error(
    tmp_path, config: Configuration
):
    config.input = {
        "dummy": {"type": "dummy_input", "documents": [{"something": "yeah"}, "Exception"]}
    }
    config.error_output = {"dummy": {"type": "dummy_output", "exceptions": ["Exception"]}}
    config.error_backlog_size = 1
    config.output.update({"kafka": {"type": "dummy_output", "default": False}})
    config_path = tmp_path / "generated_config.yml"
    config_path.write_text(config.as_yaml(), encoding="utf-8")
    proc = start_logprep(config_path)
    wait_for_output(
        proc,
        r".*\[Error Event\] Couldn't enqueue error item due to:.*",
        test_timeout=30,
        forbidden_outputs=[],
    )
