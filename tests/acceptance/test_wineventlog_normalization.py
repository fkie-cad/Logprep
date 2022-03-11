#!/usr/bin/python3
import pytest

from tests.acceptance.util import *
from logprep.util.json_handling import dump_config_as_file, parse_jsonl


@pytest.fixture
def config():
    config_yml = {
        'process_count': 1,
        'timeout': 0.1,
        'profile_pipelines': True,
        'pipeline': [
            {
                'normalizername': {
                    'type': 'normalizer',
                    'specific_rules': ['tests/testdata/acceptance/normalizer/rules_static/specific'],
                    'generic_rules': ['tests/testdata/acceptance/normalizer/rules_static/generic'],
                    'regex_mapping': 'tests/testdata/acceptance/normalizer/rules_static/regex_mapping.yml'
                }
            }
        ],
        'connector': {
            'type': 'writer',
            'output_path': 'tests/testdata/acceptance/test_kafka_data_processing_acceptance.out',
            'input_path': 'tests/testdata/input_logdata/kafka_raw_event.jsonl'
        }
    }
    return config_yml


def test_events_normalized_correctly(tmp_path, config):
    expected_output = 'normalized_win_event_log.jsonl'
    expected_output_path = path.join('tests/testdata/acceptance/expected_result', expected_output)

    config_path = str(tmp_path / 'generated_config.yml')
    dump_config_as_file(config_path, config)

    test_output = get_test_output(config_path)
    store_latest_test_output(expected_output, test_output)

    expected_output = parse_jsonl(expected_output_path)

    result = get_difference(test_output, expected_output)

    assert result['difference'][0] == result['difference'][1], \
        'Missmatch in event at line {}!'.format(result['event_line_no'])
