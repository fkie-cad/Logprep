# pylint: disable=missing-docstring
# pylint: disable=line-too-long
import tempfile
import time
from pathlib import Path

import pytest

from logprep.util.configuration import Configuration
from tests.acceptance.util import start_logprep, stop_logprep, wait_for_output

CHECK_INTERVAL = 0.1


def wait_for_interval(interval):
    time.sleep(2 * interval)


@pytest.fixture(name="config")
def get_config():
    config = {
        "version": "1",
        "logger": {"level": "DEBUG"},
        "process_count": 1,
        "timeout": 0.1,
        "profile_pipelines": False,
        "restart_count": -1,
        "pipeline": [
            {
                "dissector": {
                    "type": "dissector",
                    "rules": ["tests/testdata/acceptance/dissector/rules"],
                }
            },
            {
                "selective_extractor": {
                    "type": "selective_extractor",
                    "rules": ["tests/testdata/acceptance/selective_extractor/rules"],
                }
            },
            {
                "pseudonymizer": {
                    "type": "pseudonymizer",
                    "pubkey_analyst": "tests/testdata/acceptance/pseudonymizer/example_analyst_pub.pem",
                    "pubkey_depseudo": "tests/testdata/acceptance/pseudonymizer/example_depseudo_pub.pem",
                    "hash_salt": "a_secret_tasty_ingredient",
                    "outputs": [{"second_output": "pseudonyms"}],
                    "rules": ["tests/testdata/acceptance/pseudonymizer/rules"],
                    "regex_mapping": "tests/testdata/acceptance/pseudonymizer/regex_mapping.yml",
                    "max_cached_pseudonyms": 1000000,
                }
            },
            {
                "pre_detector": {
                    "type": "pre_detector",
                    "outputs": [{"jsonl": "pre_detector_topic"}],
                    "rules": ["tests/testdata/acceptance/pre_detector/rules"],
                    "tree_config": "tests/testdata/acceptance/pre_detector/tree_config.json",
                }
            },
        ],
        "input": {
            "jsonl": {
                "type": "jsonl_input",
                "documents_path": "tests/testdata/input_logdata/selective_extractor_events.jsonl",
            }
        },
        "output": {
            "jsonl": {
                "type": "jsonl_output",
                "output_file": tempfile.mkstemp(suffix="output1.jsonl")[1],
                "output_file_custom": tempfile.mkstemp(suffix="custom1.jsonl")[1],
            },
            "second_output": {
                "type": "jsonl_output",
                "output_file": tempfile.mkstemp(suffix="output2.jsonl")[1],
                "output_file_custom": tempfile.mkstemp(suffix="custom2.jsonl")[1],
            },
        },
        "error_output": {
            "jsonl": {
                "type": "jsonl_output",
                "output_file": tempfile.mkstemp(suffix="error.jsonl")[1],
            }
        },
    }
    return Configuration(**config)


def setup_function():
    stop_logprep()


def teardown_function():
    stop_logprep()


def test_full_pipeline_run_with_two_outputs(tmp_path: Path, config: Configuration):
    output_path1 = Path(config.output["jsonl"]["output_file"])
    output_path_custom1 = Path(config.output["jsonl"]["output_file_custom"])
    output_path_error = Path(config.error_output["jsonl"]["output_file"])
    output_path2 = Path(config.output["second_output"]["output_file"])
    output_path_custom2 = Path(config.output["second_output"]["output_file_custom"])
    config_path = tmp_path / "generated_config.yml"
    config_path.write_text(config.as_yaml())
    proc = start_logprep(str(config_path))
    wait_for_output(proc, "no documents left")
    stop_logprep(proc)
    assert output_path1.read_text("utf8"), "output is not empty"
    assert output_path1.read_text("utf8") == output_path2.read_text(
        "utf8"
    ), "stored output in both default outputs"
    assert output_path_custom1.read_text("utf8"), "stored custom output in output with name 'jsonl'"
    assert not output_path_custom2.read_text(
        "utf8"
    ), "stored custom output not in output with name 'second_output'"
    assert not output_path_error.read_text("utf8"), "no errors in processing"
