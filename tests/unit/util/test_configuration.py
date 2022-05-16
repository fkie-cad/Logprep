# pylint: disable=missing-docstring
# pylint: disable=protected-access

from copy import deepcopy
from logging import getLogger

import pytest

from tests.testdata.metadata import path_to_config
from logprep.util.configuration import (
    InvalidConfigurationError,
    Configuration,
    InvalidStatusLoggerConfigurationError,
    RequiredConfigurationKeyMissingError,
    InvalidConfigurationErrors,
)

logger = getLogger()


class TestConfiguration:

    config: dict

    def setup_method(self):
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

        with pytest.raises(InvalidConfigurationError, match=expected_message):
            config.verify(logger)

    def test_verify_passes_for_valid_configuration(self):
        try:
            self.config.verify(logger)
        except InvalidConfigurationError:
            pytest.fail("The verification should pass for a valid configuration.")

    def test_verify_fails_on_missing_required_value(self):
        for key in list(self.config.keys()):
            config = deepcopy(self.config)
            del config[key]

            with pytest.raises(InvalidConfigurationError):
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

    @pytest.mark.parametrize(
        "test_case, status_logger_config_dict, raised_error",
        [
            (
                "valid configuration",
                {
                    "status_logger": {
                        "period": 10,
                        "enabled": True,
                        "cumulative": True,
                        "aggregate_processes": True,
                        "targets": [
                            {"prometheus": {"port": 8000}},
                            {
                                "file": {
                                    "path": "./logs/status.json",
                                    "rollover_interval": 86400,
                                    "backup_count": 10,
                                }
                            },
                        ],
                    }
                },
                None,
            ),
            (
                "key period is missing",
                {
                    "status_logger": {
                        "enabled": True,
                        "cumulative": True,
                        "aggregate_processes": True,
                        "targets": [
                            {"prometheus": {"port": 8000}},
                            {
                                "file": {
                                    "path": "./logs/status.json",
                                    "rollover_interval": 86400,
                                    "backup_count": 10,
                                }
                            },
                        ],
                    }
                },
                RequiredConfigurationKeyMissingError,
            ),
            (
                "empty target",
                {
                    "status_logger": {
                        "period": 10,
                        "enabled": True,
                        "cumulative": True,
                        "aggregate_processes": True,
                        "targets": [],
                    }
                },
                InvalidStatusLoggerConfigurationError,
            ),
            (
                "unkown target",
                {
                    "status_logger": {
                        "period": 10,
                        "enabled": True,
                        "cumulative": True,
                        "aggregate_processes": True,
                        "targets": [{"webserver": {"does-not": "exist"}}],
                    }
                },
                InvalidStatusLoggerConfigurationError,
            ),
            (
                "missing key in prometheus target config",
                {
                    "status_logger": {
                        "period": 10,
                        "enabled": True,
                        "cumulative": True,
                        "aggregate_processes": True,
                        "targets": [{"prometheus": {"wrong": "key"}}],
                    }
                },
                RequiredConfigurationKeyMissingError,
            ),
            (
                "missing key in file target config",
                {
                    "status_logger": {
                        "period": 10,
                        "enabled": True,
                        "cumulative": True,
                        "aggregate_processes": True,
                        "targets": [
                            {
                                "file": {
                                    "rollover_interval": 86400,
                                    "backup_count": 10,
                                }
                            },
                        ],
                    }
                },
                RequiredConfigurationKeyMissingError,
            ),
            (
                "valid configuration",
                {
                    "status_logger": {
                        "period": 10,
                        "enabled": True,
                        "cumulative": True,
                        "aggregate_processes": True,
                        "targets": [
                            {"prometheus": {"port": 8000}},
                            {"file": {}},
                        ],
                    }
                },
                RequiredConfigurationKeyMissingError,
            ),
        ],
    )
    def test_verify_status_logger(
        self, status_logger_config_dict, raised_error, test_case
    ):  # pylint: disable=unused-argument
        status_logger_config = deepcopy(self.config)
        status_logger_config.update(status_logger_config_dict)
        if raised_error is not None:
            try:
                status_logger_config._verify_status_logger()
            except InvalidConfigurationErrors as error:
                assert any(
                    (type(error) == raised_error for error in error.errors)
                ), f"No '{raised_error.__name__}' raised for test case '{test_case}'!"
        else:
            status_logger_config._verify_status_logger()
