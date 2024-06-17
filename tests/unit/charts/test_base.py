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

    def setup_class(self):
        self.manifests = self.render_chart("logprep")

    @property
    def deployment(self):
        return self.manifests.by_query("kind: Deployment")[0]

    @property
    def metrics_service(self):
        return self.manifests.by_query(
            "kind: Service AND metadata.name: logprep-logprep-metrics-service"
        )[0]


class TestLogprepChart(TestBaseChartTest):

    def test_manifests_are_rendered(self):
        assert self.manifests
        assert len(self.manifests) > 0
        assert len(self.manifests) == 4

    def test_deployment_pod_affinity(self):
        assert False

    def test_temp_directory(self):
        assert False

    def test_certificate_store(self):
        assert False


class TestDefaultValues(TestBaseChartTest):

    def test_labels_are_set(self):
        for manifest in self.manifests:
            assert "metadata.labels" in manifest

    def test_application_label_is_set(self):
        for manifest in self.manifests:
            assert manifest["metadata.labels"]["app.kubernetes.io/name"] == "logprep-logprep"
            assert manifest["metadata.labels"]["app.kubernetes.io/application"] == "logprep"
