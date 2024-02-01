# pylint: disable=missing-docstring
from pathlib import Path

from ruamel.yaml import YAML

from logprep.util.configuration import Configuration
from tests.acceptance.util import start_logprep, stop_logprep, wait_for_output

yaml = YAML(typ="safe", pure=True)


def teardown_function():
    Path("generated_config.yml").unlink(missing_ok=True)
    stop_logprep()


def test_two_times_config_refresh_after_5_seconds(tmp_path):
    config = Configuration.from_sources(["tests/testdata/config/config.yml"])
    config.config_refresh_interval = 5
    config.metrics = {"enabled": False}
    config_path = tmp_path / "generated_config.yml"
    config_path.write_text(config.as_json())
    proc = start_logprep(config_path)
    wait_for_output(proc, "Config refresh interval is set to: 5 seconds", test_timeout=5)
    config.version = "2"
    config_path.write_text(config.as_json())
    wait_for_output(proc, "Successfully reloaded configuration", test_timeout=7)
    config.version = "other version"
    config_path.write_text(config.as_json())
    wait_for_output(proc, "Successfully reloaded configuration", test_timeout=6)


def test_no_config_refresh_after_5_seconds(tmp_path):
    config = Configuration.from_sources(["tests/testdata/config/config.yml"])
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
