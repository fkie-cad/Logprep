# pylint: disable=missing-docstring
import tempfile
from os import kill

import psutil
import pytest
from ruamel.yaml import YAML

from logprep.util.configuration import Configuration
from tests.acceptance.util import (
    run_logprep,
    wait_for_output,
    wait_for_output_with_search,
)

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
        "logger": {"level": "DEBUG"},
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


def test_two_times_config_refresh_after_5_seconds(tmp_path, config):
    config_path = tmp_path / "generated_config.yml"
    config_path.write_text(config.as_json())
    config = Configuration.from_sources([str(config_path)])
    with run_logprep(config_path) as proc:
        wait_for_output(proc, "Config refresh interval is set to: 5 seconds", test_timeout=5)
        config.version = "2"
        config_path.write_text(config.as_json())
        wait_for_output(proc, "Successfully reloaded configuration", test_timeout=12)
        config.version = "other version"
        config_path.write_text(config.as_json())
        wait_for_output(proc, "Successfully reloaded configuration", test_timeout=20)


def test_config_refresh_after_5_seconds_without_change(tmp_path, config):
    config.config_refresh_interval = 5
    config.metrics = {"enabled": False}
    config_path = tmp_path / "generated_config.yml"
    config_path.write_text(config.as_json())
    with run_logprep(config_path) as proc:
        wait_for_output(proc, "Config refresh interval is set to: 5 seconds", test_timeout=5)
        wait_for_output(
            proc,
            "Successfully reloaded configuration",
            test_timeout=10,
        )


def test_config_refresh_after_crash_config_not_changed(tmp_path, config):
    config.config_refresh_interval = 5
    config.metrics = {"enabled": False}

    config_path = tmp_path / "generated_config.yml"
    config_path.write_text(config.as_json())
    with run_logprep(config_path) as proc:
        wait_for_output(proc, "Config refresh interval is set to: 5 seconds", test_timeout=5)

        m = wait_for_output_with_search(
            proc, r"^.{10}\s.{8}\s(?P<pid>\d*?)\s*Pipeline1\s.*$", test_timeout=10
        )

        wait_for_output(proc, "Finished building pipeline")

        config.input = {
            "dummy_input": {"type": "dummy_input", "documents": [{"something": "yeah"}]}
        }
        config.pipeline = [
            {
                "calc": {
                    "type": "calculator",
                    "rules": [
                        {
                            "filter": "test_label: execute",
                            "calculator": {"target_field": "calculation", "calc": "1 / 0"},
                        }
                    ],
                }
            }
        ]
        config_path.write_text(config.as_json())
        wait_for_output(
            proc,
            "Successfully reloaded configuration",
            test_timeout=10,
        )

        pipeline_pid = int(m.group("pid"))
        pipeline1 = psutil.Process(pipeline_pid)
        pipeline1.kill()

        print("Waiting for restarting failed pipeline")
        wait_for_output(proc, "Restarting failed pipeline", test_timeout=5)

        timed_out = False
        try:
            wait_for_output(
                proc,
                expected_output="Created 'calculator' processor",
                test_timeout=10,
            )
        except:
            timed_out = True
        finally:
            assert timed_out
