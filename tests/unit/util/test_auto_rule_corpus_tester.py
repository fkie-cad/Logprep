import json
import os
from json import JSONDecodeError
from unittest import mock

import pytest
import yaml
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

    @mock.patch("logprep.util.auto_rule_corpus_tester.sys.exit")
    def test_run_prints_logprep_errors(self, mock_exit, tmp_path, corpus_tester):
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
            "Following errors happened:",
            "'error_message': 'error_message'",
            "'document_received': {}",
            "'document_processed': {}",
            "Success rate: 0.00%",
        ]
        prepare_corpus_tester(corpus_tester, tmp_path, test_data)
        mocked_output = [
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
        ]
        corpus_tester._retrieve_pipeline_output = mock.MagicMock(return_value=mocked_output)
        with corpus_tester.console.capture() as capture:
            corpus_tester.run()
        console_output = capture.get()
        for expected_print in expected_prints:
            assert expected_print in console_output
        mock_exit.assert_called_with(1)

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
        expected_output_data_path = tmp_path / f"rule_auto_corpus_test_out.json"
        expected_output_data_path.write_text("not important")
        corpus_tester.input_test_data_path = tmp_path
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

    def test_patch_config_rewrites_input_output_and_process_count(self, corpus_tester, tmp_path):
        corpus_tester.tmp_dir = tmp_path
        original_config_path = corpus_tester.config_path
        with open(original_config_path, "r", encoding="utf8") as config_file:
            original_config = yaml.load(config_file, Loader=yaml.FullLoader)
        original_input_type = list(original_config.get("input").items())[0][1].get("type")
        original_output_type = list(original_config.get("output").items())[0][1].get("type")
        assert original_input_type == "confluentkafka_input"
        assert original_output_type == "confluentkafka_output"
        assert original_config.get("process_count") == 3
        patched_config_path = corpus_tester._patch_config(original_config_path)
        with open(patched_config_path, "r", encoding="utf8") as config_file:
            patched_config = yaml.load(config_file, Loader=yaml.FullLoader)
        patched_input = patched_config.get("input")
        patched_output = patched_config.get("output")
        patched_input_type = list(patched_input.items())[0][1].get("type")
        patched_output_type = list(patched_output.items())[0][1].get("type")
        assert patched_input_type == "jsonl_input"
        assert patched_output_type == "jsonl_output"
        assert patched_config.get("process_count") == 1
        assert str(corpus_tester.tmp_dir) in patched_input.get("test_input").get("documents_path")
        patched_test_output = patched_output.get("test_output")
        assert str(corpus_tester.tmp_dir) in patched_test_output.get("output_file")
        assert str(corpus_tester.tmp_dir) in patched_test_output.get("output_file_custom")
        assert str(corpus_tester.tmp_dir) in patched_test_output.get("output_file_error")

    def test_patch_config_removes_metrics_key_if_present(self, corpus_tester, tmp_path):
        corpus_tester.tmp_dir = tmp_path
        original_config_path = corpus_tester.config_path
        with open(original_config_path, "r", encoding="utf8") as config_file:
            original_config = yaml.load(config_file, Loader=yaml.FullLoader)
        original_config["metrics"] = {"some_unimportant": "values"}
        patched_test_config_path = f"{tmp_path}/patched_test_config.yaml"
        with open(patched_test_config_path, "w", encoding="utf8") as generated_config_file:
            yaml.safe_dump(original_config, generated_config_file)
        patched_config_path = corpus_tester._patch_config(patched_test_config_path)
        with open(patched_config_path, "r", encoding="utf8") as config_file:
            patched_config = yaml.load(config_file, Loader=yaml.FullLoader)
        assert patched_config.get("metrics") is None

    def test_prepare_connector_files_removes_version_info_from_previous_run(self, corpus_tester):
        pipeline = corpus_tester._get_patched_pipeline(corpus_tester.config_path)
        pipeline._logprep_config["input"]["version_information"] = {"logprep": 1, "config": 2}
        test_case = ("test_case", {"in": "path", "out": "path", "expected_out": "path"})
        with mock.patch("builtins.open") as _:
            with mock.patch("logprep.util.auto_rule_corpus_tester.json") as _:
                pipeline_input = pipeline._logprep_config.get("input", {})
                assert pipeline_input.get("version_information") is not None
                corpus_tester._prepare_connector_files(test_case, pipeline)
                assert pipeline_input.get("version_information") is None
