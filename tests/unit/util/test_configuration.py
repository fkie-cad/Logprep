# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long

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
    InvalidProcessorConfigurationError,
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

    def test_verify_pipeline_only_passes_for_valid_configuration(self):
        try:
            self.config.verify_pipeline_only(logger)
        except InvalidConfigurationError:
            pytest.fail("The verification should pass for a valid configuration.")

    def test_verify_fails_on_missing_required_value(self):
        for key in list(self.config.keys()):
            config = deepcopy(self.config)
            del config[key]

            with pytest.raises(InvalidConfigurationError):
                config.verify(logger)

    def test_verify_pipeline_only_fails_on_missing_pipeline_value(self):
        for key in list(key for key in self.config.keys() if key != "pipeline"):
            config = deepcopy(self.config)
            del config[key]
            config.verify_pipeline_only(logger)

        config = deepcopy(self.config)
        del config["pipeline"]
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
                    (isinstance(error, raised_error) for error in error.errors)
                ), f"No '{raised_error.__name__}' raised for test case '{test_case}'!"
        else:
            status_logger_config._verify_status_logger()

    @pytest.mark.parametrize(
        "test_case, config_dict, raised_errors",
        [
            (
                "valid configuration",
                {},
                None,
            ),
            (
                "processor does not exist",
                {
                    "pipeline": [
                        {
                            "some_processor_name": {
                                "type": "does_not_exist",
                            }
                        }
                    ]
                },
                [
                    (
                        InvalidProcessorConfigurationError,
                        "Invalid processor config: Unknown processor type 'does_not_exist'",
                    )
                ],
            ),
            (
                "generic_rules missing from processor",
                {
                    "pipeline": [
                        {
                            "labelername": {
                                "type": "labeler",
                                "schema": "quickstart/exampledata/rules/labeler/schema.json",
                                "include_parent_labels": "on",
                                "specific_rules": ["quickstart/exampledata/rules/labeler/specific"],
                            }
                        }
                    ]
                },
                [
                    (
                        InvalidProcessorConfigurationError,
                        "Invalid processor config: __init__() missing 1 required keyword-only argument: 'generic_rules'",
                    )
                ],
            ),
            (
                "two processor do not exist",
                {
                    "pipeline": [
                        {
                            "some_processor_name": {
                                "type": "does_not_exist",
                            }
                        },
                        {"another_processor_name": {"type": "does_not_exist"}},
                    ]
                },
                [
                    (
                        InvalidProcessorConfigurationError,
                        "Invalid processor config: Unknown processor type 'does_not_exist'",
                    ),
                    (
                        InvalidProcessorConfigurationError,
                        "Invalid processor config: Unknown processor type 'does_not_exist'",
                    ),
                ],
            ),
            (
                "pipeline count invalid and processor type missing",
                {"process_count": 0, "pipeline": [{"some_processor_name": {}}]},
                [
                    (
                        InvalidConfigurationError,
                        "Invalid Configuration: Process count must be an integer of one or larger, not: 0",
                    ),
                ],
            ),
        ],
    )
    def test_verify_error(self, config_dict, raised_errors, test_case):
        config = deepcopy(self.config)
        config.update(config_dict)
        if raised_errors is not None:
            with pytest.raises(InvalidConfigurationErrors) as e_info:
                config.verify(logger)
            errors_set = [(type(err), str(err)) for err in e_info.value.errors]
            assert errors_set == raised_errors, f"For test case '{test_case}'!"

    @pytest.mark.parametrize(
        "test_case, config_dict, raised_errors",
        [
            (
                "valid configuration",
                {},
                None,
            ),
            (
                "processor does not exist",
                {
                    "pipeline": [
                        {
                            "some_processor_name": {
                                "type": "does_not_exist",
                            }
                        }
                    ]
                },
                [
                    (
                        InvalidProcessorConfigurationError,
                        "Invalid processor config: Unknown processor type 'does_not_exist'",
                    )
                ],
            ),
            (
                "generic_rules missing from processor",
                {
                    "pipeline": [
                        {
                            "labelername": {
                                "type": "labeler",
                                "schema": "quickstart/exampledata/rules/labeler/schema.json",
                                "include_parent_labels": "on",
                                "specific_rules": ["quickstart/exampledata/rules/labeler/specific"],
                            }
                        }
                    ]
                },
                [
                    (
                        InvalidProcessorConfigurationError,
                        "Invalid processor config: __init__() missing 1 required keyword-only argument: 'generic_rules'",
                    )
                ],
            ),
            (
                "two processors do not exist",
                {
                    "pipeline": [
                        {
                            "some_processor_name": {
                                "type": "does_not_exist",
                            }
                        },
                        {"another_processor_name": {"type": "does_not_exist"}},
                    ]
                },
                [
                    (
                        InvalidProcessorConfigurationError,
                        "Invalid processor config: Unknown processor type 'does_not_exist'",
                    ),
                    (
                        InvalidProcessorConfigurationError,
                        "Invalid processor config: Unknown processor type 'does_not_exist'",
                    ),
                ],
            ),
            (
                "pipeline count invalid and processor type missing",
                {"process_count": 0, "pipeline": [{"some_processor_name": {}}]},
                [
                    (
                        InvalidConfigurationError,
                        "Invalid Configuration: Process count must be an integer of one or larger, not: 0",
                    ),
                    (
                        InvalidProcessorConfigurationError,
                        "Invalid processor config: The processor type specification is missing for processor with name 'some_processor_name'",
                    ),
                ],
            ),
        ],
    )
    def test_verify_errors_get_collected(self, config_dict, raised_errors, test_case):
        config = deepcopy(self.config)
        config.update(config_dict)
        if raised_errors is not None:
            errors = config._perform_verfification_and_get_errors(logger)
            collected_errors = []
            for error in errors:
                collected_errors += error.errors
            errors_set = [(type(error), str(error)) for error in collected_errors]
            assert errors_set == raised_errors, f"For test case '{test_case}'!"
        else:
            config._verify_status_logger()
