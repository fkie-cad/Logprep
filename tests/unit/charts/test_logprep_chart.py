# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access

import subprocess
from tempfile import NamedTemporaryFile
from typing import Dict, Optional

from logprep.util.configuration import yaml
from logprep.util.event import Documents

LOGPREP_CHART_PATH = "charts/logprep"


class TestBaseChartTest:

    @staticmethod
    def render_chart(release, values: Optional[Dict] = None) -> Documents:
        """Render a Helm chart with the given values and return the Kubernetes objects."""
        values = values or {}
        with NamedTemporaryFile() as tmp_file:
            content = yaml.dump(values)
            tmp_file.write(content.encode())
            tmp_file.flush()
            return Documents(
                subprocess.check_output(
                    ["helm", "template", release, LOGPREP_CHART_PATH, "--values", tmp_file.name]
                )
            )


class TestLogprepChart(TestBaseChartTest):

    def setup_class(self):
        self.manifests = self.render_chart("logprep")

    def test_manifests_are_rendered(self):
        assert self.manifests
        assert len(self.manifests) > 0
        assert len(self.manifests) == 4


class TestDefaultValues(TestBaseChartTest):

    def setup_class(self):
        self.manifests = self.render_chart("logprep")

    def test_labels_are_set(self):
        for manifest in self.manifests:
            assert "metadata.labels" in manifest

    def test_application_label_is_set(self):
        for manifest in self.manifests:
            assert manifest["metadata.labels"]["app.kubernetes.io/name"] == "logprep-logprep"
            assert manifest["metadata.labels"]["app.kubernetes.io/application"] == "logprep"


class TestMetricsService(TestBaseChartTest):

    def setup_class(self):
        self.manifests = self.render_chart("logprep")

    @property
    def service(self):
        return self.manifests.by_query("kind: Service")[0]

    def test_service_name(self):
        assert self.service["metadata.name"] == "logprep-logprep-metrics-service"

    def test_service_is_not_rendered_if_metrics_disabled(self):
        manifests = self.render_chart("logprep", {"exporter": {"enabled": False}})
        assert len(manifests.by_query("kind: Service")) == 0

    def test_service_sets_port(self):
        logprep_values = {"exporter": {"port": 9000, "service_port": 9001}}
        self.manifests = self.render_chart("logprep", logprep_values)
        assert self.service["spec.ports"][0]["port"] == 9001
        assert self.service["spec.ports"][0]["targetPort"] == 9000

    def test_service_sets_defaults(self):
        assert self.service["spec.ports"][0]["port"] == 8001
        assert self.service["spec.ports"][0]["targetPort"] == 8000

    def test_service_sets_selector(self):
        deployment = self.manifests.by_query("kind: Deployment")[0]
        deployment_selected_label = deployment["spec.template.metadata.labels"][
            "app.kubernetes.io/name"
        ]
        assert self.service["spec.selector"]["app.kubernetes.io/name"] == deployment_selected_label

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
