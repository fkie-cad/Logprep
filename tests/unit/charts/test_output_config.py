# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access


from logprep.util.configuration import yaml
from tests.unit.charts.test_base import TestBaseChartTest

opensearch_config = {
    "ca_cert": "/path/to/cert.crt",
    "default_index": "default_index",
    "hosts": ["127.0.0.1:9200"],
    "message_backlog_size": 10000,
    "timeout": 10000,
    "type": "opensearch_output",
}


class TestOutputConfig(TestBaseChartTest):

    def test_output_config_file_is_set(self):
        expected_output_config = {
            "output": {
                "opensearch": opensearch_config,
            }
        }
        self.manifests = self.render_chart("logprep", {"output": opensearch_config})
        expected_output_config = yaml.dump(expected_output_config)
        output_config = self.manifests.by_query(
            "kind: ConfigMap AND metadata.name: logprep-logprep-output"
        )
        assert output_config
        output_config = output_config[0]
        assert output_config["data"]["output-config.yaml"] == expected_output_config

    def test_deployment_mounts_output_config(self):
        deployment = self.manifests.by_query("kind: Deployment")[0]
        volume_mounts = deployment["spec.template.spec.containers"][0]["volumeMounts"]
        volume_mount = [mount for mount in volume_mounts if mount["name"] == "output-config"][0]
        assert volume_mount
        assert volume_mount["mountPath"] == "/home/logprep/output-config.yaml"
        assert volume_mount["subPath"] == "output-config.yaml"

    def test_output_config_volume_is_populated(self):
        deployment = self.manifests.by_query("kind: Deployment")[0]
        exporter_config = self.manifests.by_query(
            "kind: ConfigMap AND metadata.name: logprep-logprep-output"
        )
        exporter_config_name = exporter_config[0]["metadata"]["name"]
        volumes = deployment["spec.template.spec.volumes"]
        volume = [vol for vol in volumes if vol["name"] == "output-config"][0]
        assert volume
        assert volume["configMap"]["name"] == exporter_config_name

    def test_output_config_is_used_to_start_logprep(self):
        container = self.deployment["spec.template.spec.containers"][0]
        volume_mounts = container["volumeMounts"]
        volume_mount = [mount for mount in volume_mounts if mount["name"] == "output-config"][0]
        assert volume_mount["subPath"] in " ".join(container["command"])
