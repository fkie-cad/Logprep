"""conftest for acceptance tests"""
from pathlib import Path
from typing import Tuple
import pytest
from logprep.util.helper import remove_file_if_exists
from tests.acceptance.util import (
    get_default_logprep_config,
    get_test_output,
    get_difference,
    store_latest_test_output,
)
from logprep.util.json_handling import dump_config_as_file, parse_jsonl


@pytest.fixture(scope="function")
def get_test_result(tmp_path_factory):
    """fixture that return a logprep pipeline from list input"""

    def run_config(testcase, pipeline, testdata) -> Tuple:
        logprep_config = get_default_logprep_config(pipeline, with_hmac=False)
        logprep_config["input"]["jsonl"]["documents_path"] = testdata.get("input_data")
        test_identifier = testcase.replace(" ", "_")
        base_output_path = Path(f"tests/testdata/out/")
        output_file = base_output_path / f"latest_{test_identifier}_output.out"
        output_file_custom = base_output_path / f"latest_{test_identifier}_custom.out"
        output_file_error = base_output_path / f"latest_{test_identifier}_error.out"
        output_config = logprep_config["output"]["jsonl"]
        output_config["output_file"] = str(output_file)
        output_config["output_file_custom"] = str(output_file_custom)
        output_config["output_file_error"] = str(output_file_error)
        config_path = str(tmp_path_factory.getbasetemp() / "generated_config.yml")
        dump_config_as_file(config_path, logprep_config)
        test_output, test_custom, test_failed = get_test_output(config_path, remove_on_finish=False)
        test_list = [
            (test_output, testdata.get("expected_output")),
            (test_custom, testdata.get("expected_custom")),
            (test_failed, testdata.get("expected_failed")),
        ]
        results = []
        for test, expected_path in test_list:
            if expected_path:
                expected = parse_jsonl(expected_path)
                assert test, "should not be empty cause expected path was given"
                diff = get_difference(test, expected)
                diff["expected_path"] = expected_path
                results.append(diff)
        return results

    return run_config
