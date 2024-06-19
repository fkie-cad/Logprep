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
        mount = self.deployment["spec.template.spec.containers.0.volumeMounts.0"]
        assert mount["mountPath"] == "/tmp"
        assert mount["name"] == "logprep-temp"

    @pytest.mark.parametrize(
        "logprep_values, expected",
        [
            ({}, False),
            ({"secrets": {"certificates": {"name": "custom-certs"}}}, True),
        ],
    )
    def test_deployment_certificates(self, logprep_values, expected):
        self.manifests = self.render_chart("logprep", logprep_values)
        volumes = self.deployment["spec.template.spec.volumes"]
        mounts = self.deployment["spec.template.spec.containers.0.volumeMounts"]
        env = self.deployment["spec.template.spec.containers.0.env"]

        for volume in volumes:
            if volume["name"] == "certificates":
                assert expected
                break
        else:
            assert not expected

        for mount in mounts:
            if mount["name"] == "certificates":
                assert expected
                break
        else:
            assert not expected

        for variable in env:
            if variable["name"] == "REQUESTS_CA_BUNDLE":
                assert expected
                break
        else:
            assert not expected

    def test_certificates_env(self):
        self.manifests = self.render_chart(
            "logprep", {"secrets": {"certificates": {"name": "custom-certs"}}}
        )
        env = self.deployment["spec.template.spec.containers.0.env"]
        for variable in env:
            if variable["name"] == "REQUESTS_CA_BUNDLE":
                assert variable["value"] == "/home/logprep/certificates/custom-certs"
                break
        else:
            assert False, "REQUESTS_CA_BUNDLE not found"

    def test_certificates_volume(self):
        self.manifests = self.render_chart(
            "logprep", {"secrets": {"certificates": {"name": "custom-certs"}}}
        )
        volumes = self.deployment["spec.template.spec.volumes"]
        for volume in volumes:
            if volume["name"] == "certificates":
                assert volume["secret"]["secretName"] == "custom-certs"
                break
        else:
            assert False, "certificates volume not found"

    def test_certificates_volume_mount(self):
        self.manifests = self.render_chart(
            "logprep", {"secrets": {"certificates": {"name": "custom-certs"}}}
        )
        mounts = self.deployment["spec.template.spec.containers.0.volumeMounts"]
        for mount in mounts:
            if mount["name"] == "certificates":
                assert mount["mountPath"].endswith("custom-certs")
                break
        else:
            assert False, "certificates mount not found"

    @pytest.mark.parametrize(
        "logprep_values, expected",
        [
            ({}, False),
            ({"secrets": {"credentials": {"name": "my-creds"}}}, True),
        ],
    )
    def test_deployment_credentials(self, logprep_values, expected):
        self.manifests = self.render_chart("logprep", logprep_values)
        volumes = self.deployment["spec.template.spec.volumes"]
        mounts = self.deployment["spec.template.spec.containers.0.volumeMounts"]
        env = self.deployment["spec.template.spec.containers.0.env"]

        for volume in volumes:
            if volume["name"] == "credentials":
                assert expected
                break
        else:
            assert not expected

        for mount in mounts:
            if mount["name"] == "credentials":
                assert expected
                break
        else:
            assert not expected

        for variable in env:
            if variable["name"] == "LOGPREP_CREDENTIALS_FILE":
                assert expected
                break
        else:
            assert not expected

    def test_credentials_env(self):
        self.manifests = self.render_chart(
            "logprep", {"secrets": {"credentials": {"name": "my-creds"}}}
        )
        env = self.deployment["spec.template.spec.containers.0.env"]
        for variable in env:
            if variable["name"] == "LOGPREP_CREDENTIALS_FILE":
                assert variable["value"] == "/home/logprep/credentials/my-creds"
                break
        else:
            assert False, "LOGPREP_CREDENTIALS_FILE not found"

    def test_credentials_volume(self):
        self.manifests = self.render_chart(
            "logprep", {"secrets": {"credentials": {"name": "my-creds"}}}
        )
        volumes = self.deployment["spec.template.spec.volumes"]
        for volume in volumes:
            if volume["name"] == "credentials":
                assert volume["secret"]["secretName"] == "my-creds"
                break
        else:
            assert False, "credentials volume not found"

    def test_credentials_volume_mount(self):
        self.manifests = self.render_chart(
            "logprep", {"secrets": {"credentials": {"name": "my-creds"}}}
        )
        mounts = self.deployment["spec.template.spec.containers.0.volumeMounts"]
        for mount in mounts:
            if mount["name"] == "credentials":
                assert mount["mountPath"].endswith("my-creds"), mount["mountPath"]
                break
        else:
            assert False, "credentials mount not found"

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

    def test_image_pull_secret(self):
        assert False
