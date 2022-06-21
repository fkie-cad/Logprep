#!/usr/bin/python3
from logging import getLogger, DEBUG, basicConfig
from os import path

import pytest

from logprep.util.json_handling import dump_config_as_file
from logprep.util.json_handling import parse_jsonl
from tests.acceptance.util import get_test_output, store_latest_test_output, get_difference

basicConfig(level=DEBUG, format="%(asctime)-15s %(name)-5s %(levelname)-8s: %(message)s")
logger = getLogger("Logprep-Test")


@pytest.fixture
def config():
    config_yml = {
        "process_count": 1,
        "timeout": 0.1,
        "profile_pipelines": True,
        "pipeline": [
            {
                "pseudonymizer": {
                    "type": "pseudonymizer",
                    "pubkey_analyst": "tests/testdata/acceptance/pseudonymizer/example_analyst_pub.pem",
                    "pubkey_depseudo": "tests/testdata/acceptance/pseudonymizer/example_depseudo_pub.pem",
                    "hash_salt": "a_secret_tasty_ingredient",
                    "pseudonyms_topic": "pseudonyms",
                    "specific_rules": [
                        "tests/testdata/acceptance/pseudonymizer/rules_static/specific"
                    ],
                    "generic_rules": [
                        "tests/testdata/acceptance/pseudonymizer/rules_static/generic"
                    ],
                    "regex_mapping": "tests/testdata/acceptance/pseudonymizer/rules_static/regex_mapping.yml",
                    "max_cached_pseudonyms": 1000000,
                    "max_caching_days": 1,
                }
            }
        ],
        "connector": {
            "type": "writer",
            "output_path": "-",
            "output_path_custom": "tests/testdata/acceptance/test_kafka_data_processing_acceptance.out",
            "input_path": "tests/testdata/input_logdata/kafka_raw_event.jsonl",
        },
    }
    return config_yml


def test_events_pseudonymized_correctly(tmp_path, config):
    expected_output = "pseudonymized_win_event_log.jsonl"
    expected_output_path = path.join("tests/testdata/acceptance/expected_result", expected_output)

    config_path = str(tmp_path / "generated_config.yml")
    dump_config_as_file(config_path, config)

    test_output = get_test_output(config_path)
    store_latest_test_output(expected_output, test_output)

    expected_output = parse_jsonl(expected_output_path)

    test_output = [event for event in test_output if "pseudonym" not in event.keys()]
    expected_output = [event for event in expected_output if "pseudonym" not in event.keys()]

    result = get_difference(test_output, expected_output)

    assert (
        result["difference"][0] == result["difference"][1]
    ), "Missmatch in event at line {}!".format(result["event_line_no"])
