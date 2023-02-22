# pylint: disable=missing-docstring
# pylint: disable=protected-access
import json
import os
from json import JSONDecodeError
from unittest import mock

import pytest

from logprep.util.auto_rule_tester.auto_rule_corpus_tester import RuleCorpusTester
from logprep.util.getter import GetterFactory


@pytest.fixture(name="corpus_tester")
def fixture_auto_rule_corpus_tester():
    config_path = "tests/testdata/config/config.yml"
    data_dir = "will be overwritten in test cases"
    corpus_tester = RuleCorpusTester(config_path, data_dir)
    return corpus_tester


def prepare_corpus_tester(corpus_tester, tmp_path, test_data):
    case_name = "rule_auto_corpus_test"
    test_data_dir = tmp_path / "test_data"
    os.makedirs(test_data_dir, exist_ok=True)
    input_data_path = test_data_dir / f"{case_name}_in.json"
    input_data_path.write_text(json.dumps(test_data.get("input")))
    expected_output_data_path = test_data_dir / f"{case_name}_out.json"
    expected_output_data_path.write_text(json.dumps(test_data.get("expected_output")))
    expected_extra_output_data_path = test_data_dir / f"{case_name}_out_extra.json"
    expected_extra_output_data_path.write_text(json.dumps(test_data.get("expected_extra_output")))
    corpus_tester._input_test_data_path = test_data_dir
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
                    {
                        "winlog": {"event_id": "2222", "event_data": {"Test1": 1}},
                        "test_normalized": {"test": {"field1": 1}},
                    },
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
                    {
                        "winlog": {"event_id": "2222", "event_data": "SOME_RANDOM_CONTENT"},
                        "test_normalized": {"test": {"field1": 1, "field2": 2}},
                    },
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
                    {
                        "winlog": {"event_id": "2222"},
                        "test_normalized": {"test": {"field1": 1, "field2": 2}},
                    },
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
                "Successful test with optional key missing in generated by logprep output",
                {
                    "input": {
                        "winlog": {"event_id": "2222", "event_data": {"Test1": 1, "Test2": 2}}
                    },
                    "expected_output": {
                        "winlog": {"event_id": "2222", "event_data": "<OPTIONAL_KEY>"},
                        "test_normalized": {"test": {"field1": 1, "field2": 2}},
                    },
                    "expected_extra_output": [],
                },
                [
                    {
                        "winlog": {"event_id": "2222"},
                        "test_normalized": {"test": {"field1": 1, "field2": 2}},
                    },
                    [],
                ],
                [
                    "PASSED",
                    "Success rate: 100.00%",
                ],
                0,
            ),
            (
                "Successful test with optional key present in generated by logprep output",
                {
                    "input": {
                        "winlog": {"event_id": "2222", "event_data": {"Test1": 1, "Test2": 2}}
                    },
                    "expected_output": {
                        "winlog": {"event_id": "2222", "event_data": "<OPTIONAL_KEY>"},
                        "test_normalized": {"test": {"field1": 1, "field2": 2}},
                    },
                    "expected_extra_output": [],
                },
                [
                    {
                        "winlog": {"event_id": "2222", "event_data": "something"},
                        "test_normalized": {"test": {"field1": 1, "field2": 2}},
                    },
                    [],
                ],
                [
                    "PASSED",
                    "Success rate: 100.00%",
                ],
                0,
            ),
        ],
    )
    @mock.patch("logprep.util.auto_rule_tester.auto_rule_corpus_tester.sys.exit")
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
        capsys,
    ):
        prepare_corpus_tester(corpus_tester, tmp_path, test_data)
        if mock_output is not None:
            with mock.patch(
                "logprep.util.auto_rule_tester.auto_rule_corpus_tester.Pipeline.process_pipeline"
            ) as mock_process_pipeline:
                mock_process_pipeline.return_value = mock_output
                corpus_tester.run()
        else:
            corpus_tester.run()
        console_output, console_error = capsys.readouterr()
        for expected_print in expected_prints:
            assert expected_print in console_output, test_case
        mock_exit.assert_called_with(exit_code)

    @mock.patch("logprep.util.auto_rule_tester.auto_rule_corpus_tester.sys.exit")
    @mock.patch("logprep.util.auto_rule_tester.auto_rule_corpus_tester.parse_json")
    def test_run_logs_json_decoding_error(
        self, mock_parse_json, mock_exit, tmp_path, corpus_tester, capsys
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
            "Json-Error decoding file rule_auto_corpus_test_in.json:",
            "Json-Error decoding file rule_auto_corpus_test_out.json:",
            "Json-Error decoding file rule_auto_corpus_test_out_extra.json:",
            "Some Error: line 1 column 1 (char 0)",
            "Success rate: 0.00%",
        ]
        prepare_corpus_tester(corpus_tester, tmp_path, test_data)
        mock_parse_json.side_effect = JSONDecodeError("Some Error", "in doc", 0)
        corpus_tester.run()
        console_output, console_error = capsys.readouterr()
        for expected_print in expected_prints:
            assert expected_print in console_output
        mock_exit.assert_called_with(1)

    def test_run_raises_if_case_misses_input_file(self, tmp_path, corpus_tester):
        expected_output_data_path = tmp_path / "rule_auto_corpus_test_out.json"
        expected_output_data_path.write_text("not important")
        corpus_tester._input_test_data_path = tmp_path
        with pytest.raises(ValueError, match="is missing an input file."):
            corpus_tester.run()

    @mock.patch("logprep.util.auto_rule_tester.auto_rule_corpus_tester.sys.exit")
    def test_run_skips_test_if_expected_output_is_missing(
        self, mock_exit, tmp_path, corpus_tester, capsys
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
            "SKIPPED",
            "no expected output given",
            "Total test cases: 1",
            "Success rate: 100.00%",
        ]
        prepare_corpus_tester(corpus_tester, tmp_path, test_data)
        os.remove(tmp_path / "test_data" / "rule_auto_corpus_test_out.json")
        corpus_tester.run()
        console_output, console_error = capsys.readouterr()
        for expected_print in expected_prints:
            assert expected_print in console_output
        mock_exit.assert_called_with(0)

    @mock.patch("logprep.util.auto_rule_tester.auto_rule_corpus_tester.shutil.rmtree")
    @mock.patch("logprep.util.auto_rule_tester.auto_rule_corpus_tester.sys.exit")
    def test_run_removes_test_tmp_dir(self, _, mock_shutil, corpus_tester):
        corpus_tester.run()
        mock_shutil.assert_called_with(corpus_tester._tmp_dir)

    @mock.patch("logprep.util.auto_rule_tester.auto_rule_corpus_tester.sys.exit")
    def test_run_with_two_processors_that_have_different_extra_outputs(
        self, mock_exit, tmp_path, capsys
    ):
        config_path = "tests/testdata/config/config.yml"
        config = GetterFactory.from_string(config_path).get_yaml()
        config["pipeline"].append(
            {
                "selective_extractor": {
                    "type": "selective_extractor",
                    "specific_rules": ["tests/testdata/unit/selective_extractor/rules/specific"],
                    "generic_rules": [],
                }
            }
        )
        test_config_path = tmp_path / "test_config.yml"
        test_config_path.write_text(json.dumps(config), encoding="utf8")
        corpus_tester = RuleCorpusTester(str(test_config_path), "")
        test_data = {
            "input": {
                "message": "something",
                "field1": "field 1 value",
                "winlog": {"event_id": "2222", "event_data": {"IpAddress": "1.2.3.4"}},
            },
            "expected_output": {
                "message": "something",
                "field1": "field 1 value",
                "winlog": {"event_id": "2222", "event_data": {"IpAddress": "<IGNORE_VALUE>"}},
            },
            "expected_extra_output": [
                {"test_specific_topic": {"field1": "field 1 value"}},
                {"test_specific_topic": {"message": "something"}},
                {"pseudonyms": {"origin": "<IGNORE_VALUE>", "pseudonym": "<IGNORE_VALUE>"}},
            ],
        }
        expected_prints = [
            "PASSED",
            "Total test cases: 1",
            "Success rate: 100.00%",
        ]
        prepare_corpus_tester(corpus_tester, tmp_path, test_data)
        corpus_tester.run()
        console_output, console_error = capsys.readouterr()
        for expected_print in expected_prints:
            assert expected_print in console_output
        mock_exit.assert_called_with(0)
