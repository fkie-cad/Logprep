"""Compares the logprep output with an expected value."""

import json

from deepdiff import DeepDiff


def parse_json_path(path):
    output_jsonl = []
    with open(path) as jsonl_file:
        json_lines = jsonl_file.readline()
        json_lines = json_lines.replace('} {"@timestamp', '}\n{"@timestamp').splitlines()
        for json_line in json_lines:
            output_jsonl.append(json.loads(json_line))
    return output_jsonl


def parse_expected(path):
    expected_jsonl = []
    with open(path) as jsonl_file:
        json_lines = jsonl_file.readlines()
        for json_line in json_lines:
            expected_jsonl.append(json.loads(json_line))
    return expected_jsonl


def test_compare_output():
    output_jsonl = parse_json_path("tests/testdata/output.jsonl")
    expected_jsonl = parse_expected(
        "tests/testdata/acceptance/expected_result/expected_test_compare.jsonl"
    )

    assert DeepDiff(output_jsonl, expected_jsonl, ignore_order=True, report_repetition=True) == {}
