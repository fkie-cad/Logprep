#!/usr/bin/env python3
# pylint: disable=not-an-iterable
# pylint: disable=missing-docstring

import tempfile
from logging import DEBUG, basicConfig, getLogger
from pathlib import Path

import pytest

from logprep.ng.util.configuration import Configuration
from tests.acceptance.ng.util import get_test_outputs

basicConfig(level=DEBUG, format="%(asctime)-15s %(name)-5s %(levelname)-8s: %(message)s")
logger = getLogger("Logprep-Test")


@pytest.fixture(name="configuration")
def config():
    config_dict = {
        "process_count": 1,
        "timeout": 0.1,
        "profile_pipelines": False,
        "pipeline": [
            {
                "amides": {
                    "type": "amides",
                    "models_path": "tests/testdata/unit/amides/model.zip",
                    "rules": ["tests/testdata/unit/amides/rules"],
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
            "default_and_extras": {
                "type": "jsonl_output",
                "output_file": f"{tempfile.gettempdir()}/amides_output.jsonl",
            }
        },
    }

    return Configuration(**config_dict)


@pytest.mark.filterwarnings("ignore:Trying to unpickle.*")
@pytest.mark.timeout(3)
async def test_amides(tmp_path: Path, configuration: Configuration):
    config_path = tmp_path / "generated_config.yml"
    config_path.write_text(configuration.as_yaml())

    outputs = await get_test_outputs(config_path)

    events = outputs["default_and_extras"]

    test_output_documents = [event for event in events if event.get("amides")]
    attributed_documents = [
        event for event in test_output_documents if event.get("amides").get("attributions")
    ]
    assert len(test_output_documents) == 20
    assert len(attributed_documents) == 8
