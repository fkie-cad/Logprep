# pylint: disable=missing-docstring
# pylint: disable=line-too-long
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
    return Configuration(
        **{
            "version": "1",
            "logger": {"level": "DEBUG"},
            "process_count": 1,
            "timeout": 0.1,
            "profile_pipelines": False,
            "pipeline": [
                {
                    "dissector": {
                        "type": "dissector",
                        "specific_rules": ["tests/testdata/acceptance/dissector/rules/specific"],
                        "generic_rules": ["tests/testdata/acceptance/dissector/rules/generic"],
                    }
                },
                {
                    "selective_extractor": {
                        "type": "selective_extractor",
                        "specific_rules": [
                            "tests/testdata/acceptance/selective_extractor/rules/specific"
                        ],
                        "generic_rules": [
                            "tests/testdata/acceptance/selective_extractor/rules/generic"
                        ],
                    }
                },
                {
                    "pseudonymizer": {
                        "type": "pseudonymizer",
                        "pubkey_analyst": "tests/testdata/acceptance/pseudonymizer/example_analyst_pub.pem",
                        "pubkey_depseudo": "tests/testdata/acceptance/pseudonymizer/example_depseudo_pub.pem",
                        "hash_salt": "a_secret_tasty_ingredient",
                        "outputs": [{"jsonl": "pseudonyms"}],
                        "specific_rules": [
                            "tests/testdata/acceptance/pseudonymizer/rules_static/specific"
                        ],
                        "generic_rules": [
                            "tests/testdata/acceptance/pseudonymizer/rules_static/generic"
                        ],
                        "regex_mapping": "tests/testdata/acceptance/pseudonymizer/rules_static/regex_mapping.yml",
                        "max_cached_pseudonyms": 1000000,
                    }
                },
                {
                    "pre_detector": {
                        "type": "pre_detector",
                        "outputs": [{"jsonl": "pre_detector_topic"}],
                        "generic_rules": ["tests/testdata/acceptance/pre_detector/rules/generic"],
                        "specific_rules": ["tests/testdata/acceptance/pre_detector/rules/specific"],
                        "tree_config": "tests/testdata/acceptance/pre_detector/tree_config.json",
                    }
                },
            ],
            "input": {
                "jsonl": {
                    "type": "jsonl_input",
                    "documents_path": "tests/testdata/input_logdata/kafka_raw_event_for_pre_detector.jsonl",
                }
            },
        }
    )


def setup_function():
    stop_logprep()


def teardown_function():
    stop_logprep()


def test_full_pipeline_run_with_two_outputs(tmp_path: Path, config: Configuration):
    output_path1 = tmp_path / "output1.jsonl"
    output_path_custom1 = tmp_path / "output_custom1.jsonl"
    output_path_error1 = tmp_path / "output_error1.jsonl"
    output_path2 = tmp_path / "output2.jsonl"
    output_path_custom2 = tmp_path / "output_custom2.jsonl"
    output_path_error2 = tmp_path / "output_error2.jsonl"
    config.input["jsonl"][
        "documents_path"
    ] = "tests/testdata/input_logdata/selective_extractor_events.jsonl"
    config.output = {
        "jsonl": {
            "type": "jsonl_output",
            "output_file": f"{str(output_path1)}",
            "output_file_custom": f"{str(output_path_custom1)}",
            "output_file_error": f"{str(output_path_error1)}",
        },
        "second_output": {
            "type": "jsonl_output",
            "output_file": f"{str(output_path2)}",
            "output_file_custom": f"{str(output_path_custom2)}",
            "output_file_error": f"{str(output_path_error2)}",
        },
    }
    config_path = tmp_path / "generated_config.yml"
    config_path.write_text(config.as_yaml())
    proc = start_logprep(str(config_path))
    wait_for_output(proc, "no documents left")
    stop_logprep(proc)
    assert output_path1.read_text(), "output is not empty"
    assert (
        output_path1.read_text() == output_path2.read_text()
    ), "stored output in both default outputs"
    assert output_path_custom1.read_text(), "stored custom output in output with name 'jsonl'"
    assert (
        not output_path_custom2.read_text()
    ), "stored custom output not in output with name 'second_output'"
    assert not output_path_error1.read_text(), "no errors in processing for 'jsonl' output"
    assert not output_path_error2.read_text(), "no errors in processing for 'second_output' output"
