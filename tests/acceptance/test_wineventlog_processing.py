# pylint: disable=missing-docstring
import logging
import os

import pytest

from logprep.util.configuration import Configuration
from logprep.util.json_handling import parse_jsonl
from tests.acceptance.util import (
    get_default_logprep_config,
    get_difference,
    get_test_output,
    store_latest_test_output,
)

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)-15s %(name)-5s %(levelname)-8s: %(message)s"
)
logger = logging.getLogger("Logprep-Test")


@pytest.fixture(name="config")
def fixture_config_template():
    pipeline = [
        {
            "labelername": {
                "type": "labeler",
                "schema": "",
                "include_parent_labels": True,
                "rules": None,
            }
        }
    ]
    return get_default_logprep_config(pipeline, with_hmac=False)


@pytest.mark.parametrize(
    "rules, schema, expected_output",
    [
        (
            ["acceptance/labeler/no_regex/rules"],
            "acceptance/labeler/no_regex/labeling/schema.json",
            "labeled_win_event_log.jsonl",
        ),
        (
            [
                "acceptance/labeler/no_regex/rules",
                "acceptance/labeler/only_regex/rules",
            ],
            "acceptance/labeler/only_regex/labeling/schema.json",
            "labeled_win_event_log_with_regex.jsonl",
        ),
    ],
)
def test_events_labeled_correctly(
    tmp_path, config: Configuration, rules, schema, expected_output
):  # pylint: disable=too-many-arguments
    expected_output_path = os.path.join(
        "tests/testdata/acceptance/expected_result", expected_output
    )
    set_config(config, rules, schema)
    config.input["jsonl"]["documents_path"] = "tests/testdata/input_logdata/wineventlog_raw.jsonl"
    config_path = tmp_path / "generated_config.yml"
    config_path.write_text(config.as_yaml())

    test_output, _, _ = get_test_output(str(config_path))
    assert test_output, "should not be empty"
    store_latest_test_output(expected_output, test_output)
    expected_output = parse_jsonl(expected_output_path)
    result = get_difference(test_output, expected_output)
    assert (
        result["difference"][0] == result["difference"][1]
    ), f"Missmatch in event at line {result['event_line_no']}!"


def set_config(config: Configuration, rules, schema):
    config.pipeline[0]["labelername"]["schema"] = os.path.join("tests/testdata", schema)
    config.pipeline[0]["labelername"]["rules"] = [
        os.path.join("tests/testdata", rule) for rule in rules
    ]
