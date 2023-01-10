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
            )
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
