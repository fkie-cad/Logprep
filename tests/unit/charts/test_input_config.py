# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access

import pytest

from logprep.util.configuration import yaml
from tests.unit.charts.test_base import TestBaseChartTest


class TestInputConfig(TestBaseChartTest):

    def test_todo(self):
        assert False

    def test_input_config_file_is_set(self):
        expected_input_config = {
            "input": {
                "documents": [],
                "type": "dummy_input",
            }
        }
        self.manifests = self.render_chart("logprep", expected_input_config)
        expected_input_config = yaml.dump(expected_input_config)
        input_config = self.manifests.by_query(
            "kind: ConfigMap AND metadata.name: logprep-logprep-input"
        )
        assert input_config
        input_config = input_config[0]
        assert input_config["data"]["input-config.yaml"] == expected_input_config

    def test_deployment_mounts_input_config(self):
        deployment = self.manifests.by_query("kind: Deployment")[0]
        volume_mounts = deployment["spec.template.spec.containers"][0]["volumeMounts"]
        volume_mount = [mount for mount in volume_mounts if mount["name"] == "input-config"][0]
        assert volume_mount
        assert volume_mount["mountPath"] == "/home/logprep/configurations/input-config.yaml"
        assert volume_mount["subPath"] == "input-config.yaml"

    def test_input_config_volume_is_populated(self):
        deployment = self.manifests.by_query("kind: Deployment")[0]
        exporter_config = self.manifests.by_query(
            "kind: ConfigMap AND metadata.name: logprep-logprep-input"
        )
        exporter_config_name = exporter_config[0]["metadata"]["name"]
        volumes = deployment["spec.template.spec.volumes"]
        volume = [vol for vol in volumes if vol["name"] == "input-config"][0]
        assert volume
        assert volume["configMap"]["name"] == exporter_config_name

    def test_input_config_is_used_to_start_logprep(self):
        container = self.deployment["spec.template.spec.containers"][0]
        volume_mounts = container["volumeMounts"]
        volume_mount = [mount for mount in volume_mounts if mount["name"] == "input-config"][0]
        assert volume_mount["mountPath"] in " ".join(container["command"])
