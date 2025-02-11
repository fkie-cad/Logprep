# pylint: disable=missing-docstring
import tempfile
from pathlib import Path
import time

import pytest
from ruamel.yaml import YAML

from logprep.util.configuration import Configuration
from tests.acceptance.util import start_logprep, stop_logprep, wait_for_output

yaml = YAML(typ="safe", pure=True)


@pytest.fixture(name="config")
def get_config():
    input_file = tempfile.mkstemp(suffix=".input.log")[1]

    config_dict = {
        "version": "1",
        "process_count": 1,
        "timeout": 0.1,
        "profile_pipelines": False,
        "config_refresh_interval": 5,
        "metrics": {"enabled": False},
        "pipeline": [],
        "input": {
            "file_input": {
                "type": "file_input",
                "logfile_path": input_file,
                "start": "begin",
                "interval": 1,
                "watch_file": True,
            }
        },
        "output": {
            "jsonl_output": {
                "type": "dummy_output",
            }
        },
    }

    return Configuration(**config_dict)


def teardown_function():
    Path("generated_config.yml").unlink(missing_ok=True)
    stop_logprep()


def test_two_times_config_refresh_after_5_seconds(tmp_path, config):
    config_path = tmp_path / "generated_config.yml"
    config_path.write_text(config.as_json())
    config = Configuration.from_sources([str(config_path)])
    proc = start_logprep(config_path)
    wait_for_output(proc, "Config refresh interval is set to: 5 seconds", test_timeout=5)
    config.version = "2"
    config_path.write_text(config.as_json())
    wait_for_output(proc, "Successfully reloaded configuration", test_timeout=12)
    config.version = "other version"
    config_path.write_text(config.as_json())
    wait_for_output(proc, "Successfully reloaded configuration", test_timeout=20)


def test_no_config_refresh_after_5_seconds(tmp_path, config):
    config.config_refresh_interval = 5
    config.metrics = {"enabled": False}
    config_path = tmp_path / "generated_config.yml"
    config_path.write_text(config.as_json())
    proc = start_logprep(config_path)
    wait_for_output(proc, "Config refresh interval is set to: 5 seconds", test_timeout=5)
    wait_for_output(
        proc,
        "Configuration version didn't change. Continue running with current version.",
        test_timeout=7,
    )


def test_recover_after_invalid_then_valid_config(tmp_path, config):
    config_path = tmp_path / "generated_config.yml"
    config.config_refresh_interval = 8
    config_path.write_text(config.as_json())
    proc = start_logprep(config_path)
    wait_for_output(proc, "Config refresh interval is set to: 8 seconds", test_timeout=5)

    input_backup = config.input

    config.input = {"fawlty": "config dic"}
    config.version = 5
    config_path.write_text(config.as_json())

    wait_for_output(
        proc,
        'The configuration for component "fawlty" must be specified as an object.',
        test_timeout=10,
    )

    if proc.poll() == None:
        pass
    else:
        assert False, "Process is not running."

    config.input = input_backup
    config.config_refresh_interval = 5
    config.version = "valid_again"
    config_path.write_text(config.as_json())
    wait_for_output(proc, "Successfully reloaded configuration", test_timeout=10)
    wait_for_output(proc, "Config refresh interval is set to: 5 seconds", test_timeout=10)
