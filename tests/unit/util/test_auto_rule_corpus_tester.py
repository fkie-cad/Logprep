# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=too-many-arguments
import json
import os
import re
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


def write_test_case_data_tmp_files(test_data_dir, test_case_name, test_data):
    input_data_path = test_data_dir / f"{test_case_name}_in.json"
    input_data_path.write_text(json.dumps(test_data.get("input")))
    expected_output_data_path = test_data_dir / f"{test_case_name}_out.json"
    expected_output_data_path.write_text(json.dumps(test_data.get("expected_output")))
    expected_extra_output_data_path = test_data_dir / f"{test_case_name}_out_extra.json"
    expected_extra_output_data_path.write_text(json.dumps(test_data.get("expected_extra_output")))


def prepare_corpus_tester(corpus_tester, tmp_path, test_data):
    test_data_dir = tmp_path / "test_data"
    os.makedirs(test_data_dir, exist_ok=True)
    write_test_case_data_tmp_files(test_data_dir, "rule_auto_corpus_test", test_data)
    corpus_tester._input_test_data_path = test_data_dir
    corpus_tester._tmp_dir = tmp_path


class TestAutoRuleTester:
    @pytest.mark.parametrize(
        "test_case, test_data, mock_output, expected_prints, exit_code",
        [
            (
                "One successful test",
                {
                    "input": {"message": "A B"},
                    "expected_output": {"message": "A B", "source": "A", "target": "B"},
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
                            "({'kafka_output': 'pseudonyms'},)": {
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
        assert console_error == ""
        for expected_print in expected_prints:
            assert expected_print in console_output, test_case
        mock_exit.assert_called_with(exit_code)

    @mock.patch("logprep.util.auto_rule_tester.auto_rule_corpus_tester.parse_json")
    def test_run_logs_json_decoding_error(self, mock_parse_json, tmp_path, corpus_tester):
        test_data = {"input": {}, "expected_output": {}, "expected_extra_output": []}
        prepare_corpus_tester(corpus_tester, tmp_path, test_data)
        mock_parse_json.side_effect = JSONDecodeError("Some Error", "in doc", 0)
        with pytest.raises(ValueError, match="Following parsing errors were found"):
            corpus_tester.run()

    def test_run_raises_if_case_misses_input_file(self, tmp_path, corpus_tester):
        expected_output_data_path = tmp_path / "rule_auto_corpus_test_out.json"
        expected_output_data_path.write_text('{"json":"file"}')
        corpus_tester._input_test_data_path = tmp_path
        with pytest.raises(ValueError, match="The following TestCases have no input document"):
            corpus_tester.run()

    @mock.patch("logprep.util.auto_rule_tester.auto_rule_corpus_tester.sys.exit")
    def test_run_skips_test_if_expected_output_is_missing(
        self, mock_exit, tmp_path, corpus_tester, capsys
    ):
        test_data = {
            "input": {"winlog": {"event_id": "2222", "event_data": {"Test1": 1, "Test2": 2}}},
            "expected_output": {},
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
        assert console_error == ""
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
                "message": "A B",
                "field1": "field 1 value",
                "winlog": {"event_id": "2222", "event_data": {"IpAddress": "1.2.3.4"}},
            },
            "expected_output": {
                "message": "A B",
                "source": "A",
                "target": "B",
                "field1": "field 1 value",
                "winlog": {"event_id": "2222", "event_data": {"IpAddress": "<IGNORE_VALUE>"}},
            },
            "expected_extra_output": [
                {"({'kafka': 'topic'},)": {"field1": "field 1 value"}},
                {"({'kafka': 'topic'},)": {"message": "something"}},
                {
                    "({'kafka_output': 'pseudonyms'},)": {
                        "origin": "<IGNORE_VALUE>",
                        "pseudonym": "<IGNORE_VALUE>",
                    }
                },
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
        assert console_error == ""
        for expected_print in expected_prints:
            assert expected_print in console_output
        mock_exit.assert_called_with(0)

    @mock.patch("logprep.util.auto_rule_tester.auto_rule_corpus_tester.sys.exit")
    def test_corpus_tests_dont_share_cache_between_runs_by_resetting_processors(
        self, mock_exit, tmp_path, capsys
    ):
        test_case_data = {
            "input": {
                "winlog": {"event_id": "2222", "event_data": {"IpAddress": "1.2.3.4"}},
            },
            "expected_output": {
                "winlog": {"event_id": "2222", "event_data": {"IpAddress": "<IGNORE_VALUE>"}},
            },
            "expected_extra_output": [
                {
                    "({'kafka_output': 'pseudonyms'},)": {
                        "origin": "<IGNORE_VALUE>",
                        "pseudonym": "<IGNORE_VALUE>",
                    }
                },
            ],
        }
        test_data_dir = tmp_path / "test_data"
        os.makedirs(test_data_dir, exist_ok=True)
        # run one test case two times to trigger the pseudonymizer cache.
        # Without reinitializing the processors the second test wouldn't create an extra output, as
        # the cache realizes it as an existing pseudonym already.
        write_test_case_data_tmp_files(test_data_dir, "test_case_one", test_case_data)
        write_test_case_data_tmp_files(test_data_dir, "test_case_two", test_case_data)
        config_path = "tests/testdata/config/config.yml"
        corpus_tester = RuleCorpusTester(config_path, test_data_dir)
        corpus_tester.run()
        console_output, console_error = capsys.readouterr()
        assert console_error == ""
        expected_prints = [
            "PASSED",
            "Total test cases: 2",
            "Success rate: 100.00%",
        ]
        for expected_print in expected_prints:
            assert expected_print in console_output
        mock_exit.assert_called_with(0)

    @mock.patch("logprep.util.auto_rule_tester.auto_rule_corpus_tester.sys.exit")
    def test_warnings_are_printed_inside_the_detailed_reports(self, mock_exit, tmp_path, capsys):
        test_case_data = {
            "input": {
                "field1": 2,
                "field2": 2,
                "new_field": "exists already",
            },
            "expected_output": {
                "field1": 2,
                "field2": 2,
                "new_field": "exists already",
            },
            "expected_extra_output": [],
        }
        test_data_dir = tmp_path / "test_data"
        os.makedirs(test_data_dir, exist_ok=True)
        write_test_case_data_tmp_files(test_data_dir, "test_case_one", test_case_data)
        config_path = "tests/testdata/config/config.yml"
        corpus_tester = RuleCorpusTester(config_path, test_data_dir)
        corpus_tester.run()
        console_output, console_error = capsys.readouterr()
        assert console_error == ""
        warnings_inside_details_pattern = (
            r".*Test Cases Detailed Reports.*test_case_one.*"
            r"Logprep Warnings.*FieldExistsWarning.*test_case_one.*"
            r"Test Overview"
        )
        assert re.match(warnings_inside_details_pattern, console_output, flags=re.DOTALL)
        mock_exit.assert_called_with(1)
