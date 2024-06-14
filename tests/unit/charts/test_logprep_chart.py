# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access

import subprocess
from tempfile import NamedTemporaryFile
from typing import Dict, List, Optional

from attrs import define, field, validators

from logprep.filter.expression.filter_expression import KeyDoesNotExistError
from logprep.filter.lucene_filter import LuceneFilter
from logprep.util.configuration import yaml
from logprep.util.helper import get_dotted_field_value

LOGPREP_CHART_PATH = "charts/logprep"


def convert_manifests(data: bytes | list) -> List[Dict]:
    if isinstance(data, bytes):
        data = yaml.load_all(data)
    return [
        Manifest(manifest_dict) if isinstance(manifest_dict, dict) else manifest_dict
        for manifest_dict in data
        if manifest_dict
    ]


@define
class Manifests:

    _manifests: List["Manifest"] = field(
        validator=validators.instance_of(list), converter=convert_manifests
    )

    def by_query(self, query: str) -> "Manifests":
        return Manifests([manifest for manifest in self._manifests if manifest.query(query)])

    def __len__(self):
        return len(self._manifests)


@define
class Manifest:

    _manifest: Dict = field(validator=validators.instance_of(dict))

    def query(self, query: str) -> bool:
        filter_expression = LuceneFilter.create(query)
        try:
            return filter_expression.does_match(self._manifest)
        except KeyDoesNotExistError:
            return False

    def __getitem__(self, key):
        return get_dotted_field_value(self._manifest, key)

    def __contains__(self, key):
        return self.query(key)


class TestBaseChartTest:

    @staticmethod
    def render_chart(release, values: Optional[Dict] = None) -> Manifests:
        """Render a Helm chart with the given values and return the Kubernetes objects."""
        values = values or {}
        with NamedTemporaryFile() as tmp_file:
            content = yaml.dump(values)
            tmp_file.write(content.encode())
            tmp_file.flush()
            return Manifests(
                subprocess.check_output(
                    ["helm", "template", release, LOGPREP_CHART_PATH, "--values", tmp_file.name]
                )
            )


class TestDefaultValues(TestBaseChartTest):

    def setup_class(self):
        self.manifests = self.render_chart("logprep")

    def test_labels_are_set(self):
        for manifest in self.manifests._manifests:
            assert "metadata.labels" in manifest

    def test_application_label_is_set(self):
        for manifest in self.manifests._manifests:
            assert manifest["metadata.labels"]["app.kubernetes.io/name"] == "logprep-logprep"
