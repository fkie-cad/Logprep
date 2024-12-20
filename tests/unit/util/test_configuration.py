# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
import json
import os
import uuid
from logging import getLogger
from pathlib import Path
from unittest import mock

import pytest
import responses
from attrs import asdict
from requests.exceptions import HTTPError
from ruamel.yaml.scanner import ScannerError

from logprep.util.configuration import (
    Configuration,
    InvalidConfigurationError,
    InvalidConfigurationErrors,
    LoggerConfig,
    MetricsConfig,
)
from logprep.util.defaults import ENV_NAME_LOGPREP_CREDENTIALS_FILE
from logprep.util.getter import FileGetter, GetterNotFoundError
from tests.testdata.metadata import (
    path_to_config,
    path_to_invalid_config,
    path_to_only_output_config,
)

in_ci = os.environ.get("GITHUB_ACTIONS") == "true"

logger = getLogger()


@pytest.fixture(name="config_path", scope="function")
def fixture_config_path(tmp_path: Path) -> Path:
    config_path = tmp_path / uuid.uuid4().hex
    configuration = Configuration.from_sources([path_to_config])
    config_path.write_text(configuration.as_yaml())
    return config_path


class TestConfiguration:
    @pytest.mark.parametrize(
        "attribute, attribute_type, default",
        [
            ("version", str, "unset"),
            ("config_refresh_interval", type(None), None),
            ("process_count", int, 1),
            ("timeout", float, 5.0),
            ("logger", LoggerConfig, LoggerConfig(**{"level": "INFO"})),
            ("pipeline", list, []),
            ("input", dict, {}),
            ("output", dict, {}),
            ("metrics", MetricsConfig, MetricsConfig(**{"enabled": False, "port": 8000})),
        ],
    )
    def test_configuration_init(self, attribute, attribute_type, default):
        config = Configuration()
        assert isinstance(getattr(config, attribute), attribute_type)
        assert getattr(config, attribute) == default

    def test_create_from_source_creates_configuration(self):
        config = Configuration.from_source(path_to_config)
        assert isinstance(config, Configuration)

    def test_create_from_source_adds_getter(self):
        config = Configuration.from_source(path_to_config)
        assert isinstance(config._getter, FileGetter)

    def test_create_from_sources_adds_configs(self):
        config = Configuration.from_sources([path_to_config, path_to_config])
        assert isinstance(config, Configuration)
        assert isinstance(config._configs, tuple)
        assert isinstance(config._configs[0], Configuration)

    @pytest.mark.parametrize(
        "attribute, first_value, second_value",
        [
            ("config_refresh_interval", 0, 900),
            ("process_count", 1, 2),
            ("timeout", 1.0, 2.0),
            (
                "metrics",
                {"enabled": False, "port": 8000, "uvicorn_config": {"access_log": True}},
                {"enabled": True, "port": 9000, "uvicorn_config": {"access_log": False}},
            ),
            (
                "metrics",
                {"enabled": False, "port": 8000},
                {"enabled": True, "port": 9000, "uvicorn_config": {}},
            ),
        ],
    )
    def test_get_last_value(self, tmp_path, attribute, first_value, second_value):
        first_config = tmp_path / "pipeline.yml"
        first_config.write_text(
            f"""
input:
    dummy:
        type: dummy_input
        documents: []
output:
    dummy:
        type: dummy_output
{attribute}: {first_value}
"""
        )
        second_config = tmp_path / "pipeline2.yml"
        second_config.write_text(
            f"""
input:
    dummy:
        type: dummy_input
        documents: []
output:
    dummy:
        type: dummy_output
{attribute}: {second_value}
"""
        )
        with mock.patch("os.environ", new={"PROMETHEUS_MULTIPROC_DIR": str(tmp_path)}):
            config = Configuration.from_sources([str(first_config), str(second_config)])
            attribute_from_test = getattr(config, attribute)
            if hasattr(attribute_from_test, "__attrs_attrs__"):
                assert asdict(attribute_from_test) == second_value
            else:
                assert attribute_from_test == second_value

    def test_get_last_value_logger_config(self, tmp_path):
        attribute = "logger"
        first_value = {"level": "INFO"}
        second_value = {"level": "DEBUG"}
        first_config = tmp_path / "pipeline.yml"
        first_config.write_text(
            f"""
input:
    dummy:
        type: dummy_input
        documents: []
output:
    dummy:
        type: dummy_output
{attribute}: {first_value}
"""
        )
        second_config = tmp_path / "pipeline2.yml"
        second_config.write_text(
            f"""
input:
    dummy:
        type: dummy_input
        documents: []
output:
    dummy:
        type: dummy_output
{attribute}: {second_value}
"""
        )
        config = Configuration.from_sources([str(first_config), str(second_config)])
        assert config.logger.level == "DEBUG"
        assert config.logger.loggers.get("root").get("level") == "DEBUG"

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
            Configuration(**{attribute: value})
        else:
            with pytest.raises(expected_error, match=expected_message):
                Configuration(**{attribute: value})

    def test_pipeline_property_is_merged_from_configs(self, tmp_path):
        first_config = tmp_path / "pipeline.yml"
        first_config.write_text(
            """
input:
    dummy:
        type: dummy_input
        documents: []
output:
    dummy:
        type: dummy_output
pipeline:
    - labelername:
        type: labeler
        schema: examples/exampledata/rules/labeler/schema.json
        include_parent_labels: true
        rules: []
"""
        )
        second_config = tmp_path / "pipeline2.yml"
        second_config.write_text(
            """
pipeline:
    - dissectorname:
        type: dissector
        rules: []
"""
        )
        config = Configuration.from_sources([str(first_config), str(second_config)])
        assert isinstance(config.pipeline, list)
        assert len(config.pipeline) == 2
        assert config.pipeline[0]["labelername"]["type"] == "labeler"
        assert config.pipeline[1]["dissectorname"]["type"] == "dissector"

    def test_create_from_sources_with_incomplete_second_config(self):
        config = Configuration.from_sources([path_to_config, path_to_only_output_config])
        assert config.output.get("kafka_output").get("type") == "dummy_output"

    def test_create_from_sources_collects_errors(self):
        with pytest.raises(InvalidConfigurationErrors) as raised:
            config = Configuration.from_sources([path_to_invalid_config, path_to_invalid_config])
            assert len(raised.value.errors) == 2
            assert isinstance(config, Configuration)
            assert isinstance(config._configs, tuple)

    def test_create_from_sources_loads_processors(self):
        config = Configuration.from_sources([path_to_config])
        labeler = config.pipeline[2]
        assert isinstance(labeler, dict)
        assert isinstance(labeler["labelername"], dict)
        assert isinstance(labeler["labelername"]["type"], str)
        assert labeler["labelername"]["type"] == "labeler"

    def test_create_from_sources_loads_rules(self):
        config = Configuration.from_sources([path_to_config])
        labeler = config.pipeline[2]
        assert isinstance(labeler, dict)
        assert isinstance(labeler["labelername"], dict)
        assert isinstance(labeler["labelername"]["rules"], list)
        assert isinstance(labeler["labelername"]["rules"][0], dict)

    def test_verify_passes_for_valid_configuration(self):
        try:
            Configuration.from_sources([path_to_config])
        except InvalidConfigurationError as error:
            pytest.fail(f"The verification should pass for a valid configuration.: {error}")

    @pytest.mark.parametrize(
        "test_case, test_config, error_count",
        [
            (
                "str as processor definition",
                {"pipeline": [{"processor_name": "SHOULD BE A DICT"}]},
                1,
            ),
            (
                "unknown processor type",
                {"pipeline": [{"processor_name": {"type": "UNKNOWN"}}]},
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
                                "rules": [
                                    {
                                        "filter": "message",
                                        "dissector": {
                                            "mapping": {"message": "%{source} %{target}"}
                                        },
                                        "description": "do nothing rule for dissector",
                                    },
                                    {
                                        "filter": "message",
                                        "dissector": "THIS SHOULD BE A DICT",
                                        "description": "do nothing rule for dissector",
                                    },
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
                                "rules": [
                                    {
                                        "filter": "message",
                                        "dissector": {
                                            "mapping": {"message": "%{source} %{target}"}
                                        },
                                        "description": "do nothing rule for dissector",
                                    },
                                    {
                                        "filter": "message",
                                        "dissector": "THIS SHOULD BE A DICT",
                                        "description": "do nothing rule for dissector",
                                    },
                                ],
                            },
                        },
                        {
                            "another_error_processor": {"type": "UNKNOWN"},
                        },
                    ]
                },
                3,
            ),
            ("verifies input config", {"input": {"random_name": {"type": "UNKNOWN"}}}, 1),
            ("verifies output config", {"output": {"kafka_output": {"type": "UNKNOWN"}}}, 1),
            (
                "multiple outputs but one config failure",
                {
                    "output": {
                        "dummy": {"type": "WRONG_TYPE"},
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
                                "type": "DOES_NOT_EXIST",
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
                                "schema": "examples/exampledata/rules/labeler/schema.json",
                                "include_parent_labels": "on",
                                "rules": ["examples/exampledata/rules/labeler/rules"],
                                "SOME_UNKNOWN_OPTION": "FOO",
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
                                "schema": "examples/exampledata/rules/labeler/schema.json",
                                "include_parent_labels": "on",
                                "rules": ["examples/exampledata/rules/labeler/rules"],
                                "SOME UNKNOWN OPTION": "FOO",
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
                                "type": "DOES_NOT_EXIST",
                            }
                        },
                        {"another_processor_name": {"type": "DOES_NOT_EXIST"}},
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
                                "schema": "examples/exampledata/rules/labeler/schema.json",
                                "include_parent_labels": "on",
                                "rules": ["examples/exampledata/rules/labeler/rules"],
                                "SOME UNKNOWN OPTION": "FOO",
                            }
                        },
                        {
                            "pseudo": {
                                "type": "pseudonymizer",
                                "outputs": [{"KAFKA": "topic"}],
                                "pubkey_analyst": "tests/testdata/unit/pseudonymizer/example_analyst_pub.pem",
                                "pubkey_depseudo": "tests/testdata/unit/pseudonymizer/example_depseudo_pub.pem",
                                "hash_salt": "a_secret_tasty_ingredient",
                                "rules": ["tests/testdata/unit/pseudonymizer/rules"],
                                "regex_mapping": "tests/testdata/unit/pseudonymizer/rules/regex_mapping.yml",
                                "max_cached_pseudonyms": 1000000,
                            }
                        },
                    ],
                },
                3,
            ),
            (
                "rule with not existent output",
                {
                    "output": {"kafka_output": {"type": "dummy_output"}},
                    "pipeline": [
                        {
                            "selective_extractor": {
                                "type": "selective_extractor",
                                "rules": [
                                    {
                                        "filter": "message",
                                        "selective_extractor": {
                                            "outputs": [{"DOES_NOT_EXIST": "FOO"}]
                                        },
                                        "source_fields": ["field.extract", "field2", "field3"],
                                    }
                                ],
                            }
                        }
                    ],
                },
                1,
            ),
            (
                "error_output with unknown type",
                {
                    "error_output": {"kafka_output": {"type": "UNKNOWN"}},
                },
                1,
            ),
        ],
    )
    def test_verify_verifies_config(self, tmp_path, test_case, test_config, error_count):
        test_config_path = tmp_path / "failure-config.yml"
        test_config = Configuration(**test_config)
        if not test_config.input:
            test_config.input = {"dummy": {"type": "dummy_input", "documents": []}}
        if not test_config.output:
            test_config.output = {"dummy": {"type": "dummy_output"}}
        test_config_path.write_text(test_config.as_yaml())
        if error_count:
            with pytest.raises(InvalidConfigurationErrors) as raised:
                Configuration.from_sources([str(test_config_path)])
            assert len(raised.value.errors) == error_count, test_case
        else:
            Configuration.from_sources([str(test_config_path)])

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
        schema: examples/exampledata/rules/labeler/schema.json
        include_parent_labels: true
        rules:
            - examples/exampledata/rules/labeler/rules
