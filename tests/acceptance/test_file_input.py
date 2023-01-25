# pylint: disable=missing-docstring
# pylint: disable=line-too-long
import time
from logging import DEBUG, basicConfig, getLogger
import pytest
from logprep.util.json_handling import dump_config_as_file
from tests.acceptance.util import (
    get_default_logprep_config,
    start_logprep,
    wait_for_output,
    stop_logprep,
)
from tests.testdata.input_logdata.file_input_logs import (
    test_initial_log_data,
)

CHECK_INTERVAL = 0.1


def wait_for_interval(interval):
    time.sleep(2 * interval)


def write_file(file_name: str, source_data: list):
    with open(file_name, "w", encoding="utf-8") as file:
        for line in source_data:
            file.write(line + "\n")


def write_empty_file(file_name: str):
    open(file_name, "w", encoding="utf-8").close()


def append_file(file_name: str, source_data: list):
    with open(file_name, "a", encoding="utf-8") as file:
        for line in source_data:
            file.write(line + "\n")


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
            "type": "file_input",
            "logfile_path": "",
            "start": "begin",
            "interval": CHECK_INTERVAL,
            "watch_file": True,
        }
    }

    return config


def setup_function():
    stop_logprep()


def teardown_function():
    stop_logprep()


def test_file_input_accepts_message_for_single_pipeline(tmp_path, config):
    output_path = tmp_path / "output.jsonl"
    input_path = tmp_path / "input.log"
    config["input"]["testinput"]["logfile_path"] = str(input_path)
    config["output"] = {"testoutput": {"type": "jsonl_output", "output_file": str(output_path)}}
    config_path = str(tmp_path / "generated_config.yml")
    dump_config_as_file(config_path, config)
    write_file(str(input_path), test_initial_log_data)
    proc = start_logprep(config_path)
    wait_for_output(proc, "Logprep INFO    : Log level set to 'INFO'")
    wait_for_interval(4 * CHECK_INTERVAL)
    assert test_initial_log_data[0] in output_path.read_text()


def test_file_input_accepts_message_for_two_pipelines(tmp_path, config):
    config["process_count"] = 2
    output_path = tmp_path / "output.jsonl"
    input_path = tmp_path / "input.log"
    config["input"]["testinput"]["logfile_path"] = str(input_path)
    config["output"] = {"testoutput": {"type": "jsonl_output", "output_file": str(output_path)}}
    config_path = str(tmp_path / "generated_config.yml")
    dump_config_as_file(config_path, config)
    write_file(str(input_path), test_initial_log_data)
    proc = start_logprep(config_path)
    wait_for_output(proc, "Logprep INFO    : Log level set to 'INFO'")
    wait_for_interval(4 * CHECK_INTERVAL)
    assert test_initial_log_data[0] in output_path.read_text()
