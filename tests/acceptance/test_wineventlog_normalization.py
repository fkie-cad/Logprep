# pylint: disable=missing-docstring
# pylint: disable=line-too-long
#!/usr/bin/python3
import re
from os import path

import pytest

from logprep.framework.pipeline import Pipeline
from logprep.util.json_handling import dump_config_as_file, parse_jsonl
from tests.acceptance.util import (
    get_default_logprep_config,
    get_difference,
    get_test_output,
    start_logprep,
    stop_logprep,
    store_latest_test_output,
    wait_for_output,
)


@pytest.fixture(name="config")
def create_config():
    pipeline = [
        {
            "normalizername": {
                "type": "normalizer",
                "specific_rules": ["tests/testdata/acceptance/normalizer/rules_static/specific"],
                "generic_rules": ["tests/testdata/acceptance/normalizer/rules_static/generic"],
                "regex_mapping": "tests/testdata/acceptance/normalizer/rules_static/regex_mapping.yml",
            }
        }
    ]
    return get_default_logprep_config(pipeline, with_hmac=False)


def test_events_normalized_without_errors(tmp_path, config):
    config["input"]["jsonl"][
        "documents_path"
    ] = "tests/testdata/input_logdata/wineventlog_raw.jsonl"
    output_file = tmp_path / "output.jsonl"
    custom_file = tmp_path / "custom.jsonl"
    error_file = tmp_path / "error.jsonl"
    config["output"]["jsonl"]["output_file"] = str(output_file)
    config["output"]["jsonl"]["output_file_custom"] = str(custom_file)
    config["output"]["jsonl"]["output_file_error"] = str(error_file)
    config_path = str(tmp_path / "generated_config.yml")
    dump_config_as_file(config_path, config)
    proc = start_logprep(config_path)
    wait_for_output(proc, "no documents left")
    stop_logprep(proc)
    assert len(output_file.read_text().splitlines()) > 0, "documents were processed"
    assert len(error_file.read_text().splitlines()) == 0, "no errors occurred"
    assert len(custom_file.read_text().splitlines()) == 0, "no custom output was written"
