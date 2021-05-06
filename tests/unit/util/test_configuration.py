from copy import deepcopy
from os.path import join
from logging import getLogger

from pytest import fail, raises

from tests.testdata.metadata import (path_to_config, path_to_schema, path_to_testdata, path_to_invalid_rules,
                                     path_to_schema2)
from logprep.util.configuration import InvalidConfigurationError, Configuration

logger = getLogger()


class Keys:
    class Labeler:
        schema = ['pipeline', 1, 'labelername', 'schema']
        include_parents = ['pipeline', 1, 'labelername', 'include_parent_labels']
        rules = ['pipeline', 1, 'labelername', 'rules']


class ConfigurationTestCommon:
    def setup_class(self):
        self.config = Configuration.create_from_yaml(path_to_config)

    def assert_fails_when_replacing_key_with_value(self, key, value, expected_message):
        config = Configuration(deepcopy(self.config))

        parent = config
        if not isinstance(key, str):
            key = list(key)
            while len(key) > 1:
                parent = parent[key.pop(0)]
            key = key[0]
        parent[key] = value

        with raises(InvalidConfigurationError, match=expected_message):
            config.verify(logger)


class TestConfiguration(ConfigurationTestCommon):
    def test_verify_passes_for_valid_configuration(self):
        try:
            self.config.verify(logger)
        except InvalidConfigurationError:
            fail('The verification should pass for a valid configuration.')

    def test_verify_fails_on_missing_required_value(self):
        for key in list(self.config.keys()):
            config = deepcopy(self.config)
            del config[key]

            with raises(InvalidConfigurationError):
                config.verify(logger)

    def test_verify_fails_on_low_process_count(self):
        for i in range(0, -10, -1):
            self.assert_fails_when_replacing_key_with_value(
                'process_count', i, 'Process count must be an integer of one or larger, not:')

    def test_verify_fails_on_empty_pipeline(self):
        self.assert_fails_when_replacing_key_with_value(
            'pipeline', [], '"pipeline" must contain at least one item!')

    def test_verify_verifies_connector_config(self):
        self.assert_fails_when_replacing_key_with_value(
            'connector', {'type': 'unknown'}, 'Unknown connector type: "unknown"')

    def test_fails_when_rules_are_invalid(self):
        self.assert_fails_when_replacing_key_with_value(
            Keys.Labeler.rules, [path_to_invalid_rules], 'Invalid rule file ".*"')

    def test_fails_when_schema_and_rules_are_inconsistent(self):
        self.assert_fails_when_replacing_key_with_value(
            Keys.Labeler.schema, path_to_schema2,
            'Invalid rule file ".*": Does not conform to labeling schema.')


class TestConfigurationProcessorLabeler(ConfigurationTestCommon):
    def test_verify_fails_if_schema_points_to_non_existing_file(self):
        self.assert_fails_when_replacing_key_with_value(
            Keys.Labeler.schema, join('non', 'existing', 'file'), 'Not a valid schema file: ')

    def test_verify_fails_if_schema_points_to_directory(self):
        self.assert_fails_when_replacing_key_with_value(
            Keys.Labeler.schema, path_to_testdata, 'Not a valid schema file: ')

    def test_verify_fails_if_rules_entry_points_to_file(self):
        self.assert_fails_when_replacing_key_with_value(
            Keys.Labeler.rules, [path_to_schema], 'Not a rule directory: ')

    def test_verify_fails_if_rules_entry_points_to_non_existing_path(self):
        self.assert_fails_when_replacing_key_with_value(
            Keys.Labeler.rules, [join('non', 'existing', 'directory')], 'Not a rule directory: ')

    def test_verify_fails_if_include_parent_labels_is_a_string(self):
        self.assert_fails_when_replacing_key_with_value(
            Keys.Labeler.include_parents, 'this is a string',
            '"include_parent_labels" must be either true or false')
