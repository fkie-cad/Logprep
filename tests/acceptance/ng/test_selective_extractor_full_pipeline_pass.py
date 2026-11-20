# pylint: disable=missing-docstring
# pylint: disable=line-too-long

import json

import pytest

from logprep.ng.util.configuration import Configuration
from tests.acceptance.ng.util import get_default_logprep_config, get_test_outputs


@pytest.fixture(name="config")
def config_fixture(tmp_path):
    pipeline = [
        {
            "dissector": {
                "type": "dissector",
                "rules": ["tests/testdata/acceptance/dissector/rules"],
            }
        },
        {
            "selective_extractor": {
                "type": "selective_extractor",
                "rules": ["tests/testdata/acceptance/selective_extractor/rules"],
            }
        },
    ]
    config = get_default_logprep_config(pipeline, with_hmac=False)
    config.error_output = {
        "error": {"type": "jsonl_output", "output_file": str(tmp_path / "errors.jsonl")}
    }
    return config


class TestSelectiveExtractor:
    async def test_selective_extractor_full_pipeline_pass(self, tmp_path, config: Configuration):
        config_path = tmp_path / "generated_config.yml"
        config.input["jsonl"][
            "documents_path"
        ] = "tests/testdata/input_logdata/selective_extractor_events.jsonl"
        config_path.write_text(config.as_yaml())
        out = await get_test_outputs(config_path)

        assert out["jsonl"] == [], "NG routes events with warnings to the error output"
        assert len(out["error"]) == 1
        assert out["jsonl_custom"] == [], "missing selected fields prevent partial extra events"
        assert {
            "user": {"agent": "ok_admin", "other": "field"},
            "event": {"action": "less_evil_action"},
            "tags": ["_selective_extractor_missing_field_warning"],
        } == json.loads(out["error"][0]["event"])

    async def test_extraction_field_not_in_event(self, tmp_path, config: Configuration):
        # tests behaviour in case a field from the extraction list is not in the provided event
        config_path = tmp_path / "generated_config.yml"
        config.input["jsonl"][
            "documents_path"
        ] = "tests/testdata/input_logdata/selective_extractor_events_2.jsonl"
        config_path.write_text(config.as_yaml())
        out = await get_test_outputs(config_path)

        assert out["jsonl"] == [], "NG routes events with warnings to the error output"
        assert len(out["error"]) == 1
        assert out["jsonl_custom"] == [], "missing selected fields prevent partial extra events"
        assert {
            "user": {"other": "field"},
            "event": {"action": "less_evil_action"},
            "tags": ["_selective_extractor_missing_field_warning"],
        } == json.loads(out["error"][0]["event"])
