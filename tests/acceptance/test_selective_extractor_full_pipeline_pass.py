# pylint: disable=missing-docstring
# pylint: disable=line-too-long
import pytest

from logprep.util.configuration import Configuration
from tests.acceptance.util import get_default_logprep_config, get_test_output


@pytest.fixture(name="config")
def config_fixture():
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
    return get_default_logprep_config(pipeline, with_hmac=False)


class TestSelectiveExtractor:
    def test_selective_extractor_full_pipeline_pass(self, tmp_path, config: Configuration):
        config_path = tmp_path / "generated_config.yml"
        config.input["jsonl"][
            "documents_path"
        ] = "tests/testdata/input_logdata/selective_extractor_events.jsonl"
        config_path.write_text(config.as_yaml())
        test_output, test_custom, _ = get_test_output(str(config_path))
        assert test_output, "should not be empty"
        assert test_custom, "should not be empty"
        assert len(test_custom) == 2, "2 events extracted"
        assert {"test_topic_2": {"event": {"action": "less_evil_action"}}} in test_custom
        assert {"test_topic_1": {"user": {"agent": "ok_admin"}}} in test_custom
        assert {
            "user": {"agent": "ok_admin", "other": "field"},
            "event": {"action": "less_evil_action"},
        } in test_output

    def test_extraction_field_not_in_event(self, tmp_path, config: Configuration):
        # tests behaviour in case a field from the extraction list is not in the provided event
        config_path = tmp_path / "generated_config.yml"
        config.input["jsonl"][
            "documents_path"
        ] = "tests/testdata/input_logdata/selective_extractor_events_2.jsonl"
        config_path.write_text(config.as_yaml())
        test_output, test_custom, _ = get_test_output(str(config_path))
        assert test_output, "should not be empty"
        assert test_custom, "should not be empty"
        assert len(test_custom) == 1, "one extracted event"
        assert {"test_topic_2": {"event": {"action": "less_evil_action"}}} in test_custom
        assert {"user": {"other": "field"}, "event": {"action": "less_evil_action"}} in test_output
