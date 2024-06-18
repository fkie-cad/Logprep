# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access

import pytest

from tests.unit.charts.test_base import TestBaseChartTest


class TestDeployment(TestBaseChartTest):

    @pytest.mark.parametrize(
        "logprep_values, expected",
        [
            ({"affinity": True}, True),
            ({"affinity": False}, False),
        ],
    )
    def test_deployment_pod_affinity(self, logprep_values, expected):
        self.manifests = self.render_chart("logprep", logprep_values)
        assert bool(self.deployment["spec.template.spec.affinity"]) == expected

    @pytest.mark.parametrize(
        "logprep_values",
        [{"affinity": True}],
    )
    def test_affinity_uses_selector_labels(self, logprep_values):
        self.manifests = self.render_chart("logprep", logprep_values)
        affinity = self.deployment["spec.template.spec.affinity.podAntiAffinity"]
        label_selector = affinity["requiredDuringSchedulingIgnoredDuringExecution"][0][
            "labelSelector"
        ]
        assert len(label_selector["matchExpressions"]) == 2
        assert label_selector["matchExpressions"][0] == {
            "key": "app.kubernetes.io/instance",
            "operator": "In",
            "values": ["logprep"],
        }
        assert label_selector["matchExpressions"][1] == {
            "key": "app.kubernetes.io/name",
            "operator": "In",
            "values": ["logprep-logprep"],
        }

    def test_temp_directory(self):
        assert False

    def test_certificate_store(self):
        assert False

    def test_security_context(self):
        assert self.deployment["spec.template.spec.securityContext"]
        security_context = self.deployment["spec.template.spec.securityContext"]
        assert security_context["runAsUser"] == 1000
        assert security_context["fsGroup"] == 1000
        security_context = self.deployment["spec.template.spec.containers.0.securityContext"]
        assert security_context["runAsUser"] == 1000
        assert security_context["capabilities"]["drop"] == ["ALL"]
        assert security_context["readOnlyRootFilesystem"] is True
        assert security_context["runAsNonRoot"] is True

    def test_resources(self):
        assert self.deployment["spec.template.spec.containers.0.resources"]
        resources = self.deployment["spec.template.spec.containers.0.resources"]
        assert resources["limits"]["cpu"] == "1"
        assert resources["limits"]["memory"] == "2Gi"
        assert resources["requests"]["cpu"] == "250m"
        assert resources["requests"]["memory"] == "2Gi"

    def test_deployment_match_labels(self):
        assert self.deployment["spec.selector.matchLabels"] == {
            "app.kubernetes.io/name": "logprep-logprep",
            "app.kubernetes.io/instance": "logprep",
        }
