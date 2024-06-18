# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access

import pytest

from logprep.util.configuration import yaml
from tests.unit.charts.test_base import TestBaseChartTest


class TestExporterConfig(TestBaseChartTest):

    def test_service_name(self):
        assert self.exporter_service["metadata.name"] == "logprep-logprep-exporter"

    def test_service_is_not_rendered_if_exporter_disabled(self):
        manifests = self.render_chart("logprep", {"exporter": {"enabled": False}})
        assert len(manifests.by_query("kind: Service")) == 0

    def test_service_sets_port(self):
        logprep_values = {"exporter": {"port": 9000, "service_port": 9001}}
        self.manifests = self.render_chart("logprep", logprep_values)
        assert self.exporter_service["spec.ports"][0]["port"] == 9001
        assert self.exporter_service["spec.ports"][0]["targetPort"] == 9000

    def test_service_sets_defaults(self):
        assert self.exporter_service["spec.ports"][0]["port"] == 8001
        assert self.exporter_service["spec.ports"][0]["targetPort"] == 8000

    def test_service_sets_selector(self):
        deployment = self.manifests.by_query("kind: Deployment")[0]
        deployment_selected_label = deployment["spec.template.metadata.labels"][
            "app.kubernetes.io/name"
        ]
        assert (
            self.exporter_service["spec.selector"]["app.kubernetes.io/name"]
            == deployment_selected_label
        )

    def test_exporter_config_file_is_set(self):
        expected_exporter_config = {
            "metrics": {
                "enabled": True,
                "port": 8000,
            }
        }
        expected_exporter_config = yaml.dump(expected_exporter_config)
        exporter_config = self.manifests.by_query(
            "kind: ConfigMap AND metadata.name: logprep-logprep-exporter"
        )
        assert exporter_config
        exporter_config = exporter_config[0]
        assert exporter_config["data"]["exporter-config.yaml"] == expected_exporter_config

    def test_exporter_config_file_is_set_if_exporter_not_enabled(self):
        self.manifests = self.render_chart("logprep", {"exporter": {"enabled": False}})
        exporter_config = self.manifests.by_query(
            "kind: ConfigMap AND metadata.name: logprep-logprep-exporter"
        )
        assert exporter_config
        exporter_config = exporter_config[0]
        assert "enabled: false" in exporter_config["data"]["exporter-config.yaml"]

    def test_deployment_mounts_exporter_config(self):
        deployment = self.manifests.by_query("kind: Deployment")[0]
        volume_mounts = deployment["spec.template.spec.containers"][0]["volumeMounts"]
        volume_mount = [mount for mount in volume_mounts if mount["name"] == "exporter-config"][0]
        assert volume_mount
        assert volume_mount["mountPath"] == "/home/logprep/configurations/exporter-config.yaml"
        assert volume_mount["subPath"] == "exporter-config.yaml"

    def test_exporter_config_volume_is_populated(self):
        deployment = self.manifests.by_query("kind: Deployment")[0]
        exporter_config = self.manifests.by_query(
            "kind: ConfigMap AND metadata.name: logprep-logprep-exporter"
        )
        exporter_config_name = exporter_config[0]["metadata"]["name"]
        volumes = deployment["spec.template.spec.volumes"]
        volume = [vol for vol in volumes if vol["name"] == "exporter-config"][0]
        assert volume
        assert volume["configMap"]["name"] == exporter_config_name

    def test_exporter_config_is_used_to_start_logprep(self):
        container = self.deployment["spec.template.spec.containers"][0]
        volume_mounts = container["volumeMounts"]
        volume_mount = [mount for mount in volume_mounts if mount["name"] == "exporter-config"][0]
        assert volume_mount["mountPath"] in " ".join(container["command"])

    def test_exporter_config_is_mounted_if_exporter_not_enabled(self):
        self.manifests = self.render_chart("logprep", {"exporter": {"enabled": False}})
        container = self.deployment["spec.template.spec.containers"][0]
        volume_mounts = container["volumeMounts"]
        volume_mount = [mount for mount in volume_mounts if mount["name"] == "exporter-config"][0]
        assert volume_mount["mountPath"] in " ".join(container["command"])
        volumes = self.deployment["spec.template.spec.volumes"]
        volume = [vol for vol in volumes if vol["name"] == "exporter-config"]
        assert volume
        assert volume[0]["configMap"]["name"] == "logprep-logprep-exporter"

    @pytest.mark.parametrize(
        "exporter_config, expected",
        [
            ({"exporter": {"enabled": True}}, True),
            ({"exporter": {"enabled": False}}, False),
        ],
    )
    def test_prometheus_multiproc_environment_variable(self, exporter_config, expected):
        self.manifests = self.render_chart("logprep", exporter_config)
        env_var = self.deployment["spec.template.spec.containers.0.env.2"]
        assert (env_var["name"] == "PROMETHEUS_MULTIPROC_DIR") == expected

    @pytest.mark.parametrize(
        "exporter_config, expected",
        [
            ({"exporter": {"enabled": True}}, True),
            ({"exporter": {"enabled": False}}, False),
        ],
    )
    def test_prometheus_multiproc_environment_volume(self, exporter_config, expected):
        self.manifests = self.render_chart("logprep", exporter_config)
        volume_mount = self.deployment["spec.template.spec.containers.0.volumeMounts.1"]
        assert (volume_mount["name"] == "prometheus-multiproc") == expected
        volumes = self.deployment["spec.template.spec.volumes.1"]
        assert (volumes["name"] == "prometheus-multiproc") == expected

    @pytest.mark.parametrize(
        "exporter_config, expected",
        [
            ({"exporter": {"enabled": True}}, True),
            ({"exporter": {"enabled": False}}, False),
        ],
    )
    def test_probes_are_only_populated_if_exporter_enabled(self, exporter_config, expected):
        self.manifests = self.render_chart("logprep", exporter_config)
        deployment = self.manifests.by_query("kind: Deployment")[0]
        container = deployment["spec.template.spec.containers"][0]
        assert bool(container.get("livenessProbe")) == expected
        assert bool(container.get("readinessProbe")) == expected
        assert bool(container.get("startupProbe")) == expected

    @pytest.mark.parametrize(
        "exporter_config, expected",
        [
            ({"exporter": {"enabled": True}}, True),
            ({"exporter": {"enabled": False}}, False),
        ],
    )
    def test_pod_monitor_are_populated(self, exporter_config, expected):
        self.manifests = self.render_chart("logprep", exporter_config)
        assert bool(self.manifests.by_query("kind: PodMonitor")) == expected

    def test_pod_monitor_uses_exporter_port(self):
        logprep_values = {"exporter": {"port": 9000, "service_port": 9001}}
        self.manifests = self.render_chart("logprep", logprep_values)
        pod_monitor = self.manifests.by_query("kind: PodMonitor")[0]
        assert pod_monitor["spec.podMetricsEndpoints.0.targetPort"] == 9000

    def test_pod_monitor_uses_scrape_interval(self):
        logprep_values = {"exporter": {"port": 9000, "scrape_interval": "10s"}}
        self.manifests = self.render_chart("logprep", logprep_values)
        pod_monitor = self.manifests.by_query("kind: PodMonitor")[0]
        assert pod_monitor["spec.podMetricsEndpoints.0.interval"] == "10s"

    def test_defaults(self):
        pod_monitor = self.manifests.by_query("kind: PodMonitor")[0]
        assert pod_monitor["metadata.name"] == "logprep-logprep"
        assert pod_monitor["spec.selector.matchLabels"]["kubernetes.io/name"] == "logprep-logprep"
        assert pod_monitor["spec.podMetricsEndpoints.0.targetPort"] == 8000
        assert pod_monitor["spec.podMetricsEndpoints.0.interval"] == "30s"