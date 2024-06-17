# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access

from logprep.util.configuration import yaml
from tests.unit.charts.test_base import TestBaseChartTest


class TestMetricsService(TestBaseChartTest):

    def test_service_name(self):
        assert self.metrics_service["metadata.name"] == "logprep-logprep-metrics-service"

    def test_service_is_not_rendered_if_metrics_disabled(self):
        manifests = self.render_chart("logprep", {"exporter": {"enabled": False}})
        assert len(manifests.by_query("kind: Service")) == 0

    def test_service_sets_port(self):
        logprep_values = {"exporter": {"port": 9000, "service_port": 9001}}
        self.manifests = self.render_chart("logprep", logprep_values)
        assert self.metrics_service["spec.ports"][0]["port"] == 9001
        assert self.metrics_service["spec.ports"][0]["targetPort"] == 9000

    def test_service_sets_defaults(self):
        assert self.metrics_service["spec.ports"][0]["port"] == 8001
        assert self.metrics_service["spec.ports"][0]["targetPort"] == 8000

    def test_service_sets_selector(self):
        deployment = self.manifests.by_query("kind: Deployment")[0]
        deployment_selected_label = deployment["spec.template.metadata.labels"][
            "app.kubernetes.io/name"
        ]
        assert (
            self.metrics_service["spec.selector"]["app.kubernetes.io/name"]
            == deployment_selected_label
        )

    def test_metrics_config_file_is_set(self):
        expected_metrics_config = {
            "metrics": {
                "enabled": True,
                "port": 8000,
            }
        }
        expected_metrics_config = yaml.dump(expected_metrics_config)
        metrics_config = self.manifests.by_query(
            "kind: ConfigMap AND metadata.name: logprep-logprep-metrics-config"
        )
        assert metrics_config
        metrics_config = metrics_config[0]
        assert metrics_config["data"]["metrics-config.yaml"] == expected_metrics_config

    def test_metrics_config_file_is_set_if_exporter_not_enabled(self):
        self.manifests = self.render_chart("logprep", {"exporter": {"enabled": False}})
        metrics_config = self.manifests.by_query(
            "kind: ConfigMap AND metadata.name: logprep-logprep-metrics-config"
        )
        assert metrics_config
        metrics_config = metrics_config[0]
        assert "enabled: false" in metrics_config["data"]["metrics-config.yaml"]

    def test_deployment_mounts_metrics_config(self):
        deployment = self.manifests.by_query("kind: Deployment")[0]
        volume_mounts = deployment["spec.template.spec.containers"][0]["volumeMounts"]
        volume_mount = [mount for mount in volume_mounts if mount["name"] == "metrics-config"][0]
        assert volume_mount
        assert volume_mount["mountPath"] == "/home/logprep/configurations/metrics-config.yaml"
        assert volume_mount["subPath"] == "metrics-config.yaml"

    def test_metrics_config_volume_is_populated(self):
        deployment = self.manifests.by_query("kind: Deployment")[0]
        metrics_config = self.manifests.by_query(
            "kind: ConfigMap AND metadata.name: logprep-logprep-metrics-config"
        )
        metrics_config_name = metrics_config[0]["metadata"]["name"]
        volumes = deployment["spec.template.spec.volumes"]
        volume = [vol for vol in volumes if vol["name"] == "metrics-config"][0]
        assert volume
        assert volume["configMap"]["name"] == metrics_config_name

    def test_metrics_config_is_used_to_start_logprep(self):
        deployment = self.manifests.by_query("kind: Deployment")[0]
        container = deployment["spec.template.spec.containers"][0]
        volume_mounts = container["volumeMounts"]
        volume_mount = [mount for mount in volume_mounts if mount["name"] == "metrics-config"][0]
        assert volume_mount["mountPath"] in " ".join(container["command"])

    def test_metrics_config_is_mounted_if_exporter_not_enabled(self):
        self.manifests = self.render_chart("logprep", {"exporter": {"enabled": False}})
        deployment = self.manifests.by_query("kind: Deployment")[0]
        container = deployment["spec.template.spec.containers"][0]
        volume_mounts = container["volumeMounts"]
        volume_mount = [mount for mount in volume_mounts if mount["name"] == "metrics-config"][0]
        assert volume_mount["mountPath"] in " ".join(container["command"])
        volumes = deployment["spec.template.spec.volumes"]
        volume = [vol for vol in volumes if vol["name"] == "metrics-config"]
        assert volume
        assert volume[0]["configMap"]["name"] == "logprep-logprep-metrics-config"

    def test_prometheus_multiproc_environment_variable(self):
        assert False

    def test_prometheus_multiproc_environment_mount(self):
        assert False

    def test_readiness_probes(self):
        assert False

    def test_pod_monitors(self):
        assert False
