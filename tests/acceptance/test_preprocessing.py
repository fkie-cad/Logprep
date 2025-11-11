# pylint: disable=missing-docstring
# pylint: disable=no-self-use
from logging import DEBUG, basicConfig, getLogger
from pathlib import Path

import pytest

from logprep.util.configuration import Configuration
from tests.acceptance.util import get_default_logprep_config, get_test_output

basicConfig(level=DEBUG, format="%(asctime)-15s %(name)-5s %(levelname)-8s: %(message)s")
logger = getLogger("Logprep-Test")


@pytest.fixture(name="config")
def get_config() -> Configuration:
    pipeline = [
        {
            "dissector": {
                "type": "dissector",
                "rules": ["tests/testdata/acceptance/dissector/rules"],
            }
        }
    ]
    return get_default_logprep_config(pipeline, with_hmac=False)


class TestVersionInfoTargetField:
    def test_preprocessor_adds_version_information(self, tmp_path: Path, config: Configuration):
        config.input["jsonl"].update(
            {
                "documents_path": "tests/testdata/input_logdata/selective_extractor_events.jsonl",
                "preprocessing": {"version_info_target_field": "version_info"},
            }
        )

        config_path = tmp_path / "generated_config.yml"
        config_path.write_text(config.as_yaml())
        test_output, _, __ = get_test_output(str(config_path))
        assert test_output, "should not be empty"
        processed_event = test_output[0]
        assert processed_event.get("version_info", {}).get(
            "logprep"
        ), "no logprep version info found"
        assert processed_event.get("version_info", {}).get(
            "configuration"
        ), "no config version info found"
