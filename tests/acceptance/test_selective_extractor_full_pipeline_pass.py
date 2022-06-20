# pylint: disable=missing-docstring
# pylint: disable=line-too-long
from unittest.mock import patch

import pytest

from tests.acceptance.util import mock_kafka_and_run_pipeline, get_default_logprep_config
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
    return get_default_logprep_config(pipeline)


class TestSelectiveExtractor:
    def test_selective_extractor_full_pipeline_pass(self, tmp_path, config):
        config_path = str(tmp_path / "generated_config.yml")
        dump_config_as_file(config_path, config)

        with patch(
            "logprep.connector.connector_factory.ConnectorFactory.create"
        ) as mock_connector_factory:
            input_test_event = {
                "user": {"agent": "ok_admin", "other": "field"},
                "event": {"action": "less_evil_action"},
            }

            kafka_output_file = mock_kafka_and_run_pipeline(
                config, input_test_event, mock_connector_factory, tmp_path
            )

            with open(kafka_output_file, "r", encoding="utf8") as output_file:
                lines = output_file.readlines()
                assert len(lines) == 3, "expected default pipeline output and two extracted events"
                assert 'test_topic_2 {"event":{"action":"less_evil_action"}}\n' in lines
                assert 'test_topic_1 {"user":{"agent":"ok_admin"}}\n' in lines
                assert (
                    "test_input_processed "
                    '{"user":'
                    '{"agent":"ok_admin","other":"field"},'
                    '"event":'
                    '{"action":"less_evil_action"},'
                    '"hmac":'
                    '{"hmac":"18e2a3df8590b6cbab040f7ea4b9df399febbb5f259817459c460b196f42c4ca",'
                    '"compressed_base64":'
                    '"eJwtykEOgCAMBdG7/DUn4DKESNVGLImtbEjvLhq382bgVroQB/JGYohoR8rlZEFAs/01rEy1wAOof8+cF+MmkyqpJupc05/cH589HPw="}}\n'
                ) in lines

    def test_extraction_field_not_in_event(self, tmp_path, config):
        # tests behaviour in case a field from the extraction list is not in the provided event
        config_path = str(tmp_path / "generated_config.yml")
        dump_config_as_file(config_path, config)

        with patch(
            "logprep.connector.connector_factory.ConnectorFactory.create"
        ) as mock_connector_factory:
            input_test_event = {
                "user": {"other": "field"},
                "event": {"action": "less_evil_action"},
            }

            kafka_output_file = mock_kafka_and_run_pipeline(
                config, input_test_event, mock_connector_factory, tmp_path
            )

            with open(kafka_output_file, "r", encoding="utf8") as output_file:
                lines = output_file.readlines()
                assert len(lines) == 2, "expected default pipeline output and one extracted event"
                assert 'test_topic_2 {"event":{"action":"less_evil_action"}}\n' in lines
                assert (
                    "test_input_processed "
                    '{"user":'
                    '{"other":"field"},"event":{"action":"less_evil_action"},'
                    '"hmac":{"hmac":"cae31468df13e701f46e70bfbea86f29e77ab69f6253ac156ddda5e38fdbed92",'
                    '"compressed_base64":'
                    '"eJyrViotTi1SsqpWyi/JADGU0jJTc1KUanWUUstS80pAMonJJZn5eUCpnNTi4vjUssyceKhQbS0Ay/oWvQ=="}}\n'
                ) in lines
