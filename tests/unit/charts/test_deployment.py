# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access

from pathlib import Path

import pytest

from logprep.util.getter import GetterFactory
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

    def test_security_context(self):
        assert self.deployment["spec.template.spec.securityContext"]
        security_context = self.deployment["spec.template.spec.securityContext"]
        assert security_context["runAsUser"] == 1000
        assert security_context["fsGroup"] == 1000
        security_context = self.deployment["spec.template.spec.containers.0.securityContext"]
        assert security_context["capabilities"]["drop"] == ["ALL"]
        assert security_context["readOnlyRootFilesystem"] is True
        assert security_context["runAsNonRoot"] is True

    def test_add_security_context(self):
        self.manifests = self.render_chart(
            "logprep",
            {
                "containerSecurityContext": {"allowPriviledgeEscalation": "false"},
                "podSecurityContext": {"supplementalGroups": [4000]},
            },
        )
        assert self.deployment["spec.template.spec.securityContext"]
        security_context = self.deployment["spec.template.spec.securityContext"]
        assert security_context["supplementalGroups"] == [4000]
        security_context = self.deployment["spec.template.spec.containers.0.securityContext"]
        assert security_context["allowPriviledgeEscalation"] == "false"

    def test_init_containers(self):
        self.manifests = self.render_chart(
            "logprep",
            {
                "initContainers": {"name": "test-init"},
            },
        )

        assert self.deployment["spec.template.spec.initContainers"]
        init_container = self.deployment["spec.template.spec.initContainers"]
        assert init_container["name"] == "test-init"

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

    @pytest.mark.parametrize(
        "logprep_values, expected",
        [({}, False), ({"secrets": {"imagePullSecret": {"name": "my-secret"}}}, "my-secret")],
    )
    def test_image_pull_secret(self, logprep_values, expected):
        self.manifests = self.render_chart("logprep", logprep_values)
        image_pull_secret = self.deployment["spec.template.spec.imagePullSecrets.0"]
        assert bool(image_pull_secret) == bool(expected)
        if expected:
            assert image_pull_secret.get("name") == expected

    def test_image_pull_secret_has_no_volume(self):
        self.manifests = self.render_chart(
            "logprep", {"secrets": {"imagePullSecret": {"name": "my-secret"}}}
        )
        image_pull_secret = self.deployment["spec.template.spec.imagePullSecrets.0"]
        assert image_pull_secret.get("name") == "my-secret"
        volumes = self.deployment["spec.template.spec.volumes"]
        for volume in volumes:
            if volume["name"] == "imagepullsecret":
                assert False, "imagePullSecret in volumes"

    def test_image_pull_secret_has_no_mount(self):
        self.manifests = self.render_chart(
            "logprep", {"secrets": {"imagePullSecret": {"name": "my-secret"}}}
        )
        image_pull_secret = self.deployment["spec.template.spec.imagePullSecrets.0"]
        assert image_pull_secret.get("name") == "my-secret"
        mounts = self.deployment["spec.template.spec.containers.0.volumeMounts"]
        for mount in mounts:
            if mount["name"] == "imagepullsecret":
                assert False, "imagePullSecret in volumeMonts"

    def test_configuration_with_http_endpoints_command_is_appended(self):
        logprep_values = {
            "configurations": [
                {"name": "config1", "data": {"process_count": 2}},
                {"name": "http://external-config.bla"},
            ]
        }
        self.manifests = self.render_chart("logprep", logprep_values)
        command = self.deployment["spec.template.spec.containers.0.command"]
        assert command[3] == "http://external-config.bla"

    def test_configuration_with_http_endpoints_volume_mount_is_not_populated(self):
        logprep_values = {
            "configurations": [
                {"name": "config1", "data": {"process_count": 2}},
                {"name": "http://external-config.bla"},
            ]
        }
        self.manifests = self.render_chart("logprep", logprep_values)
        mounts = self.deployment["spec.template.spec.containers.0.volumeMounts"]
        for mount in mounts:
            if "http://external-config.bla" in mount["mountPath"]:
                assert False, "http://external-config.bla should not be there"

    def test_configuration_with_http_endpoints_configmap_entry_is_not_populated(self):
        logprep_values = {
            "configurations": [
                {"name": "config1", "data": {"process_count": 2}},
                {"name": "http://external-config.bla"},
            ]
        }
        self.manifests = self.render_chart("logprep", logprep_values)
        cm = self.manifests.by_query(
            "kind: ConfigMap AND metadata.name: logprep-logprep-configurations"
        )
        configs: dict = cm[0]["data"]
        assert "http://external-config.bla" not in configs

    def test_pod_annotations(self):
        logprep_values = {"podAnnotations": {"key1": "value1", "key2": "value2"}}
        self.manifests = self.render_chart("logprep", logprep_values)
        annotations = self.deployment["spec.template.metadata.annotations"]
        assert annotations["key1"] == "value1"
        assert annotations["key2"] == "value2"

    def test_artifacts_are_mounted(self, tmp_path):
        logprep_values = """
artifacts:
    - name: adminlist.txt
      path: artifacts/lists
      data: |
        admin1
        admin2
        adminxy
    - name: regex_mapping.yml
      data: |
        RE_WHOLE_FIELD: (.*)
        RE_DOMAIN_BACKSLASH_USERNAME: \w+\\(.*)
        RE_IP4_COLON_PORT: ([\d.]+):\d+
        RE_ALL_NO_CAP: .*
"""
        logprep_values_file: Path = tmp_path / "values.yaml"
        logprep_values_file.write_text(logprep_values)
        logprep_values = GetterFactory.from_string(str(logprep_values_file)).get_yaml()
        self.manifests = self.render_chart("logprep", logprep_values)
        mounts = self.deployment["spec.template.spec.containers.0.volumeMounts"]
        artifact_mounts = [mount for mount in mounts if mount["name"] == "artifacts"]
        assert len(artifact_mounts) == 2
        mount_paths = [mount["mountPath"] for mount in artifact_mounts]
        assert "/home/logprep/regex_mapping.yml" in mount_paths
        assert "/home/logprep/artifacts/lists/adminlist.txt" in mount_paths

    def test_artifacts_are_populated(self, tmp_path):
        logprep_values = """
artifacts:
    - name: adminlist.txt
      path: artifacts/lists
      data: |
        admin1
        admin2
        adminxy
    - name: regex_mapping.yml
      data: |
        RE_WHOLE_FIELD: (.*)
        RE_DOMAIN_BACKSLASH_USERNAME: \w+\\(.*)
        RE_IP4_COLON_PORT: ([\d.]+):\d+
        RE_ALL_NO_CAP: .*
"""
        logprep_values_file: Path = tmp_path / "values.yaml"
        logprep_values_file.write_text(logprep_values)
        logprep_values = GetterFactory.from_string(str(logprep_values_file)).get_yaml()
        self.manifests = self.render_chart("logprep", logprep_values)
        config_map = self.manifests.by_query(
            "kind: ConfigMap AND metadata.name: logprep-logprep-artifacts"
        )[0]
        assert config_map
        assert config_map["data"]["adminlist.txt"]
        assert config_map["data"]["regex_mapping.yml"]
        assert "adminxy" in config_map["data"]["adminlist.txt"]
        assert "RE_DOMAIN_BACKSLASH_USERNAME" in config_map["data"]["regex_mapping.yml"]

    def test_artifacts_volume_definition(self):
        logprep_values = {"artifacts": [{"name": "adminlist.txt", "data": "admin1\n"}]}
        self.manifests = self.render_chart("logprep", logprep_values)
        volumes = self.deployment["spec.template.spec.volumes"]
        artifacts_volume = [volume for volume in volumes if volume["name"] == "artifacts"]
        assert len(artifacts_volume) == 1
        artifacts_volume = artifacts_volume[0]
        assert artifacts_volume["configMap"]["name"] == "logprep-logprep-artifacts"

    def test_artifacts_volume_not_populated_if_not_defined(self):
        logprep_values = {"artifacts": []}
        self.manifests = self.render_chart("logprep", logprep_values)
        volumes = self.deployment["spec.template.spec.volumes"]
        artifacts_volume = [volume for volume in volumes if volume["name"] == "artifacts"]
        assert len(artifacts_volume) == 0

    def test_environment_variables_are_populated(self):
        logprep_values = {
            "environment": [
                {"name": "MY_VAR", "value": "my_value"},
                {"name": "MY_OTHER_VAR", "value": "my_other_value"},
            ]
        }
        self.manifests = self.render_chart("logprep", logprep_values)
        env = self.deployment["spec.template.spec.containers.0.env"]
        my_var = [variable for variable in env if variable["name"] == "MY_VAR"].pop()
        assert my_var["value"] == "my_value"
        my_var = [variable for variable in env if variable["name"] == "MY_OTHER_VAR"].pop()
        assert my_var["value"] == "my_other_value"

    def test_environment_variables_populated_from_secrets(self):
        logprep_values = {
            "environment": [
                {
                    "name": "MY_VAR",
                    "value": "my_value",
                },
                {
                    "name": "MY_OTHER_VAR",
                    "valueFrom": {"secretKeyRef": {"name": "my-secret", "key": "my-key"}},
                },
            ]
        }
        self.manifests = self.render_chart("logprep", logprep_values)
        env = self.deployment["spec.template.spec.containers.0.env"]
        my_var = [variable for variable in env if variable["name"] == "MY_VAR"].pop()
        assert my_var["value"] == "my_value"
        my_var = [variable for variable in env if variable["name"] == "MY_OTHER_VAR"].pop()
        assert my_var["valueFrom"]["secretKeyRef"]["name"] == "my-secret"

    def test_extra_volumes_are_populated(self):
        logprep_values = {
            "extraVolumes": [
                {
                    "name": "my-volume",
                    "configMap": {"name": "my-configmap"},
                },
                {
                    "name": "my-volume2",
                    "configMap": {"name": "my-configmap"},
                },
            ]
        }
        self.manifests = self.render_chart("logprep", logprep_values)
        volumes = self.deployment["spec.template.spec.volumes"]
        volume = [volume for volume in volumes if volume["name"] == "my-volume"].pop()
        assert volume["configMap"]["name"] == "my-configmap"

    def test_extra_mounts_are_populated(self):
        logprep_values = {
            "extraMounts": [
                {
                    "name": "my-volume",
                    "mountPath": "/my-path",
                },
                {
                    "name": "my-volume2",
                    "mountPath": "/my-path2",
                    "subPath": "sub-path",
                },
            ]
        }
        self.manifests = self.render_chart("logprep", logprep_values)
        mounts = self.deployment["spec.template.spec.containers.0.volumeMounts"]
        mount = [mount for mount in mounts if mount["name"] == "my-volume"].pop()
        assert mount["mountPath"] == "/my-path"
        mount = [mount for mount in mounts if mount["name"] == "my-volume2"].pop()
        assert mount["subPath"] == "sub-path"

    def test_logprep_cache_dir_is_populated(self):
        volumes = self.deployment["spec.template.spec.volumes"]
        cache_dir_volume = [
            volume for volume in volumes if volume["name"] == "logprep-cache-dir"
        ].pop()
        assert cache_dir_volume
        assert cache_dir_volume["emptyDir"] == {"medium": "Memory"}
        mounts = self.deployment["spec.template.spec.containers.0.volumeMounts"]
        cache_dir_mount = [mount for mount in mounts if mount["name"] == "logprep-cache-dir"].pop()
        assert cache_dir_mount
        assert cache_dir_mount["mountPath"] == "/home/logprep/.cache"
