# pylint: disable=missing-docstring
# pylint: disable=line-too-long
#!/usr/bin/python3

import pytest


@pytest.mark.parametrize(
    "testcase, pipeline, testdata",
    [
        (
            "pipeline with single normalizer",
            [
                {
                    "normalizername": {
                        "type": "normalizer",
                        "specific_rules": [
                            "tests/testdata/acceptance/normalizer/rules_static/specific"
                        ],
                        "generic_rules": [
                            "tests/testdata/acceptance/normalizer/rules_static/generic"
                        ],
                        "regex_mapping": "tests/testdata/acceptance/normalizer/rules_static/regex_mapping.yml",
                    }
                }
            ],
            {
                "input_data": "tests/testdata/input_logdata/wineventlog_raw.jsonl",
                "expected_output": "tests/testdata/acceptance/expected_result/normalized_win_event_log.jsonl",
            },
        ),
        (
            "pipeline with normalizer and selective_extractor",
            [
                {
                    "normalizername": {
                        "type": "normalizer",
                        "specific_rules": [
                            "tests/testdata/acceptance/normalizer/rules_static/specific"
                        ],
                        "generic_rules": [
                            "tests/testdata/acceptance/normalizer/rules_static/generic"
                        ],
                        "regex_mapping": "tests/testdata/acceptance/normalizer/rules_static/regex_mapping.yml",
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
            ],
            {
                "input_data": "tests/testdata/input_logdata/selective_extractor_events.jsonl",
                "expected_output": "tests/testdata/acceptance/expected_result/expected_pipeline_with_normalizer_and_selective_extractor_output.jsonl",
                "expected_custom": "tests/testdata/acceptance/expected_result/expected_pipeline_with_normalizer_and_selective_extractor_custom.jsonl",
            },
        ),
        (
            "pipeline with normalizer and selective_extractor field not in event",
            [
                {
                    "normalizername": {
                        "type": "normalizer",
                        "specific_rules": [
                            "tests/testdata/acceptance/normalizer/rules_static/specific"
                        ],
                        "generic_rules": [
                            "tests/testdata/acceptance/normalizer/rules_static/generic"
                        ],
                        "regex_mapping": "tests/testdata/acceptance/normalizer/rules_static/regex_mapping.yml",
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
            ],
            {
                "input_data": "tests/testdata/input_logdata/selective_extractor_events_2.jsonl",
                "expected_output": "tests/testdata/acceptance/expected_result/expected_pipeline_with_normalizer_and_selective_extractor_field_not_in_event_output.jsonl",
                "expected_custom": "tests/testdata/acceptance/expected_result/expected_pipeline_with_normalizer_and_selective_extractor_field_not_in_event_custom.jsonl",
            },
        ),
        (
            "test events pseudonymized correctly",
            [
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
            {
                "input_data": "tests/testdata/input_logdata/wineventlog_raw.jsonl",
                "expected_output": "tests/testdata/acceptance/expected_result/expected_test_events_pseudonymized_correctly_output.jsonl",
            },
        ),
    ],
)
def test_acceptance_pipeline(get_test_result, testcase, pipeline, testdata):
    results = get_test_result(testcase, pipeline, testdata)
    for result in results:
        assert (
            result["difference"][0] == result["difference"][1]
        ), f"Missmatch in event at line {result['event_line_no']}, expected output: {result['expected_path']}"
