# pylint: disable=missing-docstring
# pylint: disable=line-too-long
import pytest

from tests.acceptance.util import (
    get_test_output,
    get_default_logprep_config,
)
from logprep.util.json_handling import dump_config_as_file


@pytest.fixture(name="config")
def config_fixture():
    pipeline = [
        {
            "normalizername": {
                "type": "normalizer",
                "specific_rules": ["tests/testdata/acceptance/normalizer/rules_static/specific"],
                "generic_rules": ["tests/testdata/acceptance/normalizer/rules_static/generic"],
                "regex_mapping": "tests/testdata/acceptance/normalizer/rules_static/regex_mapping.yml",
            }
        },
        {
            "selective_extractor": {
                "type": "selective_extractor",
                "specific_rules": ["tests/testdata/acceptance/selective_extractor/rules/specific"],
                "generic_rules": ["tests/testdata/acceptance/selective_extractor/rules/generic"],
            }
        },
    ]
    return get_default_logprep_config(pipeline, with_hmac=False)


class TestSelectiveExtractor:
    def test_selective_extractor_full_pipeline_pass(self, tmp_path, config):
        config_path = str(tmp_path / "generated_config.yml")
        config["input"]["jsonl"][
            "documents_path"
        ] = "tests/testdata/input_logdata/selective_extractor_events.jsonl"
        dump_config_as_file(config_path, config)
        test_output, test_custom, _ = get_test_output(config_path)
        assert test_output, "should not be empty"
        assert test_custom, "should not be empty"
        assert len(test_custom) == 2, "2 events extracted"
        assert {"test_topic_2": {"event": {"action": "less_evil_action"}}} in test_custom
        assert {"test_topic_1": {"user": {"agent": "ok_admin"}}} in test_custom
        assert {
            "user": {"agent": "ok_admin", "other": "field"},
            "event": {"action": "less_evil_action"},
        } in test_output

    def test_extraction_field_not_in_event(self, tmp_path, config):
        # tests behaviour in case a field from the extraction list is not in the provided event
        config_path = str(tmp_path / "generated_config.yml")
        config["input"]["jsonl"][
            "documents_path"
        ] = "tests/testdata/input_logdata/selective_extractor_events_2.jsonl"
        dump_config_as_file(config_path, config)
        test_output, test_custom, _ = get_test_output(config_path)
        assert test_output, "should not be empty"
        assert test_custom, "should not be empty"
        assert len(test_custom) == 1, "one extracted event"
        assert {"test_topic_2": {"event": {"action": "less_evil_action"}}} in test_custom
        assert {"user": {"other": "field"}, "event": {"action": "less_evil_action"}} in test_output
