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
    }]
    return get_default_logprep_config(pipeline)


class TestFullHMACPassTest:

    def test_full_message_pass_with_hmac(self, tmp_path, config):
        config_path = str(tmp_path / 'generated_config.yml')
        create_temporary_config_file_at_path(config_path, config)

        with patch('logprep.connector.connector_factory.ConnectorFactory.create') as mock_connector_factory:
            input_test_event = {"test": "message"}
            expected_output_event = {
                'test': 'message',
                'hmac': {
                    'hmac': '5a77054b5f1d9ea60000520a4e2cf661e7a11de4205ca70c6977fc8040076a6e',
                    'compressed_base64': 'eJyrVipJLS5RslLKTS0uTkxPVaoFADwCBmA='
                }
            }

            kafka_output_file = mock_kafka_and_run_pipeline(config, input_test_event, mock_connector_factory, tmp_path)

            # read logprep kafka output from mocked kafka file producer
            with open(kafka_output_file, "r") as f:
                outputs = f.readlines()
                assert len(outputs) == 1, "Expected only one default kafka output"

                target, event = outputs[0].split(" ")
                event = ujson.loads(event)
                assert target == "test_input_processed"
                assert event == expected_output_event
