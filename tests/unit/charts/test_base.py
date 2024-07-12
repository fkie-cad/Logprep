# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access

import re
import subprocess
from tempfile import NamedTemporaryFile
from typing import Dict, Optional

import pytest

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
    def exporter_service(self):
        query = "kind: Service AND metadata.name: logprep-logprep-exporter"
        return self.manifests.by_query(query)[0]


class TestLogprepChart(TestBaseChartTest):

    def test_manifests_are_rendered(self):
        assert self.manifests
        assert len(self.manifests) > 0
        assert len(self.manifests) == 8

    def test_extra_labels_are_populated(self):
        logprep_values = {"extraLabels": {"foo": "bar"}}
        self.manifests = self.render_chart("logprep", logprep_values)
        for manifest in self.manifests:
            assert "metadata.labels" in manifest
            assert "foo" in manifest["metadata.labels"]
            assert manifest["metadata.labels.foo"] == "bar"


class TestDefaultValues(TestBaseChartTest):

    def test_labels_are_set(self):
        for manifest in self.manifests:
            assert "metadata.labels" in manifest

    @pytest.mark.parametrize(
        "label, label_value",
        [
            ("app.kubernetes.io/name", "logprep-logprep"),
            ("app.kubernetes.io/application", "logprep"),
            ("app.kubernetes.io/managed-by", "Helm"),
            ("app.kubernetes.io/instance", "logprep"),
        ],
    )
    def test_common_labels_are_set(self, label, label_value):
        for manifest in self.manifests:
            assert manifest["metadata.labels"][label] == label_value

    def test_chart_version_is_set(self):
        for manifest in self.manifests:
            assert re.search(
                r"\d+\.\d+\.\d+", manifest["metadata.labels"]["app.kubernetes.io/version"]
            )
