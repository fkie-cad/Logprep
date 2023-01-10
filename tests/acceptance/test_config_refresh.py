# pylint: disable=missing-docstring
import json
from pathlib import Path
from ruamel.yaml import YAML
from tests.acceptance.util import (
    start_logprep,
    stop_logprep,
    wait_for_output,
)
from logprep.util.configuration import Configuration

yaml = YAML(typ="safe", pure=True)


def teardown_function():
    Path("generated_config.yml").unlink(missing_ok=True)
    stop_logprep()


def test_two_times_config_refresh_after_5_seconds(tmp_path):
    config = Configuration.create_from_yaml("quickstart/exampledata/config/pipeline.yml")
    config.update({"config_refresh_interval": 5})
    config_path = tmp_path / "generated_config.yml"
    config_path.write_text(json.dumps(config))
    proc = start_logprep(config_path)
    wait_for_output(proc, "Config refresh interval is set to: 5 seconds", test_timeout=5)
    config.update({"version": 2})
    config_path.write_text(json.dumps(config))
    wait_for_output(proc, "Successfully reloaded configuration", test_timeout=7)
    config.update({"version": "other version"})
    config_path.write_text(json.dumps(config))
    wait_for_output(proc, "Successfully reloaded configuration", test_timeout=6)


def test_no_config_refresh_after_5_seconds(tmp_path):
    config = Configuration.create_from_yaml("quickstart/exampledata/config/pipeline.yml")
    config.update({"config_refresh_interval": 5})
    config_path = tmp_path / "generated_config.yml"
    config_path.write_text(json.dumps(config))
    proc = start_logprep(config_path)
    wait_for_output(proc, "Config refresh interval is set to: 5 seconds", test_timeout=5)
    wait_for_output(
        proc,
        "Configuration version didn't change. Continue running with current version.",
        test_timeout=5,
    )
