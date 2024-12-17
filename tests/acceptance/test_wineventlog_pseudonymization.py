# pylint: disable=missing-docstring
import tempfile
import time
from logging import DEBUG, basicConfig, getLogger
from pathlib import Path

import msgspec
import pytest

from logprep.util.configuration import Configuration
from logprep.util.json_handling import parse_jsonl
from tests.acceptance.util import (
    get_difference,
    start_logprep,
    stop_logprep,
    wait_for_output,
)

basicConfig(level=DEBUG, format="%(asctime)-15s %(name)-5s %(levelname)-8s: %(message)s")
logger = getLogger("Logprep-Test")


@pytest.fixture(name="config")
def get_config():
    config_dict = {
        "process_count": 1,
        "timeout": 0.1,
        "profile_pipelines": False,
        "logger": {"level": "DEBUG"},
        "pipeline": [
            {
                "pseudonymizer": {
                    "type": "pseudonymizer",
                    "pubkey_analyst": "tests/testdata/acceptance/pseudonymizer/example_analyst_pub.pem",
                    "pubkey_depseudo": "tests/testdata/acceptance/pseudonymizer/example_depseudo_pub.pem",
                    "hash_salt": "a_secret_tasty_ingredient",
                    "outputs": [{"jsonl": "pseudonyms"}],
                    "rules": ["tests/testdata/acceptance/pseudonymizer/rules"],
                    "regex_mapping": "tests/testdata/acceptance/pseudonymizer/regex_mapping.yml",
                    "max_cached_pseudonyms": 1000000,
                }
            }
        ],
        "input": {
            "jsonl_input": {
                "type": "jsonl_input",
                "documents_path": "tests/testdata/input_logdata/wineventlog_raw.jsonl",
            }
        },
        "output": {
            "jsonl": {
                "type": "jsonl_output",
                "output_file": tempfile.mktemp(suffix=".output.jsonl"),
                "output_file_custom": tempfile.mktemp(suffix=".custom.jsonl"),
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


def test_events_pseudonymized_correctly(tmp_path, config: Configuration):
    config_path = tmp_path / "generated_config.yml"
    config_path.write_text(config.as_yaml())
    proc = start_logprep(config_path)
    wait_for_output(proc, "Startup complete")
    time.sleep(2)
    expected_output_path = (
        "tests/testdata/acceptance/expected_result/pseudonymized_win_event_log.jsonl"
    )
    expected_output = parse_jsonl(expected_output_path)
    expected_logprep_outputs = [
        event for event in expected_output if "pseudonym" not in event.keys()
    ]
    output = Path(config.output["jsonl"]["output_file"]).read_bytes()
    extra_output = Path(config.output["jsonl"]["output_file_custom"]).read_bytes()
    error_output = Path(config.error_output["jsonl"]["output_file"]).read_bytes()
    decoder = msgspec.json.Decoder()
    output = decoder.decode_lines(output)
    extra_output = decoder.decode_lines(extra_output)
    error_output = decoder.decode_lines(error_output)
    assert output, "should not be empty"
    assert len(error_output) == 0, "There shouldn't be any logprep errors"
    assert extra_output, "extra outputs should not be empty"
    assert extra_output[5].get("pseudonyms", {}).get("pseudonym"), "should have pseudonym key"
    assert extra_output[5].get("pseudonyms", {}).get("origin"), "should have origin key"
    assert extra_output[5].get("pseudonyms", {}).get("@timestamp"), "should have @timestamp key"
    # Check the pseudonymized events
    result = get_difference(output, expected_logprep_outputs)
    assert (
        result["difference"][0] == result["difference"][1]
    ), f"Missmatch in event at line {result['event_line_no']}!"
