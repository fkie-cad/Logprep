import json
from unittest import mock

import pytest
from rich.console import Console

from logprep.util.auto_rule_corpus_tester import RuleCorpusTester


@pytest.fixture(name="corpus_tester")
def fixture_auto_rule_corpus_tester():
    config_path = "tests/testdata/config/config.yml"
    data_dir = "will be overwritten in test cases"
    console = Console()
    corpus_tester = RuleCorpusTester(config_path, data_dir)
    corpus_tester.console = console
    return corpus_tester


def prepare_corpus_tester(corpus_tester, tmp_path, test_data):
    case_name = "rule_auto_corpus_test"
    input_data_path = tmp_path / f"{case_name}_in.json"
    input_data_path.write_text(json.dumps(test_data.get("input")))
    expected_output_data_path = tmp_path / f"{case_name}_out.json"
    expected_output_data_path.write_text(json.dumps(test_data.get("expected_output")))
    expected_extra_output_data_path = tmp_path / f"{case_name}_out_extra.json"
    expected_extra_output_data_path.write_text(json.dumps(test_data.get("expected_extra_output")))
    corpus_tester.input_test_data_path = tmp_path
    corpus_tester.tmp_dir = tmp_path


class TestAutoRuleTester:
    @pytest.mark.parametrize(
        "test_case, test_data, expected_prints, exit_code",
        [
            (
                "One successful test",
                {
                    "input": {
                        "winlog": {"event_id": "2222", "event_data": {"Test1": 1, "Test2": 2}}
                    },
                    "expected_output": {
                        "winlog": {"event_id": "2222", "event_data": {"Test1": 1, "Test2": 2}},
                        "test_normalized": {"test": {"field1": 1, "field2": 2}},
                    },
                    "expected_extra_output": [],
                },
                ["PASSED", "Success rate: 100.00%"],
                0,
            ),
            (
                "Unknown field in logprep output",
                {
                    "input": {
                        "winlog": {"event_id": "2222", "event_data": {"Test1": 1, "Test2": 2}}
                    },
                    "expected_output": {
                        "winlog": {"event_id": "2222", "event_data": {"Test1": 1}},
                        "test_normalized": {"test": {"field1": 1, "field2": 2}},
                    },
                    "expected_extra_output": [],
                },
                [
                    "FAILED",
                    "Success rate: 0.00%",
                    "Detailed Reports",
                    "unexpected values were generated",
                    "root['winlog']['event_data']['Test2']",
                ],
                1,
            ),
            (
                "Failed test with changed value only",
                {
                    "input": {
                        "winlog": {"event_id": "2222", "event_data": {"Test1": 1, "Test2": 2}}
                    },
                    "expected_output": {
                        "winlog": {"event_id": "2222", "event_data": {"Test1": 1, "Test2": 4}},
                        "test_normalized": {"test": {"field1": 1, "field2": 2}},
                    },
                    "expected_extra_output": [],
                },
                [
                    "FAILED",
                    "Success rate: 0.00%",
                    "Detailed Reports",
                    "values differ between generated and expected output",
                    "{\"root['winlog']['event_data']['Test2']\": {'generated': 2, 'expected': 4}}",
                ],
                1,
            ),
            (
                "One successful test with extra output",
                {
                    "input": {"winlog": {"event_data": {"IpAddress": "1.2.3.4"}}},
                    "expected_output": {"winlog": {"event_data": {"IpAddress": "<IGNORE_VALUE>"}}},
                    "expected_extra_output": [
                        {
                            "pseudonyms": {
                                "pseudonym": "<IGNORE_VALUE>",
                                "origin": "<IGNORE_VALUE>",
                            }
                        }
                    ],
                },
                ["PASSED", "Success rate: 100.00%"],
                0,
            ),
            (
                "Failed test with unexpected extra output",
                {
                    "input": {"winlog": {"event_data": {"IpAddress": "1.2.3.4"}}},
                    "expected_output": {"winlog": {"event_data": {"IpAddress": "<IGNORE_VALUE>"}}},
                    "expected_extra_output": [],
                },
                [
                    "FAILED",
                    "Success rate: 0.00%",
                    "Detailed Reports",
                    "There is at least one generated extra output that is unexpected",
                    "Logprep Event Output",
                    "Logprep Extra Data Output",
                    "pseudonyms",
                ],
                1,
            ),
            (
                "Failed test with expected extra output, not generated by logprep",
                {
                    "input": {"winlog": {"event_data": {"IpAddress": "1.2.3.4"}}},
                    "expected_output": {"winlog": {"event_data": {"IpAddress": "<IGNORE_VALUE>"}}},
                    "expected_extra_output": [
                        {
                            "pseudonyms": {
                                "pseudonym": "<IGNORE_VALUE>",
                                "origin": "<IGNORE_VALUE>",
                            }
                        },
                        {"some_random_extra": {"foo": "bar"}},
                    ],
                },
                [
                    "FAILED",
                    "Success rate: 0.00%",
                    "Detailed Reports",
                    "There is at least one expected extra output missing",
                    "For the following extra output, no matching extra output was generated by",
                    "Logprep Event Output",
                    "Logprep Extra Data Output",
                    "pseudonyms",
                ],
                1,
            ),
        ],
    )
    @mock.patch("logprep.util.auto_rule_corpus_tester.sys.exit")
    def test_run_prints_expected_outputs_to_console(
        self, mock_exit, tmp_path, corpus_tester, test_case, test_data, expected_prints, exit_code
    ):
        prepare_corpus_tester(corpus_tester, tmp_path, test_data)
        with corpus_tester.console.capture() as capture:
            corpus_tester.run()
        console_output = capture.get()
        for expected_print in expected_prints:
            assert expected_print in console_output
        mock_exit.assert_called_with(exit_code)

    @mock.patch("logprep.util.auto_rule_corpus_tester.sys.exit")
    def test_run_detects_unexpected_fields(self, mock_exit, tmp_path, corpus_tester):
        test_data = {
            "input": {"winlog": {"event_id": "2222", "event_data": {"Test1": 1, "Test2": 2}}},
            "expected_output": {
                "winlog": {"event_id": "2222", "event_data": {"Test1": 1, "Test2": 2}},
                "test_normalized": {"test": {"field1": 1, "field2": 2}},
            },
            "expected_extra_output": [],
        }
        expected_prints = [
            "FAILED",
            "Success rate: 0.00%",
            "Detailed Reports",
            "expected items are missing in the generated logprep output",
            "root['winlog']['event_data']['Test2']",
            "root['test_normalized']['test']['field2']",
        ]
        prepare_corpus_tester(corpus_tester, tmp_path, test_data)
        mocked_output = [
            [
                {
                    "winlog": {"event_id": "2222", "event_data": {"Test1": 1}},
                    "test_normalized": {"test": {"field1": 1}},
                }
            ],
            [],
            [],
        ]
        corpus_tester._retrieve_pipeline_output = mock.MagicMock(return_value=mocked_output)
        with corpus_tester.console.capture() as capture:
            corpus_tester.run()
        console_output = capture.get()
        for expected_print in expected_prints:
            assert expected_print in console_output
        mock_exit.assert_called_with(1)

    @mock.patch("logprep.util.auto_rule_corpus_tester.sys.exit")
    def test_run_ignores_value_if_set_in_expected_output(self, mock_exit, tmp_path, corpus_tester):
        test_data = {
            "input": {"winlog": {"event_id": "2222", "event_data": {"Test1": 1, "Test2": 2}}},
            "expected_output": {
                "winlog": {"event_id": "2222", "event_data": "<IGNORE_VALUE>"},
                "test_normalized": {"test": {"field1": 1, "field2": 2}},
            },
            "expected_extra_output": [],
        }
        expected_prints = [
            "PASSED",
            "Success rate: 100.00%",
        ]
        prepare_corpus_tester(corpus_tester, tmp_path, test_data)
        mocked_output = [
            [
                {
                    "winlog": {"event_id": "2222", "event_data": "SOME_RANDOM_CONTENT"},
                    "test_normalized": {"test": {"field1": 1, "field2": 2}},
                }
            ],
            [],
            [],
        ]
        corpus_tester._retrieve_pipeline_output = mock.MagicMock(return_value=mocked_output)
        with corpus_tester.console.capture() as capture:
            corpus_tester.run()
        console_output = capture.get()
        for expected_print in expected_prints:
            assert expected_print in console_output
        mock_exit.assert_called_with(0)

    @mock.patch("logprep.util.auto_rule_corpus_tester.sys.exit")
    def test_run_fails_if_key_of_ignored_value_is_missing(self, mock_exit, tmp_path, corpus_tester):
        test_data = {
            "input": {"winlog": {"event_id": "2222", "event_data": {"Test1": 1, "Test2": 2}}},
            "expected_output": {
                "winlog": {"event_id": "2222", "event_data": "<IGNORE_VALUE>"},
                "test_normalized": {"test": {"field1": 1, "field2": 2}},
            },
            "expected_extra_output": [],
        }
        expected_prints = [
            "FAILED",
            "expected items are missing in the generated logprep output",
            "root['winlog']['event_data']",
            "Success rate: 0.00%",
        ]
        prepare_corpus_tester(corpus_tester, tmp_path, test_data)
        mocked_output = [
            [
                {
                    "winlog": {"event_id": "2222"},
                    "test_normalized": {"test": {"field1": 1, "field2": 2}},
                }
            ],
            [],
            [],
        ]
        corpus_tester._retrieve_pipeline_output = mock.MagicMock(return_value=mocked_output)
        with corpus_tester.console.capture() as capture:
            corpus_tester.run()
        console_output = capture.get()
        for expected_print in expected_prints:
            assert expected_print in console_output
        mock_exit.assert_called_with(1)
