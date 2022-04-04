from copy import deepcopy
from logging import getLogger

from pytest import fail, raises

from logprep.util.configuration import InvalidConfigurationError, Configuration
from tests.testdata.metadata import path_to_config

logger = getLogger()


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
            fail("The verification should pass for a valid configuration.")

    def test_verify_fails_on_missing_required_value(self):
        for key in list(self.config.keys()):
            config = deepcopy(self.config)
            del config[key]

            with raises(InvalidConfigurationError):
                config.verify(logger)

    def test_verify_fails_on_low_process_count(self):
        for i in range(0, -10, -1):
            self.assert_fails_when_replacing_key_with_value(
                "process_count", i, "Process count must be an integer of one or larger, not:"
            )

    def test_verify_fails_on_empty_pipeline(self):
        self.assert_fails_when_replacing_key_with_value(
            "pipeline", [], '"pipeline" must contain at least one item!'
        )

    def test_verify_verifies_connector_config(self):
        self.assert_fails_when_replacing_key_with_value(
            "connector", {"type": "unknown"}, 'Unknown connector type: "unknown"'
        )
