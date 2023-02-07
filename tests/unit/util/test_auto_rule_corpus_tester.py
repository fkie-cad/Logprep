# pylint: disable=missing-docstring
# pylint: disable=protected-access
import json
import os
from json import JSONDecodeError
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
    corpus_tester._input_test_data_path = tmp_path
    corpus_tester._tmp_dir = tmp_path


class TestAutoRuleTester:
    @pytest.mark.parametrize(
        "test_case, test_data, mock_output, expected_prints, exit_code",
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
                None,
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
                None,
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
                None,
                [
                    "FAILED",
                    "Success rate: 0.00%",
                    "Detailed Reports",
                    "values differ between generated and expected output",
                    "- root['winlog']['event_data']['Test2']: {'generated': 2, 'expected': 4}",
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
                None,
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
                None,
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
                None,
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
            (
                "Failed test with unexpected field generated by logprep",
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
                [
                    [
                        {
                            "winlog": {"event_id": "2222", "event_data": {"Test1": 1}},
                            "test_normalized": {"test": {"field1": 1}},
                        }
                    ],
                    [],
                    [],
                ],
                [
                    "FAILED",
                    "Success rate: 0.00%",
                    "Detailed Reports",
                    "expected items are missing in the generated logprep output",
                    "root['winlog']['event_data']['Test2']",
                    "root['test_normalized']['test']['field2']",
                ],
                1,
            ),
            (
                "Successful test with ignored value in generated by logprep output",
                {
                    "input": {
                        "winlog": {"event_id": "2222", "event_data": {"Test1": 1, "Test2": 2}}
                    },
                    "expected_output": {
                        "winlog": {"event_id": "2222", "event_data": "<IGNORE_VALUE>"},
                        "test_normalized": {"test": {"field1": 1, "field2": 2}},
                    },
                    "expected_extra_output": [],
                },
                [
                    [
                        {
                            "winlog": {"event_id": "2222", "event_data": "SOME_RANDOM_CONTENT"},
                            "test_normalized": {"test": {"field1": 1, "field2": 2}},
                        }
                    ],
                    [],
                    [],
                ],
                [
                    "PASSED",
                    "Success rate: 100.00%",
                ],
                0,
            ),
            (
                "Failed test if key of <IGNORE_VALUE> is missing in generated logprep output",
                {
                    "input": {
                        "winlog": {"event_id": "2222", "event_data": {"Test1": 1, "Test2": 2}}
                    },
                    "expected_output": {
                        "winlog": {"event_id": "2222", "event_data": "<IGNORE_VALUE>"},
                        "test_normalized": {"test": {"field1": 1, "field2": 2}},
                    },
                    "expected_extra_output": [],
                },
                [
                    [
                        {
                            "winlog": {"event_id": "2222"},
                            "test_normalized": {"test": {"field1": 1, "field2": 2}},
                        }
                    ],
                    [],
                    [],
                ],
                [
                    "FAILED",
                    "expected items are missing in the generated logprep output",
                    "root['winlog']['event_data']",
                    "Success rate: 0.00%",
                ],
                1,
            ),
            (
                "Failed test because of logprep processing error",
                {
                    "input": {
                        "winlog": {"event_id": "2222", "event_data": {"Test1": 1, "Test2": 2}}
                    },
                    "expected_output": {
                        "winlog": {"event_id": "2222", "event_data": "<IGNORE_VALUE>"},
                        "test_normalized": {"test": {"field1": 1, "field2": 2}},
                    },
                    "expected_extra_output": [],
                },
                [
                    [
                        {
                            "winlog": {"event_id": "2222", "event_data": "<IGNORE_VALUE>"},
                            "test_normalized": {"test": {"field1": 1, "field2": 2}},
                        }
                    ],
                    [],
                    [
                        {
                            "error_message": "error_message",
                            "document_received": {},
                            "document_processed": {},
                        }
                    ],
                ],
                [
                    "FAILED",
                    "Following errors happened:",
                    "'error_message': 'error_message'",
                    "'document_received': {}",
                    "'document_processed': {}",
                    "Success rate: 0.00%",
                ],
                1,
            ),
        ],
    )
    @mock.patch("logprep.util.auto_rule_corpus_tester.sys.exit")
    def test_run_prints_expected_outputs_to_console(
        self,
        mock_exit,
        tmp_path,
        corpus_tester,
        test_case,
        test_data,
        mock_output,
        expected_prints,
        exit_code,
    ):
        prepare_corpus_tester(corpus_tester, tmp_path, test_data)
        if mock_output is not None:
            with mock.patch(
                "logprep.util.auto_rule_corpus_tester.get_runner_outputs"
            ) as mocked_output:
                mocked_output.return_value = mock_output
                with corpus_tester.console.capture() as capture:
                    corpus_tester.run()
        else:
            with corpus_tester.console.capture() as capture:
                corpus_tester.run()
        console_output = capture.get()
        for expected_print in expected_prints:
            assert expected_print in console_output, test_case
        mock_exit.assert_called_with(exit_code)

    @mock.patch("logprep.util.auto_rule_corpus_tester.sys.exit")
    @mock.patch("logprep.util.auto_rule_corpus_tester.parse_json")
    def test_run_logs_json_decoding_error(
        self,
        mock_parse_json,
        mock_exit,
        tmp_path,
        corpus_tester,
    ):
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
            "Json-Error decoding file rule_auto_corpus_test_out.json:",
            "Json-Error decoding file rule_auto_corpus_test_out_extra.json:",
            "Some Error: line 1 column 1 (char 0)",
            "Success rate: 0.00%",
        ]
        prepare_corpus_tester(corpus_tester, tmp_path, test_data)
        mock_parse_json.side_effect = JSONDecodeError("Some Error", "in doc", 0)
        with corpus_tester.console.capture() as capture:
            corpus_tester.run()
        console_output = capture.get()
        for expected_print in expected_prints:
            assert expected_print in console_output
        mock_exit.assert_called_with(1)

    def test_run_raises_if_case_misses_input_file(self, tmp_path, corpus_tester):
        expected_output_data_path = tmp_path / "rule_auto_corpus_test_out.json"
        expected_output_data_path.write_text("not important")
        corpus_tester._input_test_data_path = tmp_path
        with pytest.raises(ValueError, match="is missing an input file."):
            corpus_tester.run()

    @mock.patch("logprep.util.auto_rule_corpus_tester.sys.exit")
    def test_run_skips_test_if_expected_output_is_missing(self, mock_exit, tmp_path, corpus_tester):
        test_data = {
            "input": {"winlog": {"event_id": "2222", "event_data": {"Test1": 1, "Test2": 2}}},
            "expected_output": {
                "winlog": {"event_id": "2222", "event_data": "<IGNORE_VALUE>"},
                "test_normalized": {"test": {"field1": 1, "field2": 2}},
            },
            "expected_extra_output": [],
        }
        expected_prints = [
            "SKIPPED",
            "no expected output given",
            "Total test cases: 1",
            "Success rate: 100.00%",
        ]
        prepare_corpus_tester(corpus_tester, tmp_path, test_data)
        os.remove(tmp_path / "rule_auto_corpus_test_out.json")
        with corpus_tester.console.capture() as capture:
            corpus_tester.run()
        console_output = capture.get()
        for expected_print in expected_prints:
            assert expected_print in console_output
        mock_exit.assert_called_with(0)

    @mock.patch("logprep.util.auto_rule_corpus_tester.shutil.rmtree")
    @mock.patch("logprep.util.auto_rule_corpus_tester.sys.exit")
    def test_run_removes_test_tmp_dir(self, _, mock_shutil, corpus_tester):
        corpus_tester.run()
        mock_shutil.assert_called_with(corpus_tester._tmp_dir)