""",
            "LOGPREP_OUTPUT": """
output:
    kafka:
        type: confluentkafka_output
        topic: producer
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
        config = Configuration.from_sources([str(config_path)])
        config._verify()
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
        with pytest.raises(
            InvalidConfigurationErrors,
            match=r"Environment variable\(s\) used, but not set: LOGPREP_I_DO_NOT_EXIST",
        ):
            Configuration.from_sources([str(config_path)])

    def test_duplicate_rule_id_per_processor_raises(self, tmp_path):
        config_path = tmp_path / "pipeline.yml"
        config_path.write_text(
            """
input:
    dummy:
        type: dummy_input
        documents: []
output:
    dummy:
        type: dummy_output
pipeline:
    - my dissector:
        type: dissector
        rules:
            - filter: message
              dissector:
                id: same id
                mapping:
                  message: "%{new_field} %{next_field}"
            - filter: message
              dissector:
                id: same id
                mapping:
                  message: "%{other_field} %{next_field}"
"""
        )
        with pytest.raises(InvalidConfigurationErrors) as raised:
            Configuration.from_sources([str(config_path)])
        assert len(raised.value.errors) == 1
        for error in raised.value.errors:
            assert "Duplicate rule id: same id" in error.args[0]

    def test_duplicate_rule_id_in_different_rule_trees_per_processor_raises(self, tmp_path):
        config_path = tmp_path / "pipeline.yml"
        config_path.write_text(
            """
input:
    dummy:
        type: dummy_input
        documents: []
output:
    dummy:
        type: dummy_output
pipeline:
    - my dissector:
        type: dissector
        rules:
            - filter: message
              dissector:
                id: same id
                mapping:
                  message: "%{new_field} %{next_field}"
            - filter: message
              dissector:
                id: same id
                mapping:
                  message: "%{other_field} %{next_field}"
"""
        )
        with pytest.raises(InvalidConfigurationErrors) as raised:
            Configuration.from_sources([str(config_path)])
        assert len(raised.value.errors) == 1
        for error in raised.value.errors:
            assert "Duplicate rule id: same id" in error.args[0]

    @pytest.mark.parametrize(
        "test_case, metrics_config_dict, raised_error",
        [
            (
                "valid configuration",
                {"enabled": True, "port": 8000},
                None,
            ),
            (
                "invalid datatype in port",
                {"enabled": True, "port": "8000"},
                TypeError,
            ),
            (
                "unknown option",
                {"enabled": True, "port": 8000, "UNKNOWN_OPTION": "FOO"},
                TypeError,
            ),
        ],
    )
    def test_verify_metrics_config(
        self, metrics_config_dict, raised_error, test_case
    ):  # pylint: disable=unused-argument
        if raised_error is None:
            _ = Configuration(**{"metrics": metrics_config_dict})
        else:
            with pytest.raises(raised_error):
                _ = Configuration(**{"metrics": metrics_config_dict})

    def test_reload_reloads_complete_config(self, tmp_path):
        config_path = tmp_path / "pipeline.yml"
        config_path.write_text(
            """
version: first_version
process_count: 2
timeout: 0.1
logger:
    level: DEBUG
input:
    dummy:
        type: dummy_input
        documents: []
output:
    dummy:
        type: dummy_output
"""
        )
        config = Configuration.from_sources([str(config_path)])
        assert config.version == "first_version"
        config_path.write_text(
            """
version: second_version
process_count: 2
timeout: 0.1
logger:
    level: DEBUG
input:
    dummy:
        type: dummy_input
        documents: []
output:
    dummy:
        type: dummy_output
"""
        )
        config.reload()
        assert config.version == "second_version"

    def test_reload_raises_on_invalid_config(self, tmp_path):
        config_path = tmp_path / "pipeline.yml"
        config_path.write_text(
            """
version: first_version
process_count: 2
timeout: 0.1
logger:
    level: DEBUG
input:
    dummy:
        type: dummy_input
        documents: []
output:
    dummy:
        type: dummy_output
"""
        )
        config = Configuration.from_sources([str(config_path)])
        assert config.version == "first_version"
        config_path.write_text(
            """
version: second_version
process_count: THIS SHOULD BE AN INT
timeout: 0.1
logger:
    level: DEBUG
input:
    dummy:
        type: dummy_input
        documents: []
output:
    dummy:
        type: dummy_output
"""
        )
        with pytest.raises(InvalidConfigurationError):
            config.reload()
        assert config.version == "first_version"

    def test_reload_raises_on_invalid_processor_config(self, tmp_path):
        config_path = tmp_path / "pipeline.yml"
        config_path.write_text(
            """
version: first_version
process_count: 2
timeout: 0.1
logger:
    level: DEBUG
pipeline:
    - labelername:
        type: labeler
        schema: examples/exampledata/rules/labeler/schema.json
        include_parent_labels: true
        rules: []
input:
    dummy:
        type: dummy_input
        documents: []
output:
    dummy:
        type: dummy_output
"""
        )
        config = Configuration.from_sources([str(config_path)])
        assert config.version == "first_version"
        config_path.write_text(
            """
version: second_version
process_count: 2
timeout: 0.1
logger:
    level: DEBUG
pipeline:
    - labelername:
        type: labeler
        schema: examples/exampledata/rules/labeler/schema.json
        include_parent_labels: true
        rules: []
    - new_processor:
        type: THIS SHOULD BE A VALID PROCESSOR
input:
    dummy:
        type: dummy_input
        documents: []
output:
    dummy:
        type: dummy_output
"""
        )
        with pytest.raises(InvalidConfigurationError):
            config.reload()
        assert config.version == "first_version"

    def test_reload_raises_on_same_version(self, tmp_path):
        config_path = tmp_path / "pipeline.yml"
        config_path.write_text(
            """
version: first_version
process_count: 2
timeout: 0.1
logger:
    level: DEBUG
input:
    dummy:
        type: dummy_input
        documents: []
output:
    dummy:
        type: dummy_output
"""
        )
        config = Configuration.from_sources([str(config_path)])
        assert config.version == "first_version"
        config_path.write_text(
            """
version: first_version
process_count: 2
timeout: 0.1
logger:
    level: DEBUG
pipeline:
    - labelername:
        type: labeler
        schema: examples/exampledata/rules/labeler/schema.json
        include_parent_labels: true
        rules: []
input:
    dummy:
        type: dummy_input
        documents: []
output:
    dummy:
        type: dummy_output
"""
        )
        with pytest.raises(InvalidConfigurationError, match="Configuration version didn't change."):
            config.reload()
        assert config.version == "first_version"

    def test_as_dict_returns_config(self):
        config = Configuration.from_sources([path_to_config, path_to_only_output_config])
        config_dict = config.as_dict()
        assert isinstance(config_dict, dict)
        assert config_dict["output"]["kafka_output"]["type"] == "dummy_output"
        assert len(config_dict["output"]) == 1, "only last output should be in config"
        assert len(config_dict["pipeline"]) == 4, "all processors should be in config"
        labeler = config_dict["pipeline"][2]["labelername"]
        assert len(labeler["rules"]) == 2
        assert isinstance(labeler["rules"][0], dict)

    def test_as_json_returns_json(self):
        config = Configuration.from_sources([path_to_config, path_to_only_output_config])
        assert isinstance(config.as_json(), str)
        assert '"type": "dummy_output"' in config.as_json()

    def test_as_yaml_returns_yaml(self):
        config = Configuration.from_sources([path_to_config, path_to_only_output_config])
        assert isinstance(config.as_yaml(), str)
        assert "type: dummy_output" in config.as_yaml()

    def test_as_dict_returns_json_serializable_dict(self, config_path):
        config = Configuration.from_sources([str(config_path)])
        config.version = "super_custom_version"
        config_dict = config.as_dict()
        assert isinstance(config_dict, dict)
        for key in config_dict.get("pipeline"):
            try:
                assert json.dumps(key)
            except Exception as error:
                raise AssertionError(f"Value for key {key} is not json serializable") from error
        assert json.dumps(config_dict), "Config dict is not json serializable"
        assert config.as_json(), "Config json is not json serializable"
        config_path.write_text(config.as_json())

    def test_returned_json_is_valid_config(self, config_path):
        config = Configuration.from_sources([str(config_path)])
        config.version = "super_custom_version"
        config_path.write_text(config.as_json())
        newconfig = Configuration.from_sources([str(config_path)])
        assert newconfig.version == "super_custom_version"

    def test_returned_yaml_is_valid_config(self, config_path):
        config = Configuration.from_sources([str(config_path)])
        config.version = "super_custom_version"
        config_path.write_text(config.as_yaml())
        newconfig = Configuration.from_sources([str(config_path)])
        assert newconfig.version == "super_custom_version"

    def test_reload_loads_generated_config(self, config_path):
        config = Configuration.from_sources([str(config_path)])
        config_path.write_text(config.as_yaml())
        config.version = "very old version"
        config.reload()
        assert config.version == "1"

    def test_reload_sets_pipeline(self, config_path):
        config = Configuration.from_sources([str(config_path)])
        config.config_refresh_interval = 5
        config_path.write_text(config.as_yaml())
        config.version = "older version"
        config.reload()
        assert config.pipeline[2]["labelername"]["type"] == "labeler"

    def test_reload_sets_new_pipline(self, config_path):
        config = Configuration.from_sources([str(config_path)])
        assert len(config.pipeline) == 4
        config.pipeline.append(
            {
                "new_processor": {
                    "type": "field_manager",
                    "rules": [],
                }
            }
        )
        config_path.write_text(config.as_yaml())
        config.version = "older version"
        config.reload()
        assert len(config.pipeline) == 5
        assert config.pipeline[4]["new_processor"]["type"] == "field_manager"

    def test_configurations_are_equal_if_version_is_equal(self):
        config = Configuration.from_sources([path_to_config])
        config2 = Configuration.from_sources([path_to_config])
        assert config is not config2
        assert config.version == config2.version
        config.config_refresh_interval = 99
        assert config.config_refresh_interval != config2.config_refresh_interval
        assert config == config2

    @pytest.mark.parametrize(
        "testcase, mocked, side_effect, expected_error_message",
        [
            (
                "getter protocol does not exist",
                "logprep.util.getter.GetterFactory.from_string",
                GetterNotFoundError("No getter for protocol 'does_not_exist'"),
                r"No getter for protocol 'does_not_exist'",
            ),
            (
                "getter raises FileNotFoundError",
                "logprep.util.getter.FileGetter.get",
                FileNotFoundError,
                r"One or more of the given config file\(s\) does not exist:",
            ),
            (
                "document is not a valid json or yaml",
                "logprep.util.getter.FileGetter.get_yaml",
                ScannerError,
                "Invalid yaml or json file:",
            ),
            (
                "url returns 404",
                "logprep.util.getter.GetterFactory.from_string",
                HTTPError("404 Client Error: Not Found for url: http://does_not_exist"),
                "404 Client Error: Not Found for url: http://does_not_exist",
            ),
        ],
    )
    def test_configuration_raises_invalidconfigurationerror(
        self, testcase, mocked, side_effect, expected_error_message
    ):
        with mock.patch(mocked, side_effect=side_effect):
            with pytest.raises(InvalidConfigurationError, match=expected_error_message):
                Configuration.from_sources([path_to_config])

    def test_valueerror_in_from_source(self, config_path):
        config_path.write_text("process_count: -1")
        with pytest.raises(InvalidConfigurationError, match=r"'process_count' must be >= 1"):
            Configuration.from_sources([str(config_path)])

    def test_from_sources_without_config_paths_attribute(self):
        with pytest.raises(
            InvalidConfigurationError, match=r"does not exist: \/etc\/logprep\/pipeline\.yml"
        ):
            Configuration.from_sources()

    def test_config_with_missing_environment_error(self):
        with mock.patch("os.environ", {"PROMETHEUS_MULTIPROC_DIR": "DOES/NOT/EXIST"}):
            with pytest.raises(
                InvalidConfigurationError,
                match=r"'DOES\/NOT\/EXIST' does not exist",
            ):
                Configuration.from_sources([path_to_config])

    def test_config_with_single_json_rule(self, config_path):
        config_path.write_text(
            """
{
"input": {
    "dummy": {"type": "dummy_input", "documents": []}
},
"output": {
    "dummy": {"type": "dummy_output"}
},
"pipeline": [
    {
        "my dissector": {
            "type": "dissector",
            "rules": [
                {
                    "filter": "message",
                    "dissector": {
                        "id": "random id",
                        "mapping": {
                            "message": "%{new_field} %{next_field}"
                        }
                    }
                }
            ]
        }
    }
    ]
}
"""
        )
        config = Configuration.from_sources([str(config_path)])
        assert len(config.pipeline) == 1

    def test_config_with_missing_environment_variable_and_other_failure_raises(self, config_path):
        config_path.write_text(
            """
version: $LOGPREP_VERSION
process_count: 1
pipeline:
    - labelername:
        type: DOES_NOT_EXIST
        rules: []
input:
    dummy:
        type: dummy_input
        documents: []
output:
    dummy:
        type: dummy_output
"""
        )
        with pytest.raises(InvalidConfigurationError) as raised:
            Configuration.from_sources([str(config_path)])
        assert len(raised.value.errors) == 2

    def test_processor_config_with_file_path(self, config_path):
        config_path.write_text(
            """
pipeline:
    - the almighty dissector:
        type: dissector
        rules:
            - tests/testdata/unit/dissector/rules/dissector_rule_1.json
input:
    dummy:
        type: dummy_input
        documents: []
output:
    dummy:
        type: dummy_output
"""
        )
        config = Configuration.from_sources([str(config_path)])
        assert len(config.pipeline) == 1
        assert len(config.pipeline[0]["the almighty dissector"]["rules"]) == 1

    @responses.activate
    def test_processor_config_with_url_path(self, tmp_path):
        config_path = tmp_path / "pipeline.yml"
        config_path.write_text(
            """
pipeline:
    - the almighty dissector:
        type: dissector
        rules:
            - http://localhost/dissector_rule.json
input:
    dummy:
        type: dummy_input
        documents: []
output:
    dummy:
        type: dummy_output
"""
        )
        resp_text = json.dumps(
            [
                {
                    "filter": "message",
                    "dissector": {
                        "id": "random id",
                        "mapping": {"message": "%{new_field} %{next_field}"},
                    },
                }
            ]
        )
        responses.add(
            responses.GET,
            "http://localhost/dissector_rule.json",
            resp_text,
        )
        config = Configuration.from_sources([str(config_path)])
        assert len(config.pipeline) == 1
        assert len(config.pipeline[0]["the almighty dissector"]["rules"]) == 1

    def test_verify_environment_raises_if_metrics_enabled_but_prometheus_multiproc_dir_not_set(
        self, config_path
    ):
        config = Configuration.from_sources([str(config_path)])
        config.metrics = MetricsConfig(enabled=True, port=4242)
        with mock.patch("os.environ", {}):
            with pytest.raises(
                InvalidConfigurationError,
                match="Metrics enabled but PROMETHEUS_MULTIPROC_DIR is not set",
            ):
                config._verify_environment()

    def test_versions_are_aggregated_for_multiple_configs(self, tmp_path):
        dummy_config = {
            "input": {"dummy": {"type": "dummy_input", "documents": []}},
            "output": {"dummy": {"type": "dummy_output"}},
        }
        config1 = Configuration(version="first", **dummy_config)
        config1_path = tmp_path / "config1.yml"
        config1_path.write_text(config1.as_yaml())

        config2 = Configuration(version="second", **dummy_config)
        config2_path = tmp_path / "config2.yml"
        config2_path.write_text(config2.as_yaml())

        config = Configuration.from_sources([str(config1_path), str(config2_path)])
        assert config.version == "first, second"

    def test_versions_are_aggregated_for_multiple_configs_with_first_unset(self, tmp_path):
        dummy_config = {
            "input": {"dummy": {"type": "dummy_input", "documents": []}},
            "output": {"dummy": {"type": "dummy_output"}},
        }
        config1 = Configuration(**dummy_config)
        config1_path = tmp_path / "config1.yml"
        config1_path.write_text(config1.as_yaml())

        config2 = Configuration(version="second", **dummy_config)
        config2_path = tmp_path / "config2.yml"
        config2_path.write_text(config2.as_yaml())

        config = Configuration.from_sources([str(config1_path), str(config2_path)])
        assert config.version == "unset, second"

    def test_versions_are_aggregated_for_multiple_configs_with_second_unset(self, tmp_path):
        dummy_config = {
            "input": {"dummy": {"type": "dummy_input", "documents": []}},
            "output": {"dummy": {"type": "dummy_output"}},
        }
        config1 = Configuration(version="first", **dummy_config)
        config1_path = tmp_path / "config1.yml"
        config1_path.write_text(config1.as_yaml())

        config2 = Configuration(**dummy_config)
        config2_path = tmp_path / "config2.yml"
        config2_path.write_text(config2.as_yaml())

        config = Configuration.from_sources([str(config1_path), str(config2_path)])
        assert config.version == "first, unset"

    def test_verify_credentials_file_raises_for_unexpected_key(self, config_path, tmp_path):
        credential_file_path = tmp_path / "credentials.yml"
        credential_file_path.write_text(
            """---
endpoints:
    /some/auth/endpoint:
        username: test_user
        password: myverysecretpassword
"""
        )
        mock_env = {ENV_NAME_LOGPREP_CREDENTIALS_FILE: str(credential_file_path)}
        with mock.patch.dict("os.environ", mock_env):
            with pytest.raises(
                InvalidConfigurationError,
                match="Invalid credentials file.* unexpected keyword argument",
            ):
                _ = Configuration.from_sources([str(config_path)])

    @pytest.mark.skipif(in_ci, reason="breaks on broken ci runner")
    def test_no_config_parameter_is_overwritten_with_a_default(self, tmp_path):
        prometheus_multiproc_dir: Path = tmp_path / "prometheus_multiproc_dir"
        prometheus_multiproc_dir.mkdir()
        exporter_config = tmp_path / "exporter-config"
        exporter_config.write_text(
            """
metrics:
  enabled: true
  port: 8000
"""
        )
        input_config = tmp_path / "input-config"
        input_config.write_text(
            """
input:
  stdin:
    type: file_input
    logfile_path: /proc/1/fdinfo/0
    start: end
    watch_file: true
    interval: 1
"""
        )

        output_config = tmp_path / "output-config"
        output_config.write_text(
            """
output:
  console:
    type: console_output
"""
        )
        with mock.patch.dict(
            "os.environ", {"PROMETHEUS_MULTIPROC_DIR": str(prometheus_multiproc_dir)}
        ):
            config1 = Configuration.from_sources(
                [str(input_config), str(output_config), str(exporter_config)]
            )
            assert config1.metrics.enabled

            config1 = Configuration.from_sources(
                [str(exporter_config), str(input_config), str(output_config)]
            )
            assert config1.metrics.enabled

            config1 = Configuration.from_sources(
                [str(input_config), str(exporter_config), str(output_config)]
            )
            assert config1.metrics.enabled

    def test_verify_calls_processor_setup(self, config_path):
        config = Configuration.from_sources([str(config_path)])
        with mock.patch("logprep.abc.processor.Processor.setup") as mocked_setup:
            config._verify()
            mocked_setup.assert_called()

    def test_verify_prints_file_not_found_errors_with_filename(self, config_path):
        config = Configuration.from_sources([str(config_path)])
        with mock.patch(
            "logprep.abc.processor.Processor.setup", side_effect=lambda: open("not_existing_file")
        ):
            with pytest.raises(
                InvalidConfigurationError, match="File not found: not_existing_file"
            ):
                config._verify()


