# pylint: disable=missing-docstring
import subprocess
from tempfile import NamedTemporaryFile
from typing import Dict, Optional

from logprep.util.configuration import yaml

LOGPREP_CHART_PATH = "charts/logprep"


class TestBaseChartTest:

    @staticmethod
    def render_chart(name, values: Optional[Dict] = None):
        """Render a Helm chart with the given values and return the Kubernetes objects."""
        values = values or {}
        with NamedTemporaryFile() as tmp_file:
            content = yaml.dump(values)
            tmp_file.write(content.encode())
            tmp_file.flush()
            templates = subprocess.check_output(
                ["helm", "template", name, f"{LOGPREP_CHART_PATH}", "--values", tmp_file.name]
            )
            k8s_objects = yaml.load_all(templates)
            k8s_objects = [k8s_object for k8s_object in k8s_objects if k8s_object]
            return k8s_objects

    def test_basic_deployments(self):
        rendered_objects = self.render_chart("logprep", {"logprep": {"replicas": 1}})
        assert rendered_objects
