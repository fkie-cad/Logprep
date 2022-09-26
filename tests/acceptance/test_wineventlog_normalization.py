# pylint: disable=missing-docstring
# pylint: disable=line-too-long
#!/usr/bin/python3
from os import path

import pytest

from logprep.util.json_handling import dump_config_as_file, parse_jsonl
from tests.acceptance.util import (
    get_default_logprep_config,
    get_test_output,
    store_latest_test_output,
    get_difference,
)


@pytest.fixture(name="config")
def create_config():
    pipeline = [
        {
            "normalizername": {
                "type": "normalizer",
                "specific_rules": ["tests/testdata/acceptance/normalizer/rules_static/specific"],
                "generic_rules": ["tests/testdata/acceptance/normalizer/rules_static/generic"],
                "regex_mapping": "tests/testdata/acceptance/normalizer/rules_static/regex_mapping.yml",
            }
        }
    ]
    return get_default_logprep_config(pipeline, with_hmac=False)


def test_events_normalized_correctly(tmp_path, config):
    expected_output = "normalized_win_event_log.jsonl"
    expected_output_path = path.join("tests/testdata/acceptance/expected_result", expected_output)
    config["input"]["jsonl"][
        "documents_path"
    ] = "tests/testdata/input_logdata/wineventlog_raw.jsonl"
    config_path = str(tmp_path / "generated_config.yml")
    dump_config_as_file(config_path, config)

    test_output, _, _ = get_test_output(config_path)
    assert test_output, "should not be empty"
    store_latest_test_output(expected_output, test_output)

    expected_output = parse_jsonl(expected_output_path)

    result = get_difference(test_output, expected_output)

    assert (
        result["difference"][0] == result["difference"][1]
    ), f"Missmatch in event at line {result['event_line_no']}!"
