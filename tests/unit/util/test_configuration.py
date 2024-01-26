# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
from logging import getLogger
from unittest import mock

import pytest

from logprep.util.configuration import (
    Configuration,
    InvalidConfigurationError,
    InvalidConfigurationErrors,
)
from logprep.util.getter import FileGetter
from logprep.util.json_handling import dump_config_as_file
from tests.testdata.metadata import (
    path_to_config,
    path_to_invalid_config,
    path_to_only_output_config,
)

logger = getLogger()


class TestConfiguration:
    @pytest.mark.parametrize(
        "attribute, attribute_type, default",
        [
            ("version", str, "unset"),
            ("config_refresh_interval", int, 0),
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
            ("version", "1", "2"),
            ("config_refresh_interval", 0, 900),
            ("process_count", 1, 2),
            ("timeout", 1.0, 2.0),
            ("logger", {"level": "INFO"}, {"level": "DEBUG"}),
            ("metrics", {"enabled": False, "port": 8000}, {"enabled": True, "port": 9000}),
            ("metrics", {"enabled": False, "port": 8000}, {"enabled": True, "port": 9000}),
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

        config = Configuration.from_sources([str(first_config), str(second_config)])
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
        schema: quickstart/exampledata/rules/labeler/schema.json
        include_parent_labels: true
        specific_rules: []
        generic_rules: []
"""
        )
        second_config = tmp_path / "pipeline2.yml"
        second_config.write_text(
            """
pipeline:
    - dissectorname:
        type: dissector
        specific_rules: []
        generic_rules: []
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
        assert isinstance(labeler["labelername"]["specific_rules"], list)
        assert isinstance(labeler["labelername"]["generic_rules"], list)
        assert isinstance(labeler["labelername"]["specific_rules"][0], dict)
        assert isinstance(labeler["labelername"]["generic_rules"][0], dict)

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
                            "another_error_processor": {"type": "UNKNOWN"},
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
                3,
            ),
        ],
    )
    def test_verify_verifies_config(self, tmp_path, test_case, test_config, error_count):
        test_config_path = str(tmp_path / "failure-config.yml")
        if "input" not in test_config:
            test_config["input"] = {"dummy": {"type": "dummy_input", "documents": []}}
        if "output" not in test_config:
            test_config["output"] = {"dummy": {"type": "dummy_output"}}
        dump_config_as_file(test_config_path, test_config)
        if error_count:
            with pytest.raises(InvalidConfigurationErrors) as raised:
                Configuration.from_sources([test_config_path])
            assert len(raised.value.errors) == error_count, test_case
        else:
            Configuration.from_sources([test_config_path])

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
        config = Configuration.from_sources([str(config_path)])
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
        specific_rules:
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
        generic_rules: []
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
        specific_rules:
            - filter: message
              dissector:
                id: same id
                mapping:
                  message: "%{new_field} %{next_field}"
        generic_rules:
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
                "invalid datatype in port is tolerated",
                {"enabled": True, "port": "8000"},
                None,
            ),
            (
                "unknown option",
                {"enabled": True, "port": 8000, "unknown_option": "foo"},
                InvalidConfigurationError,
            ),
        ],
    )
    def test_verify_metrics_config(
        self, metrics_config_dict, raised_error, test_case
    ):  # pylint: disable=unused-argument
        config = Configuration()
        config.metrics = metrics_config_dict
        config.output = {"dummy": {"type": "dummy_output"}}
        config.input = {"dummy": {"type": "dummy_input", "documents": []}}
        if raised_error is not None:
            try:
                config.verify()
            except InvalidConfigurationErrors as error:
                assert any(
                    (isinstance(error, raised_error) for error in error.errors)
                ), f"No '{raised_error.__name__}' raised for test case '{test_case}'!"
        else:
            config.verify()

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
        schema: quickstart/exampledata/rules/labeler/schema.json
        include_parent_labels: true
        specific_rules: []
        generic_rules: []
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
        schema: quickstart/exampledata/rules/labeler/schema.json
        include_parent_labels: true
        specific_rules: []
        generic_rules: []
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
        schema: quickstart/exampledata/rules/labeler/schema.json
        include_parent_labels: true
        specific_rules: []
        generic_rules: []
input:
    dummy:
        type: dummy_input
        documents: []
output:
    dummy:
        type: dummy_output
"""
        )
        with pytest.raises(InvalidConfigurationError, match="Configuration version did not change"):
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
        assert len(labeler["specific_rules"]) == 1
        assert isinstance(labeler["specific_rules"][0], dict)

    def test_as_json_returns_json(self):
        config = Configuration.from_sources([path_to_config, path_to_only_output_config])
        assert isinstance(config.as_json(), str)
        assert '"type": "dummy_output"' in config.as_json()

    def test_as_yaml_returns_yaml(self):
        config = Configuration.from_sources([path_to_config, path_to_only_output_config])
        assert isinstance(config.as_yaml(), str)
        assert "type: dummy_output" in config.as_yaml()

    def test_returned_json_is_valid_config(self, tmp_path):
        config = Configuration.from_sources([path_to_config])
        config.version = "super_custom_version"
        config_path = tmp_path / "pipeline.yml"
        config_path.write_text(config.as_json())
        newconfig = Configuration.from_sources([str(config_path)])
        assert newconfig.version == "super_custom_version"

    def test_returned_yaml_is_valid_config(self, tmp_path):
        config = Configuration.from_sources([path_to_config])
        config.version = "super_custom_version"
        config_path = tmp_path / "pipeline.yml"
        config_path.write_text(config.as_yaml())
        newconfig = Configuration.from_sources([str(config_path)])
        assert newconfig.version == "super_custom_version"

    def test_reload_loads_generated_config(self, tmp_path):
        config = Configuration.from_sources([path_to_config])
        config_path = tmp_path / "pipeline.yml"
        config_path.write_text(config.as_yaml())
        test_config = Configuration.from_sources([str(config_path)])
        config.version = "super_new_version"
        config_path.write_text(config.as_yaml())
        test_config.reload()

    def test_configurations_are_equal_if_version_is_equal(self):
        config = Configuration.from_sources([path_to_config])
        config2 = Configuration.from_sources([path_to_config])
        assert config is not config2
        assert config.version == config2.version
        config.config_refresh_interval = 99
        assert config.config_refresh_interval != config2.config_refresh_interval
        assert config == config2
