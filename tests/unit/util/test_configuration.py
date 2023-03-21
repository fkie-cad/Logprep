# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
import os
import re
from copy import deepcopy
from logging import getLogger
from pathlib import Path
from unittest import mock

import pytest

from logprep.util.configuration import (
    InvalidConfigurationError,
    Configuration,
    IncalidMetricsConfigurationError,
    RequiredConfigurationKeyMissingError,
    InvalidConfigurationErrors,
    InvalidProcessorConfigurationError,
    InvalidInputConnectorConfigurationError,
    InvalidOutputConnectorConfigurationError,
)
from logprep.util.getter import GetterFactory
from logprep.util.json_handling import dump_config_as_file
from tests.testdata.metadata import path_to_config

logger = getLogger()


class TestConfiguration:
    config: dict

    def setup_method(self):
        self.config = Configuration.create_from_yaml(path_to_config)

    def teardown_method(self):
        if "LOGPREP_VERSION" in os.environ:
            os.environ.pop("LOGPREP_VERSION")
        if "LOGPREP_PROCESS_COUNT" in os.environ:
            os.environ.pop("LOGPREP_PROCESS_COUNT")
        if "LOGPREP_LOG_LEVEL" in os.environ:
            os.environ.pop("LOGPREP_LOG_LEVEL")
        if "LOGPREP_PIPELINE" in os.environ:
            os.environ.pop("LOGPREP_PIPELINE")
        if "LOGPREP_OUTPUT" in os.environ:
            os.environ.pop("LOGPREP_OUTPUT")
        if "LOGPREP_INPUT" in os.environ:
            os.environ.pop("LOGPREP_INPUT")

    def assert_fails_when_replacing_key_with_value(self, key, value, expected_message):
        config = Configuration.create_from_yaml(path_to_config)

        parent = config
        if not isinstance(key, str):
            key = list(key)
            while len(key) > 1:
                parent = parent[key.pop(0)]
            key = key[0]
        parent[key] = value

        with pytest.raises(InvalidConfigurationError, match=expected_message):
            config.verify(logger)

    @mock.patch("logprep.util.configuration.print_fcolor")
    def test_invalid_yml_prints_formatted_error(self, mock_print_fcolor, tmp_path):
        broken_config_path = Path(tmp_path / "test_config")
        broken_config_path.write_text("process_count: 5\ninvalid_yaml", encoding="utf8")
        with pytest.raises(SystemExit, match="1"):
            Configuration.create_from_yaml(str(broken_config_path))
        mock_print_fcolor.assert_called()
        call_msg = str(mock_print_fcolor.call_args_list[0][0][1])
        assert call_msg.startswith("Error parsing YAML file")

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

    def test_verify_verifies_input_config(self):
        self.assert_fails_when_replacing_key_with_value(
            "input",
            {"random_name": {"type": "unknown"}},
            "Invalid input connector configuration: Unknown type 'unknown'",
        )

    def test_verify_verifies_output_config(self):
        self.assert_fails_when_replacing_key_with_value(
            "output",
            {"random_name": {"type": "unknown"}},
            "Invalid output connector configuration: Unknown type 'unknown'",
        )

    @pytest.mark.parametrize(
        "test_case, metrics_config_dict, raised_error",
        [
            (
                "valid configuration",
                {
                    "metrics": {
                        "period": 10,
                        "enabled": True,
                        "cumulative": True,
                        "aggregate_processes": True,
                        "measure_time": {"enabled": True, "append_to_event": False},
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
                    "metrics": {
                        "enabled": True,
                        "cumulative": True,
                        "aggregate_processes": True,
                        "measure_time": {"enabled": True, "append_to_event": False},
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
                    "metrics": {
                        "period": 10,
                        "enabled": True,
                        "cumulative": True,
                        "aggregate_processes": True,
                        "measure_time": {"enabled": True, "append_to_event": False},
                        "targets": [],
                    }
                },
                IncalidMetricsConfigurationError,
            ),
            (
                "unkown target",
                {
                    "metrics": {
                        "period": 10,
                        "enabled": True,
                        "cumulative": True,
                        "aggregate_processes": True,
                        "measure_time": {"enabled": True, "append_to_event": False},
                        "targets": [{"webserver": {"does-not": "exist"}}],
                    }
                },
                IncalidMetricsConfigurationError,
            ),
            (
                "missing key in prometheus target config",
                {
                    "metrics": {
                        "period": 10,
                        "enabled": True,
                        "cumulative": True,
                        "aggregate_processes": True,
                        "measure_time": {"enabled": True, "append_to_event": False},
                        "targets": [{"prometheus": {"wrong": "key"}}],
                    }
                },
                RequiredConfigurationKeyMissingError,
            ),
            (
                "missing key in file target config",
                {
                    "metrics": {
                        "period": 10,
                        "enabled": True,
                        "cumulative": True,
                        "aggregate_processes": True,
                        "measure_time": {"enabled": True, "append_to_event": False},
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
                    "metrics": {
                        "period": 10,
                        "enabled": True,
                        "cumulative": True,
                        "aggregate_processes": True,
                        "measure_time": {"enabled": True, "append_to_event": False},
                        "targets": [
                            {"prometheus": {"port": 8000}},
                            {"file": {}},
                        ],
                    }
                },
                RequiredConfigurationKeyMissingError,
            ),
            (
                "measure_time enabled key is missing",
                {
                    "metrics": {
                        "period": 10,
                        "enabled": True,
                        "cumulative": True,
                        "aggregate_processes": True,
                        "measure_time": {"append_to_event": False},
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
        ],
    )
    def test_verify_metrics_config(
        self, metrics_config_dict, raised_error, test_case
    ):  # pylint: disable=unused-argument
        metrics_config = deepcopy(self.config)
        metrics_config.update(metrics_config_dict)
        if raised_error is not None:
            try:
                metrics_config._verify_metrics_config()
            except InvalidConfigurationErrors as error:
                assert any(
                    (isinstance(error, raised_error) for error in error.errors)
                ), f"No '{raised_error.__name__}' raised for test case '{test_case}'!"
        else:
            metrics_config._verify_metrics_config()

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
                        "Invalid processor configuration: some_processor_name - Unknown type 'does_not_exist'",
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
                        re.escape(
                            "Invalid processor configuration: labelername - Required option(s) are "
                            + "missing: 'generic_rules'."
                        ),
                    )
                ],
            ),
            (
                "unknown option without spaces in processor",
                {
                    "pipeline": [
                        {
                            "labelername": {
                                "type": "labeler",
                                "schema": "quickstart/exampledata/rules/labeler/schema.json",
                                "include_parent_labels": "on",
                                "specific_rules": ["quickstart/exampledata/rules/labeler/specific"],
                                "generic_rules": ["quickstart/exampledata/rules/labeler/generic"],
                                "some_unknown_option": "foo",
                            }
                        }
                    ]
                },
                [
                    (
                        InvalidProcessorConfigurationError,
                        "Invalid processor configuration: labelername - Unknown option: 'some_unknown_option'.",
                    )
                ],
            ),
            (
                "unknown option with spaces in processor",
                {
                    "pipeline": [
                        {
                            "labelername": {
                                "type": "labeler",
                                "schema": "quickstart/exampledata/rules/labeler/schema.json",
                                "include_parent_labels": "on",
                                "specific_rules": ["quickstart/exampledata/rules/labeler/specific"],
                                "generic_rules": ["quickstart/exampledata/rules/labeler/generic"],
                                "some unknown option": "foo",
                            }
                        }
                    ]
                },
                [
                    (
                        InvalidProcessorConfigurationError,
                        "Invalid processor configuration: labelername - Unknown option: 'some unknown option'.",
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
                        "Invalid processor configuration: some_processor_name - Unknown type 'does_not_exist'",
                    ),
                    (
                        InvalidProcessorConfigurationError,
                        "Invalid processor configuration: another_processor_name - Unknown type 'does_not_exist'",
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
            (
                "pipeline is empty list",
                {"pipeline": []},
                [
                    (
                        InvalidConfigurationError,
                        'Invalid Configuration: "pipeline" must contain at least one item!',
                    )
                ],
            ),
            (
                "pipeline is empty dict",
                {"pipeline": {}},
                [
                    (
                        InvalidConfigurationError,
                        'Invalid Configuration: "pipeline" must contain at least one item!',
                    )
                ],
            ),
            (
                "pipeline is string",
                {"pipeline": "foo"},
                [
                    (
                        InvalidConfigurationError,
                        '"pipeline" must be a list of processor dictionary configurations!',
                    )
                ],
            ),
            (
                "processor error for config and output does not exists",
                {
                    "output": {},
                    "pipeline": [
                        {
                            "labelername": {
                                "type": "labeler",
                                "schema": "quickstart/exampledata/rules/labeler/schema.json",
                                "include_parent_labels": "on",
                                "specific_rules": ["quickstart/exampledata/rules/labeler/specific"],
                                "generic_rules": ["quickstart/exampledata/rules/labeler/generic"],
                                "some unknown option": "foo",
                            }
                        },
                        {
                            "pseudo": {
                                "type": "pseudonymizer",
                                "outputs": [{"kafka": "topic"}],
                                "pubkey_analyst": "tests/testdata/unit/pseudonymizer/example_analyst_pub.pem",
                                "pubkey_depseudo": "tests/testdata/unit/pseudonymizer/example_depseudo_pub.pem",
                                "hash_salt": "a_secret_tasty_ingredient",
                                "specific_rules": [
                                    "tests/testdata/unit/pseudonymizer/rules/specific/"
                                ],
                                "generic_rules": [
                                    "tests/testdata/unit/pseudonymizer/rules/generic/"
                                ],
                                "regex_mapping": "tests/testdata/unit/pseudonymizer/rules/regex_mapping.yml",
                                "max_cached_pseudonyms": 1000000,
                                "max_caching_days": 1,
                            }
                        },
                    ],
                },
                [
                    (
                        InvalidProcessorConfigurationError,
                        "Invalid processor configuration: labelername - Unknown option: 'some unknown option'.",
                    ),
                    (
                        InvalidProcessorConfigurationError,
                        "Invalid processor configuration: pseudo: output 'kafka' does not exist in logprep outputs",
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
            assert len(raised_errors) == len(errors_set), test_case
            zipped_errors = zip(raised_errors, errors_set)
            for expected_error, raised_error in zipped_errors:
                assert expected_error[0] == raised_error[0], "error class differ"
                assert re.search(expected_error[1], raised_error[1]), "error message differ"

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
                        "Invalid processor configuration: some_processor_name - Unknown type 'does_not_exist'",
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
                        re.escape(
                            "Invalid processor configuration: labelername - Required option(s) are "
                            + "missing: 'generic_rules'."
                        ),
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
                        "Invalid processor configuration: some_processor_name - Unknown type 'does_not_exist'",
                    ),
                    (
                        InvalidProcessorConfigurationError,
                        "Invalid processor configuration: another_processor_name - Unknown type 'does_not_exist'",
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
                        "Invalid processor configuration: some_processor_name - The type specification is missing for element with name 'some_processor_name'",
                    ),
                ],
            ),
            (
                "metrics configured without errors",
                {
                    "metrics": {
                        "period": 10,
                        "enabled": True,
                        "cumulative": True,
                        "aggregate_processes": True,
                        "measure_time": {"enabled": True, "append_to_event": False},
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
                [],
            ),
            (
                "measure_time enabled key is missing",
                {
                    "metrics": {
                        "period": 10,
                        "enabled": True,
                        "cumulative": True,
                        "aggregate_processes": True,
                        "measure_time": {"append_to_event": False},
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
                [
                    (
                        RequiredConfigurationKeyMissingError,
                        "Required option is missing: The following option keys for the measure time configs are missing: {'enabled'}",
                    )
                ],
            ),
        ],
    )
    def test_verify_errors_get_collected(self, config_dict, raised_errors, test_case):
        config = deepcopy(self.config)
        config.update(config_dict)
        if raised_errors is not None:
            errors = config._check_for_errors(logger)
            collected_errors = []
            for error in errors:
                collected_errors += error.errors
            errors_set = [(type(error), str(error)) for error in collected_errors]
            assert len(raised_errors) == len(errors_set), test_case
            zipped_errors = zip(raised_errors, errors_set)
            for expected_error, raised_error in zipped_errors:
                assert expected_error[0] == raised_error[0], "error class differ"
                assert re.search(expected_error[1], raised_error[1]), "error message differ"
        else:
            config._verify_metrics_config()

    def test_verify_input_raises_missing_input_key(self):
        config = deepcopy(self.config)
        del config["input"]
        with pytest.raises(
            RequiredConfigurationKeyMissingError, match="Required option is missing: input"
        ):
            config._verify_input(logger)

    def test_verify_input_raises_type_error(self):
        config = deepcopy(self.config)
        del config["input"]["kafka_input"]["bootstrapservers"]
        with pytest.raises(
            InvalidInputConnectorConfigurationError,
            match=re.escape(
                "Invalid input connector configuration: Required option(s) are missing: "
                + "'bootstrapservers'."
            ),
        ):
            config._verify_input(logger)

    def test_verify_output_raises_missing_output_key(self):
        config = deepcopy(self.config)
        del config["output"]
        with pytest.raises(
            RequiredConfigurationKeyMissingError, match="Required option is missing: output"
        ):
            config._verify_output(logger)

    def test_verify_output_raises_type_error(self):
        config = deepcopy(self.config)
        del config["output"]["kafka_output"]["bootstrapservers"]
        with pytest.raises(
            InvalidOutputConnectorConfigurationError,
            match=re.escape(
                "Invalid output connector configuration: Required option(s) are missing: "
                + "'bootstrapservers'."
            ),
        ):
            config._verify_output(logger)

    def test_patch_yaml_with_json_connectors_inserts_json_input_connector(self, tmp_path):
        regular_config = GetterFactory.from_string(path_to_config).get_yaml()
        assert (
            regular_config.get("input", {}).get("kafka_input", {}).get("type")
            == "confluentkafka_input"
        )
        patched_config_path = Configuration.patch_yaml_with_json_connectors(
            path_to_config, str(tmp_path)
        )
        patched_config = GetterFactory.from_string(patched_config_path).get_yaml()
        assert patched_config.get("input", {}).get("patched_input", {}).get("type") == "json_input"

    def test_patch_yaml_with_json_connectors_inserts_jsonl_input_connector(self, tmp_path):
        regular_config = GetterFactory.from_string(path_to_config).get_yaml()
        assert (
            regular_config.get("input", {}).get("kafka_input", {}).get("type")
            == "confluentkafka_input"
        )
        input_file_path = tmp_path / "test.jsonl"
        patched_config_path = Configuration.patch_yaml_with_json_connectors(
            path_to_config, str(tmp_path), str(input_file_path)
        )
        patched_config = GetterFactory.from_string(patched_config_path).get_yaml()
        assert patched_config.get("input", {}).get("patched_input", {}).get("type") == "jsonl_input"

    def test_patch_yaml_with_json_connectors_keeps_preprocessors(self, tmp_path):
        regular_config = GetterFactory.from_string(path_to_config).get_yaml()
        regular_config["input"]["kafka_input"]["preprocessing"] = {
            "log_arrival_time_target_field": "foo"
        }
        test_config_path = str(tmp_path / "test_config.yaml")
        dump_config_as_file(test_config_path, regular_config)
        patched_config_path = Configuration.patch_yaml_with_json_connectors(
            test_config_path, str(tmp_path)
        )
        patched_config = GetterFactory.from_string(patched_config_path).get_yaml()
        assert patched_config.get("input", {}).get("patched_input", {}).get("preprocessing") == {
            "log_arrival_time_target_field": "foo"
        }

    def test_patch_yaml_with_json_connectors_inserts_jsonl_output_connector(self, tmp_path):
        regular_config = GetterFactory.from_string(path_to_config).get_yaml()
        assert (
            regular_config.get("output", {}).get("kafka_output", {}).get("type")
            == "confluentkafka_output"
        )
        patched_config_path = Configuration.patch_yaml_with_json_connectors(
            path_to_config, str(tmp_path)
        )
        patched_config = GetterFactory.from_string(patched_config_path).get_yaml()
        assert (
            patched_config.get("output", {}).get("patched_output", {}).get("type") == "jsonl_output"
        )

    def test_patch_yaml_with_json_connectors_set_process_count_to_one(self, tmp_path):
        regular_config = GetterFactory.from_string(path_to_config).get_yaml()
        assert regular_config.get("process_count") == 3
        patched_config_path = Configuration.patch_yaml_with_json_connectors(
            path_to_config, str(tmp_path)
        )
        patched_config = GetterFactory.from_string(patched_config_path).get_yaml()
        assert patched_config.get("process_count") == 1

    def test_patch_yaml_with_json_connectors_drops_metrics_config(self, tmp_path):
        regular_config = GetterFactory.from_string(path_to_config).get_yaml()
        regular_config["metrics"] = {"enabled": "true"}
        test_config_path = str(tmp_path / "test_config.yaml")
        dump_config_as_file(test_config_path, regular_config)
        patched_config_path = Configuration.patch_yaml_with_json_connectors(
            test_config_path, str(tmp_path)
        )
        patched_config = GetterFactory.from_string(patched_config_path).get_yaml()
        assert patched_config.get("metrics") is None

    def test_config_gets_enriched_by_environment(self, tmp_path):
        config_path = tmp_path / "pipeline.yml"
        config_path.write_text(
            """
version: $LOGPREP_VERSION
process_count: $LOGPREP_PROCESS_COUNT
timeout: 0.1
logger:
    level: $LOGPREP_LOG_LEVEL
$LOGPREP_PIPELINE
$LOGPREP_INPUT
$LOGPREP_OUTPUT
"""
        )
        os.environ["LOGPREP_VERSION"] = "1"
        os.environ["LOGPREP_PROCESS_COUNT"] = "1"
        os.environ["LOGPREP_LOG_LEVEL"] = "DEBUG"
        os.environ[
            "LOGPREP_PIPELINE"
        ] = """
pipeline:
    - labelername:
        type: labeler
        schema: quickstart/exampledata/rules/labeler/schema.json
        include_parent_labels: true
        specific_rules:
            - quickstart/exampledata/rules/labeler/specific
        generic_rules:
            - quickstart/exampledata/rules/labeler/generic
"""
        os.environ[
            "LOGPREP_OUTPUT"
        ] = """
output:
    kafka:
        type: confluentkafka_output
        bootstrapservers:
        - 172.21.0.5:9092
        topic: producer
        error_topic: producer_error
        ack_policy: all
        compression: none
        maximum_backlog: 10000
        linger_duration: 0
        flush_timeout: 30
        send_timeout: 2
        ssl:
            cafile:
            certfile:
            keyfile:
            password:
"""
        os.environ[
            "LOGPREP_INPUT"
        ] = "input:\n    kafka:\n        type: confluentkafka_input\n        bootstrapservers:\n        - 172.21.0.5:9092\n        topic: consumer\n        group: cgroup3\n        auto_commit: true\n        session_timeout: 6000\n        offset_reset_policy: smallest\n        ssl:\n            cafile:\n            certfile:\n            keyfile:\n            password:\n            "
        config = Configuration.create_from_yaml(str(config_path))
        config.verify(mock.MagicMock())

    def test_config_gets_enriched_by_environment_with_non_existent_variable(self, tmp_path):
        config_path = tmp_path / "pipeline.yml"
        config_path.write_text(
            """
version: $LOGPREP_VERSION
process_count: $LOGPREP_PROCESS_COUNT
timeout: 0.1
logger:
    level: $LOGPREP_LOG_LEVEL
$LOGPREP_I_DO_NOT_EXIST
$LOGPREP_PIPELINE
$LOGPREP_INPUT
$LOGPREP_OUTPUT
"""
        )
        os.environ["LOGPREP_VERSION"] = "1"
        os.environ["LOGPREP_PROCESS_COUNT"] = "1"
        os.environ["LOGPREP_LOG_LEVEL"] = "DEBUG"
        os.environ[
            "LOGPREP_PIPELINE"
        ] = """
pipeline:
    - labelername:
        type: labeler
        schema: quickstart/exampledata/rules/labeler/schema.json
        include_parent_labels: true
        specific_rules:
            - quickstart/exampledata/rules/labeler/specific
        generic_rules:
            - quickstart/exampledata/rules/labeler/generic
"""
        os.environ[
            "LOGPREP_OUTPUT"
        ] = """
output:
    kafka:
        type: confluentkafka_output
        bootstrapservers:
        - 172.21.0.5:9092
        topic: producer
        error_topic: producer_error
        ack_policy: all
        compression: none
        maximum_backlog: 10000
        linger_duration: 0
        flush_timeout: 30
        send_timeout: 2
        ssl:
            cafile:
            certfile:
            keyfile:
            password:
"""
        os.environ[
            "LOGPREP_INPUT"
        ] = "input:\n    kafka:\n        type: confluentkafka_input\n        bootstrapservers:\n        - 172.21.0.5:9092\n        topic: consumer\n        group: cgroup3\n        auto_commit: true\n        session_timeout: 6000\n        offset_reset_policy: smallest\n        ssl:\n            cafile:\n            certfile:\n            keyfile:\n            password:\n            "
        config = Configuration.create_from_yaml(str(config_path))
        with pytest.raises(
            InvalidConfigurationErrors,
            match=r"Environment variable\(s\) used, but not set: LOGPREP_I_DO_NOT_EXIST",
        ):
            config.verify(mock.MagicMock())

    def test_verifies_processor_configs_against_defined_outputs(self):
        config = Configuration()
        pipeline = [
            {
                "se": {
                    "type": "selective_extractor",
                    "specific_rules": ["tests/testdata/unit/selective_extractor/rules/specific"],
                    "generic_rules": ["tests/testdata/unit/selective_extractor/rules/generic"],
                }
            },
            {
                "pd": {
                    "type": "pre_detector",
                    "generic_rules": ["tests/testdata/unit/pre_detector/rules/generic"],
                    "specific_rules": ["tests/testdata/unit/pre_detector/rules/specific"],
                    "outputs": [{"kafka": "pre_detector_alerts"}],
                    "alert_ip_list_path": "tests/testdata/unit/pre_detector/alert_ips.yml",
                }
            },
            {
                "pseudo": {
                    "type": "pseudonymizer",
                    "outputs": [{"kafka": "topic"}],
                    "pubkey_analyst": "tests/testdata/unit/pseudonymizer/example_analyst_pub.pem",
                    "pubkey_depseudo": "tests/testdata/unit/pseudonymizer/example_depseudo_pub.pem",
                    "hash_salt": "a_secret_tasty_ingredient",
                    "specific_rules": ["tests/testdata/unit/pseudonymizer/rules/specific/"],
                    "generic_rules": ["tests/testdata/unit/pseudonymizer/rules/generic/"],
                    "regex_mapping": "tests/testdata/unit/pseudonymizer/rules/regex_mapping.yml",
                    "max_cached_pseudonyms": 1000000,
                    "max_caching_days": 1,
                }
            },
        ]
        config.update({"pipeline": pipeline, "output": {}})
        with pytest.raises(InvalidConfigurationErrors) as raised:
            config._verify_pipeline(logger=logger)
        assert len(raised.value.errors) == 3
        for error in raised.value.errors:
            assert "output 'kafka' does not exist in logprep outputs" in error.args[0]

    def test_verify_pipeline_without_processor_outputs_ignores_processor_output_errors(self):
        config = Configuration()
        pipeline = [
            {
                "pd": {
                    "type": "pre_detector",
                    "generic_rules": ["tests/testdata/unit/pre_detector/rules/generic"],
                    "specific_rules": ["tests/testdata/unit/pre_detector/rules/specific"],
                    "outputs": [{"kafka": "pre_detector_alerts"}],
                    "alert_ip_list_path": "tests/testdata/unit/pre_detector/alert_ips.yml",
                }
            },
        ]
        config.update({"pipeline": pipeline, "output": {}})
        try:
            config.verify_pipeline_without_processor_outputs(logger=logger)
        except InvalidConfigurationErrors as error:
            assert False, f"Shouldn't raise output does not exist error: '{error}'"
