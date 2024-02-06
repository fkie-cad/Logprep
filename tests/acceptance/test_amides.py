#!/usr/bin/env python3
# pylint: disable=not-an-iterable
# pylint: disable=missing-docstring

from logging import DEBUG, basicConfig, getLogger
from pathlib import Path

import pytest

from logprep.util.configuration import Configuration
from tests.acceptance.util import get_test_output

basicConfig(level=DEBUG, format="%(asctime)-15s %(name)-5s %(levelname)-8s: %(message)s")
logger = getLogger("Logprep-Test")


@pytest.fixture
def config():
    config_dict = {
        "process_count": 1,
        "timeout": 0.1,
        "profile_pipelines": True,
        "pipeline": [
            {
                "amides": {
                    "type": "amides",
                    "models_path": "tests/testdata/unit/amides/model.zip",
                    "specific_rules": ["tests/testdata/unit/amides/rules/specific"],
                    "generic_rules": ["tests/testdata/unit/amides/rules/generic"],
                    "max_cache_entries": 1000,
                    "num_rule_attributions": 10,
                    "decision_threshold": 0.32,
                }
            }
        ],
        "input": {
            "jsonl_input": {
                "type": "jsonl_input",
                "documents_path": "tests/testdata/acceptance/amides/amides_input.jsonl",
            }
        },
        "output": {
            "jsonl_output": {
                "type": "jsonl_output",
                "output_file": "tests/testdata/acceptance/amides/amides_output.jsonl",
            }
        },
    }

    return Configuration(**config_dict)


def test_amides(tmp_path: Path, config: Configuration):
    config_path = tmp_path / "generated_config.yml"
    config_path.write_text(config.as_yaml())

    test_output = get_test_output(str(config_path))
    test_output_documents = [event for event in test_output[0] if event.get("amides")]
    attributed_documents = [
        event for event in test_output_documents if event.get("amides").get("attributions")
    ]
    assert len(test_output_documents) == 20
    assert len(attributed_documents) == 8