class TestInvalidConfigurationErrors:
    @pytest.mark.parametrize(
        "error_list, expected_error_list",
        [
            ([], []),
            (
                [
                    InvalidConfigurationError("test"),
                    InvalidConfigurationError("test"),
                ],
                [
                    InvalidConfigurationError("test"),
                ],
            ),
            (
                [
                    InvalidConfigurationError("test"),
                    InvalidConfigurationError("test"),
                    TypeError("typeerror"),
                ],
                [
                    InvalidConfigurationError("test"),
                    InvalidConfigurationError("typeerror"),
                ],
            ),
            (
                [
                    InvalidConfigurationError("test"),
                    InvalidConfigurationError("test"),
                    TypeError("typeerror"),
                    ValueError("valueerror"),
                ],
                [
                    InvalidConfigurationError("test"),
                    InvalidConfigurationError("typeerror"),
                    InvalidConfigurationError("valueerror"),
                ],
            ),
            (
                [
                    InvalidConfigurationError("test"),
                    InvalidConfigurationError("test"),
                    TypeError("typeerror"),
                    ValueError("valueerror"),
                ],
                [
                    InvalidConfigurationError("test"),
                    InvalidConfigurationError("typeerror"),
                    InvalidConfigurationError("valueerror"),
                ],
            ),
        ],
    )
    def test_invalid_configuration_error_only_append_unique_errors(
        self, error_list, expected_error_list
    ):
        error = InvalidConfigurationErrors(error_list)
        assert len(error.errors) == len(expected_error_list)
        assert error.errors == expected_error_list


class TestLoggerConfig:

    @pytest.mark.parametrize("kwargs", [{"level": "DEBUG"}, {"level": "INFO"}])
    def test_logger_config_sets_global_level(self, kwargs):
        config = LoggerConfig(**kwargs)
        assert config.loggers.get("root").get("level") == kwargs.get("level")
        assert config.loggers.get("opensearch").get("level") == "ERROR"

    @pytest.mark.parametrize("kwargs", [{"loggers": {"logprep": {"level": "DEBUG"}}}])
    def test_loggers_config_only_sets_level(self, kwargs):
        config = LoggerConfig(**kwargs)
        assert config.loggers.get("root").get("level") == "INFO", "should be default"
        assert config.loggers.get("root").get("handlers") == [
            "queue",
        ], "should be default"
        assert config.loggers.get("opensearch").get("level") == "ERROR", "should be default"
