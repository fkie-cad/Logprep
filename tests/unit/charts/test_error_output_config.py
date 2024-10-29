# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access


from logprep.util.configuration import yaml
from tests.unit.charts.test_base import TestBaseChartTest

kafka_output_config = {
    "flush_timeout": 300,
    "kafka_config": {
        "batch.size": 100,
        "bootstrap.servers": "127.0.0.1:9092",
        "compression.type": "none",
        "queue.buffering.max.kbytes": 1024,
        "queue.buffering.max.messages": 10,
        "queue.buffering.max.ms": 1000,
        "request.required.acks": -1,
        "statistics.interval.ms": 60000,
    },
    "send_timeout": 0,
    "topic": "errors",
    "type": "confluentkafka_output",
}


class TestErrorOutputConfig(TestBaseChartTest):

    def test_error_output_config_file_is_set(self):
        expected_output_config = {
            "error_output": {
                "confluentkafka": kafka_output_config,
            }
        }
        self.manifests = self.render_chart("logprep", {"error_output": kafka_output_config})
        expected_output_config = yaml.dump(expected_output_config)
        error_output_config = self.manifests.by_query(
            "kind: ConfigMap AND metadata.name: logprep-logprep-error-output"
        )
        assert error_output_config
        error_output_config = error_output_config[0]
        assert error_output_config["data"]["error-output-config.yaml"] == expected_output_config

    def test_deployment_mounts_error_output_config(self):
        self.manifests = self.render_chart("logprep", {"error_output": kafka_output_config})
        deployment = self.manifests.by_query("kind: Deployment")[0]
        volume_mounts = deployment["spec.template.spec.containers"][0]["volumeMounts"]
        volume_mount = [mount for mount in volume_mounts if mount["name"] == "error-output-config"][
            0
        ]
        assert volume_mount
        assert volume_mount["mountPath"] == "/home/logprep/error-output-config.yaml"
        assert volume_mount["subPath"] == "error-output-config.yaml"

    def test_error_output_config_volume_is_populated(self):
        self.manifests = self.render_chart("logprep", {"error_output": kafka_output_config})
        deployment = self.manifests.by_query("kind: Deployment")[0]
        error_output_config = self.manifests.by_query(
            "kind: ConfigMap AND metadata.name: logprep-logprep-error-output"
        )
        error_output_config_name = error_output_config[0]["metadata"]["name"]
        volumes = deployment["spec.template.spec.volumes"]
        volume = [vol for vol in volumes if vol["name"] == "error-output-config"][0]
        assert volume
        assert volume["configMap"]["name"] == error_output_config_name

    def test_error_output_config_is_used_in_start_command_of_logprep(self):
        self.manifests = self.render_chart("logprep", {"error_output": kafka_output_config})
        container = self.deployment["spec.template.spec.containers"][0]
        volume_mounts = container["volumeMounts"]
        volume_mount = [mount for mount in volume_mounts if mount["name"] == "error-output-config"][
            0
        ]
        assert volume_mount["subPath"] in " ".join(container["command"])

    def test_error_output_is_not_rendered_if_no_error_output(self):
        self.manifests = self.render_chart("logprep", {"error_output": {}})
        error_output_config = self.manifests.by_query(
            "kind: ConfigMap AND metadata.name: logprep-logprep-error-output"
        )
        assert not error_output_config
        container = self.deployment["spec.template.spec.containers"][0]
        volume_mounts = container["volumeMounts"]
        volume_mount = [mount["name"] for mount in volume_mounts]
        assert "error-output-config" not in volume_mount
        assert "error-output-config.yaml" not in " ".join(container["command"])
