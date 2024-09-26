# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access

import pytest

from logprep.util.configuration import yaml
from tests.unit.charts.test_base import TestBaseChartTest


class TestLoggerConfig(TestBaseChartTest):

    def test_exporter_config_file_is_set(self):
        expected_logger_config = {
            "logger": {
                "level": "INFO",
                "loggers": {
                    "Runner": {"level": "DEBUG"},
                    "py.warnings": {"level": "ERROR"},
                },
            }
        }
        self.manifests = self.render_chart("logprep", expected_logger_config)
        expected_logger_config = yaml.dump(expected_logger_config)
        logger_config = self.manifests.by_query(
            "kind: ConfigMap AND metadata.name: logprep-logprep-logger"
        )
        assert logger_config
        logger_config = logger_config[0]
        assert logger_config["data"]["logger-config.yaml"] == expected_logger_config

    def test_deployment_mounts_logger_config(self):
        deployment = self.manifests.by_query("kind: Deployment")[0]
        volume_mounts = deployment["spec.template.spec.containers"][0]["volumeMounts"]
        volume_mount = [mount for mount in volume_mounts if mount["name"] == "logger-config"][0]
        assert volume_mount
        assert volume_mount["mountPath"] == "/home/logprep/logger-config.yaml"
        assert volume_mount["subPath"] == "logger-config.yaml"

    def test_logger_config_volume_is_populated(self):
        deployment = self.manifests.by_query("kind: Deployment")[0]
        exporter_config = self.manifests.by_query(
            "kind: ConfigMap AND metadata.name: logprep-logprep-logger"
        )
        exporter_config_name = exporter_config[0]["metadata"]["name"]
        volumes = deployment["spec.template.spec.volumes"]
        volume = [vol for vol in volumes if vol["name"] == "logger-config"][0]
        assert volume
        assert volume["configMap"]["name"] == exporter_config_name

    def test_logger_config_is_used_to_start_logprep(self):
        container = self.deployment["spec.template.spec.containers"][0]
        volume_mounts = container["volumeMounts"]
        volume_mount = [mount for mount in volume_mounts if mount["name"] == "logger-config"][0]
        assert volume_mount["subPath"] in " ".join(container["command"])

    @pytest.mark.parametrize(
        "logger_config, expected",
        [
            ({"logger": {"level": "INFO"}}, False),
            ({"logger": {"level": "DEBUG"}}, True),
        ],
    )
    def test_environment_variable_is_set_if_debug_loglevel(self, logger_config, expected):
        self.manifests = self.render_chart("logprep", logger_config)
        debug_var = self.deployment["spec.template.spec.containers.0.env.0"]
        assert (debug_var["name"] == "DEBUG") == expected
