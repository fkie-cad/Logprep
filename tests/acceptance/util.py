#!/usr/bin/python3
import json
from logging import getLogger, DEBUG, basicConfig
from os import remove, path, makedirs
from copy import deepcopy

from yaml import safe_dump

from logprep.runner import Runner

basicConfig(level=DEBUG, format='%(asctime)-15s %(name)-5s %(levelname)-8s: %(message)s')
logger = getLogger('Logprep-Test')


def recursive_compare(test_output, expected_output):
    result = None

    if not isinstance(test_output, type(expected_output)):
        return test_output, expected_output

    elif isinstance(test_output, dict) and isinstance(expected_output, dict):
        if sorted(test_output.keys()) != sorted(expected_output.keys()):
            return sorted(test_output.keys()), sorted(expected_output.keys())

        for key in test_output.keys():
            result = recursive_compare(test_output[key], expected_output[key])
            if result:
                return result

    elif isinstance(test_output, list) and isinstance(expected_output, list):
        for x, _ in enumerate(test_output):
            result = recursive_compare(test_output[x], expected_output[x])
            if result:
                return result

    else:
        if test_output != expected_output:
            result = test_output, expected_output

    return result


def get_difference(test_output, expected_output):
    for x, _ in enumerate(test_output):
        test_event = deepcopy(test_output[x])
        expected_event = deepcopy(expected_output[x])
        difference = recursive_compare(test_event, expected_event)
        if difference:
            return {'event_line_no': x, 'difference': difference}
    return {'event_line_no': None, 'difference': (None, None)}


def store_latest_test_output(target_output_identifier, output_of_test):
    """ Store output for test.

    This can be used to create expected outputs for new rules.
    The resulting file can be used as it is.

    """

    output_dir = 'tests/testdata/out'
    latest_output_path = path.join(output_dir, 'latest_{}.out'.format(target_output_identifier))

    if not path.exists(output_dir):
        makedirs(output_dir)

    with open(latest_output_path, 'w') as latest_output:
        for test_output_line in output_of_test:
            latest_output.write(json.dumps(test_output_line) + '\n')


def create_temporary_config_file_at_path(config_path, config):
    with open(config_path, 'w') as generated_config_file:
        safe_dump(config, generated_config_file)


def get_test_output(config_path):
    patched_runner = get_patched_runner(config_path)

    test_output_path = patched_runner._configuration['connector']['output_path']
    remove_file_if_exists(test_output_path)

    patched_runner.start()
    parsed_test_output = parse_jsonl(test_output_path)

    remove_file_if_exists(test_output_path)

    return parsed_test_output


def get_test_output_multi(config_path):
    patched_runner = get_patched_runner(config_path)

    parsed_outputs = list()
    output_paths = list()
    output_paths.append(patched_runner._configuration['connector'].get('output_path', None))
    output_paths.append(patched_runner._configuration['connector'].get('output_path_custom', None))
    output_paths.append(patched_runner._configuration['connector'].get('output_path_errors', None))
    output_paths = [output_path for output_path in output_paths if output_path]
    
    for output_path in output_paths:
        remove_file_if_exists(output_path)

    patched_runner.start()

    for output_path in output_paths:
        parsed_outputs.append(parse_jsonl(output_path))
        remove_file_if_exists(output_path)

    return parsed_outputs


def get_patched_runner(config_path):
    runner = Runner(bypass_check_to_obtain_non_singleton_instance=True)
    runner.set_logger(logger)
    runner.load_configuration(config_path)
    patch_runner_to_stop_on_empty_pipeline(runner)

    return runner


def patch_runner_to_stop_on_empty_pipeline(runner):
    runner._keep_iterating = lambda: False


def remove_file_if_exists(test_output_path):
    try:
        remove(test_output_path)
    except FileNotFoundError:
        pass


def parse_jsonl(jsonl_path):
    parsed_events = []
    with open(jsonl_path, 'r') as jsonl_file:
        for json_string in jsonl_file.readlines():
            if json_string.strip() != '':
                event = json.loads(json_string)
                parsed_events.append(event)
    return parsed_events


def parse_json(json_path):
    with open(json_path, 'r') as json_file:
        return json.load(json_file)


def assert_result_equal_expected(config, expected_output, tmp_path):
    pass
