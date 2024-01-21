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

from logprep.abc.getter import Getter
from logprep.util.configuration import (
    Configuration,
    InvalidConfigurationError,
    InvalidConfigurationErrors,
    InvalidInputConnectorConfigurationError,
    InvalidProcessorConfigurationError,
    NewConfiguration,
    RequiredConfigurationKeyMissingError,
)
from logprep.util.getter import FileGetter, GetterFactory
from logprep.util.json_handling import dump_config_as_file
from tests.testdata.metadata import path_to_config

logger = getLogger()


class TestNewConfiguration:
    @pytest.mark.parametrize(
        "attribute, attribute_type, default",
        [
            ("version", str, "undefined"),
            ("process_count", int, 1),
            ("timeout", float, 5.0),
            ("logger", dict, {"level": "INFO"}),
            ("pipeline", list, []),
            ("input", dict, {}),
            ("output", dict, {}),
            ("metrics", dict, {"enabled": False, "port": 8000}),
        ],
    )
    def test_configuration_init(self, attribute, attribute_type, default):
        config = NewConfiguration()
        assert isinstance(getattr(config, attribute), attribute_type)
        assert getattr(config, attribute) == default

    def test_create_from_source_creates_configuration(self):
        config = NewConfiguration._create_from_source(path_to_config)
        assert isinstance(config, NewConfiguration)

    def test_create_from_source_adds_getter(self):
        config = NewConfiguration._create_from_source(path_to_config)
        assert isinstance(config._getter, FileGetter)

    def test_create_from_sources_adds_configs(self):
        config = NewConfiguration.create_from_sources([path_to_config, path_to_config])
        assert isinstance(config, NewConfiguration)
        assert isinstance(config._configs, tuple)
        assert isinstance(config._configs[0], NewConfiguration)

    @pytest.mark.parametrize(
        "attribute, first_value, second_value",
        [
            ("version", "1", "2"),
            ("process_count", 1, 2),
            ("timeout", 1.0, 2.0),
            ("logger", {"level": "INFO"}, {"level": "DEBUG"}),
            ("input", {"foo": "bar"}, {"bar": "foo"}),
            ("output", {"foo": "bar"}, {"bar": "foo"}),
            ("metrics", {"enabled": False, "port": 8000}, {"enabled": True, "port": 9000}),
            ("metrics", {"enabled": False, "port": 8000}, {"enabled": True, "port": 9000}),
        ],
    )
    def test_get_last_value(self, attribute, first_value, second_value):
        first_config = {attribute: first_value}
        second_config = {attribute: second_value}
        config = NewConfiguration()
        config._configs = (NewConfiguration(**first_config), NewConfiguration(**second_config))
        assert getattr(config, attribute) == second_value

    @pytest.mark.parametrize(
        "attribute, value, expected_error, expected_message",
        [
            ("process_count", -1, ValueError, "must be >= 1"),
            ("pipeline", {}, TypeError, "must be <class 'list'>"),
            ("timeout", "foo", TypeError, "must be <class 'float'>"),
            ("timeout", -0.1, ValueError, "must be > 0"),
            (
                "output",
                {"dummy1": {"type": "dummy_output"}, "dummy2": {"type": "dummy_output"}},
                None,
                None,
            ),
        ],
    )
    def test_validation(self, attribute, value, expected_error, expected_message):
        if expected_error is None:
            NewConfiguration(**{attribute: value})
        else:
            with pytest.raises(expected_error, match=expected_message):
                NewConfiguration(**{attribute: value})

    def test_pipeline_property_is_merged_from_configs(self):
        first_config = {"pipeline": [{"foo": "bar"}]}
        second_config = {"pipeline": [{"bar": "foo"}]}
        config = NewConfiguration()
        config._configs = (NewConfiguration(**first_config), NewConfiguration(**second_config))
        assert config.pipeline == [{"foo": "bar"}, {"bar": "foo"}]

    def test_create_from_sources_collects_errors(self, tmp_path):
        first_config = """---
process_count: -1
"""
        second_config = """---
pipeline: "wrong_type"
"""
        first_file_path = Path(tmp_path / "first_config")
        first_file_path.write_text(first_config, encoding="utf8")
        second_file_path = Path(tmp_path / "second_config")
        second_file_path.write_text(second_config, encoding="utf8")
        with pytest.raises(InvalidConfigurationErrors) as raised:
            config = NewConfiguration.create_from_sources(
                [str(first_file_path), str(second_file_path)]
            )
            assert len(raised.value.errors) == 2
            assert isinstance(config, NewConfiguration)
            assert isinstance(config._configs, tuple)

    def test_verify_passes_for_valid_configuration(self):
        try:
            config = NewConfiguration.create_from_sources([path_to_config])
            config.verify()
        except InvalidConfigurationError as error:
            pytest.fail(f"The verification should pass for a valid configuration.: {error}")

    @pytest.mark.parametrize(
        "test_case, test_config, error_count",
        [
            (
                "str as processor definition",
                {"pipeline": [{"processor_name": "should be a dict"}]},
                1,
            ),
            (
                "unknown processor type",
                {"pipeline": [{"processor_name": {"type": "unknown"}}]},
                1,
            ),
            (
                "incomplete processor definition",
                {"pipeline": [{"processor_name": {"type": "labeler"}}]},
                1,
            ),
            (
                "failure in rule definition",
                {
                    "pipeline": [
                        {
                            "processor_name": {
                                "type": "dissector",
                                "specific_rules": [
                                    {
                                        "filter": "message",
                                        "dissector": {
                                            "mapping": {"message": "%{source} %{target}"}
                                        },
                                        "description": "do nothing rule for dissector",
                                    }
                                ],
                                "generic_rules": [
                                    {
                                        "filter": "message",
                                        "dissector": "THIS SHOULD BE A DICT",
                                        "description": "do nothing rule for dissector",
                                    }
                                ],
                            }
                        }
                    ]
                },
                1,
            ),
            (
                "collects multiple errors",
                {
                    "pipeline": [
                        {
                            "error_processor": "THIS SHOULD BE A DICT",
                        },
                        {
                            "processor_name": {
                                "type": "dissector",
                                "specific_rules": [
                                    {
                                        "filter": "message",
                                        "dissector": {
                                            "mapping": {"message": "%{source} %{target}"}
                                        },
                                        "description": "do nothing rule for dissector",
                                    }
                                ],
                                "generic_rules": [
                                    {
                                        "filter": "message",
                                        "dissector": "THIS SHOULD BE A DICT",
                                        "description": "do nothing rule for dissector",
                                    }
                                ],
                            },
                        },
                        {
                            "another_error_processor": {"type": "unknown"},
                        },
                    ]
                },
                3,
            ),
            ("verifies input config", {"input": {"random_name": {"type": "unknown"}}}, 1),
            ("verifies output config", {"output": {"kafka_output": {"type": "unknown"}}}, 1),
            (
                "multiple output config failures",
                {
                    "output": {
                        "dummy": {"type": "wrong_type"},
                        "kafka_output": {"type": "dummy_output"},
                    },
                },
                1,
            ),
            (
                "multiple output configs success",
                {
                    "output": {
                        "dummy": {"type": "dummy_output"},
                        "kafka_output": {"type": "dummy_output"},
                    }
                },
                0,
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
                1,
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
                1,
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
                1,
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
                1,
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
                2,
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
                            }
                        },
                    ],
                },
                2,
            ),
        ],
    )
    def test_verify_verifies_config(self, tmp_path, test_case, test_config, error_count):
        test_config_path = str(tmp_path / "failure-config.yml")
        dump_config_as_file(test_config_path, test_config)
        config = NewConfiguration.create_from_sources([path_to_config, test_config_path])
        if error_count:
            with pytest.raises(InvalidConfigurationErrors) as raised:
                config.verify()
            assert len(raised.value.errors) == error_count, test_case
        else:
            config.verify()

    patch = mock.patch(
        "os.environ",
        {
            "LOGPREP_VERSION": "1",
            "LOGPREP_PROCESS_COUNT": "16",
            "LOGPREP_LOG_LEVEL": "DEBUG",
            "LOGPREP_PIPELINE": """
pipeline:
    - labelername:
        type: labeler
        schema: quickstart/exampledata/rules/labeler/schema.json
        include_parent_labels: true
        specific_rules:
            - quickstart/exampledata/rules/labeler/specific
        generic_rules:
            - quickstart/exampledata/rules/labeler/generic
""",
            "LOGPREP_OUTPUT": """
output:
    kafka:
        type: confluentkafka_output
        topic: producer
        error_topic: producer_error
        flush_timeout: 30
        send_timeout: 2
        kafka_config:
            bootstrap.servers: "172.21.0.5:9092"
            acks: "-1"
            compression.type: "none"
""",
            "LOGPREP_INPUT": "input:\n    kafka:\n        type: confluentkafka_input\n        topic: consumer\n        kafka_config:\n          bootstrap.servers: localhost:9092\n          group.id: testgroup\n",
        },
    )

    @patch
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
        config = NewConfiguration.create_from_sources([str(config_path)])
        config.verify()
        assert config.version == "1"
        assert config.process_count == 16
        assert config.output["kafka"]["topic"] == "producer"
        assert config.input["kafka"]["topic"] == "consumer"
        assert len(config.pipeline) == 1

    @patch
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
        config = NewConfiguration.create_from_sources([str(config_path)])
        with pytest.raises(
            InvalidConfigurationErrors,
            match=r"Environment variable\(s\) used, but not set: LOGPREP_I_DO_NOT_EXIST",
        ):
            config.verify()


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
        except InvalidConfigurationError as error:
            pytest.fail(f"The verification should pass for a valid configuration.: {error}")

    def test_verify_pipeline_only_passes_for_valid_configuration(self):
        try:
            self.config.verify_pipeline_only(logger)
        except InvalidConfigurationError:
            pytest.fail("The verification should pass for a valid configuration.")

    def test_verify_fails_on_missing_required_value(self):
        not_required_keys = ["version"]
        for key in list(self.config.keys()):
            if key in not_required_keys:
                continue
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
                {"metrics": {"enabled": True, "port": 8000}},
                None,
            ),
            (
                "invalid datatype in port",
                {"metrics": {"enabled": True, "port": "8000"}},
                None,
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
                        "port": 8000,
                    }
                },
                [],
            ),
            (
                "metrics enabled",
                {
                    "metrics": {
                        "port": 8000,
                    }
                },
                [
                    (
                        RequiredConfigurationKeyMissingError,
                        "Required option is missing: metrics > enabled",
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
        del config["input"]["kafka_input"]["topic"]
        with pytest.raises(
            InvalidInputConnectorConfigurationError,
            match=re.escape(
                "Invalid input connector configuration: Required option(s) are missing: "
                + "'topic'."
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
        topic: producer
        error_topic: producer_error
        flush_timeout: 30
        send_timeout: 2
        kafka_config:
            bootstrap.servers: "172.21.0.5:9092"
            acks: "-1"
            compression.type: "none"
"""
        os.environ[
            "LOGPREP_INPUT"
        ] = "input:\n    kafka:\n        type: confluentkafka_input\n        topic: consumer\n        kafka_config:\n          bootstrap.servers: localhost:9092\n          group.id: testgroup\n"
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
        topic: producer
        error_topic: producer_error
        flush_timeout: 30
        send_timeout: 2
        kafka_config:
            bootstrap.servers: "172.21.0.5:9092"
            acks: "-1"
            compression.type: "none"
"""
        os.environ[
            "LOGPREP_INPUT"
        ] = "input:\n    kafka:\n        type: confluentkafka_input\n        topic: consumer\n"
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

    def test_duplicate_rule_id_per_processor_raises(self):
        config = Configuration()
        pipeline = [
            {
                "my dissector": {
                    "type": "dissector",
                    "specific_rules": [
                        {
                            "filter": "message",
                            "dissector": {
                                "id": "same id",
                                "mapping": {"message": "%{new_field} %{next_field}"},
                            },
                        },
                        {
                            "filter": "message",
                            "dissector": {
                                "id": "same id",
                                "mapping": {"message": "%{other_field} %{next_field}"},
                            },
                        },
                    ],
                    "generic_rules": [],
                }
            },
        ]
        config.update({"pipeline": pipeline, "output": {}})
        with pytest.raises(InvalidConfigurationErrors) as raised:
            config._verify_pipeline(logger=logger)
        assert len(raised.value.errors) == 1
        for error in raised.value.errors:
            assert "Duplicate rule id: same id" in error.args[0]

    def test_duplicate_rule_id_in_different_rule_trees_per_processor_raises(self):
        config = Configuration()
        pipeline = [
            {
                "my dissector": {
                    "type": "dissector",
                    "specific_rules": [
                        {
                            "filter": "message",
                            "dissector": {
                                "id": "same id",
                                "mapping": {"message": "%{new_field} %{next_field}"},
                            },
                        },
                    ],
                    "generic_rules": [
                        {
                            "filter": "message",
                            "dissector": {
                                "id": "same id",
                                "mapping": {"message": "%{other_field} %{next_field}"},
                            },
                        },
                    ],
                }
            },
        ]
        config.update({"pipeline": pipeline, "output": {}})
        with pytest.raises(InvalidConfigurationErrors) as raised:
            config._verify_pipeline(logger=logger)
        assert len(raised.value.errors) == 1
        for error in raised.value.errors:
            assert "Duplicate rule id: same id" in error.args[0]
