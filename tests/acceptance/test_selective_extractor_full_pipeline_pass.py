from unittest.mock import patch

import pytest
import ujson

from tests.acceptance.util import create_temporary_config_file_at_path, mock_kafka_and_run_pipeline, \
    get_default_logprep_config


@pytest.fixture
def config():
    pipeline = [{
        'normalizername': {
            'type': 'normalizer',
            'specific_rules': ['tests/testdata/acceptance/normalizer/rules_static/specific'],
            'generic_rules': ['tests/testdata/acceptance/normalizer/rules_static/generic'],
            'regex_mapping': 'tests/testdata/acceptance/normalizer/rules_static/regex_mapping.yml'
        }
    }, {
        'selective_extractor': {
            'type': 'selective_extractor',
            'selective_extractor_topic': 'selection_target',
            'extractor_list': 'tests/testdata/acceptance/selective_extractor/whitelist.txt'
        }
    }]
    return get_default_logprep_config(pipeline)


def check_extractions(expected_extraction_event, expected_pipeline_event, kafka_output_file):
    # read logprep kafka output from mocked kafka file producer
    with open(kafka_output_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 2, "Expected two events: Selected Output and default pipeline output"
        for line in lines:
            target, event = line.split(" ")
            event = ujson.loads(event)
            if target == "selection_target":
                assert event == expected_extraction_event
            if target == "test_input_processed":
                assert event == expected_pipeline_event


class TestSelectiveExtractor:

    def test_selective_extractor_full_pipeline_pass(self, tmp_path, config):
        config_path = str(tmp_path / 'generated_config.yml')
        create_temporary_config_file_at_path(config_path, config)

        with patch('logprep.connector.connector_factory.ConnectorFactory.create') as mock_connector_factory:
            input_test_event = {
                "user": {"agent": "ok_admin", "other": "field"},
                "event": {"action": "less_evil_action"},
            }
            expected_extraction_event = {
                "user": {"agent": "ok_admin"},
                "event": {"action": "less_evil_action"},
            }
            expected_pipeline_event = {
                'user': {'agent': 'ok_admin', 'other': 'field'},
                'event': {'action': 'less_evil_action'},
                'hmac': {
                    'hmac': '18e2a3df8590b6cbab040f7ea4b9df399febbb5f259817459c460b196f42c4ca',
                    'compressed_base64': 'eJwtykEOgCAMBdG7/DUn4DKESNVGLImtbEjvLhq382bgVroQB/JGYohoR8rlZEFAs/01rEy1wAOof8+cF+MmkyqpJupc05/cH589HPw='
                }
            }

            kafka_output_file = mock_kafka_and_run_pipeline(config, input_test_event, mock_connector_factory, tmp_path)

            check_extractions(expected_extraction_event, expected_pipeline_event, kafka_output_file)

    def test_extraction_field_not_in_event(self, tmp_path, config):
        # tests behaviour in case a field from the extraction list is not in the provided event
        config_path = str(tmp_path / 'generated_config.yml')
        create_temporary_config_file_at_path(config_path, config)

        with patch('logprep.connector.connector_factory.ConnectorFactory.create') as mock_connector_factory:
            input_test_event = {
                "user": {"other": "field"},
                "event": {"action": "less_evil_action"},
            }
            expected_extraction_event = {
                "event": {"action": "less_evil_action"},
            }
            expected_pipeline_event = {
                'user': {'other': 'field'},
                'event': {'action': 'less_evil_action'},
                'hmac': {
                    'hmac': 'cae31468df13e701f46e70bfbea86f29e77ab69f6253ac156ddda5e38fdbed92',
                    'compressed_base64': 'eJyrViotTi1SsqpWyi/JADGU0jJTc1KUanWUUstS80pAMonJJZn5eUCpnNTi4vjUssyceKhQbS0Ay/oWvQ=='
                }
            }

            kafka_output_file = mock_kafka_and_run_pipeline(config, input_test_event, mock_connector_factory, tmp_path)

            check_extractions(expected_extraction_event, expected_pipeline_event, kafka_output_file)



