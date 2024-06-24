# pylint: disable=missing-docstring
from logging import DEBUG, basicConfig, getLogger
from os import path

import pytest

from logprep.util.configuration import Configuration
from logprep.util.json_handling import parse_jsonl
from tests.acceptance.util import (
    get_default_logprep_config,
    get_difference,
    get_test_output,
)

basicConfig(level=DEBUG, format="%(asctime)-15s %(name)-5s %(levelname)-8s: %(message)s")
logger = getLogger("Logprep-Test")


@pytest.fixture(name="config")
def get_config():
    pipeline = [
        {
            "pseudonymizer": {
                "type": "pseudonymizer",
                "pubkey_analyst": "tests/testdata/acceptance/pseudonymizer/example_analyst_pub.pem",
                "pubkey_depseudo": "tests/testdata/acceptance/pseudonymizer/example_depseudo_pub.pem",
                "hash_salt": "a_secret_tasty_ingredient",
                "outputs": [{"jsonl": "pseudonyms"}],
                "specific_rules": ["tests/testdata/acceptance/pseudonymizer/rules_static/specific"],
                "generic_rules": ["tests/testdata/acceptance/pseudonymizer/rules_static/generic"],
                "regex_mapping": "tests/testdata/acceptance/pseudonymizer/rules_static/regex_mapping.yml",
                "max_cached_pseudonyms": 1000000,
            }
        }
    ]
    return get_default_logprep_config(pipeline, with_hmac=False)


def test_events_pseudonymized_correctly(tmp_path, config: Configuration):
    expected_output_file_name = "pseudonymized_win_event_log.jsonl"
    expected_output_path = path.join(
        "tests/testdata/acceptance/expected_result", expected_output_file_name
    )
    expected_output = parse_jsonl(expected_output_path)
    expected_logprep_outputs = [
        event for event in expected_output if "pseudonym" not in event.keys()
    ]
    expected_logprep_extra_outputs = [
        event for event in expected_output if "pseudonym" in event.keys()
    ]

    config.input["jsonl"]["documents_path"] = "tests/testdata/input_logdata/wineventlog_raw.jsonl"
    config_path = tmp_path / "generated_config.yml"
    config_path.write_text(config.as_yaml())

    logprep_output, logprep_extra_output, logprep_error_output = get_test_output(str(config_path))
    assert logprep_output, "should not be empty"
    assert len(logprep_error_output) == 0, "There shouldn't be any logprep errors"
    result = get_difference(logprep_output, expected_logprep_outputs)
    assert (
        result["difference"][0] == result["difference"][1]
    ), f"Missmatch in event at line {result['event_line_no']}!"

    # FIXME: Test is only testing for the logprep outputs with the pseudonym inside, but not the
    #   extra outputs.
