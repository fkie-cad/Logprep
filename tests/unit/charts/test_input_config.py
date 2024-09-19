# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access


from logprep.util.configuration import yaml
from tests.unit.charts.test_base import TestBaseChartTest

http_input_config = {
    "type": "http_input",
    "message_backlog_size": 150,
    "collect_meta": True,
    "metafield_name": "@metadata",
    "uvicorn_config": {
        "host": "0.0.0.0",
        "port": 9999,
        "workers": 2,
        "access_log": True,
        "server_header": False,
        "date_header": False,
    },
    "endpoints": {
        "/auth-json": "json",
        "/json": "json",
        "/lab/123/(ABC|DEF)/pl.*": "plaintext",
        "/lab/123/ABC/auditlog": "jsonl",
    },
}


class TestInputConfig(TestBaseChartTest):

    def test_input_config_file_is_set(self):
        logprep_values = {
            "input": {
                "documents": [],
                "type": "dummy_input",
            }
        }
        expected_input_config = {
            "input": {
                "dummy": {
                    "documents": [],
                    "type": "dummy_input",
                }
            }
        }
        self.manifests = self.render_chart("logprep", logprep_values)
        expected_input_config = yaml.dump(expected_input_config)
        input_config = self.manifests.by_query(
            "kind: ConfigMap AND metadata.name: logprep-logprep-input"
        )
        assert input_config
        input_config = input_config[0]
        assert input_config["data"]["input-config.yaml"] == expected_input_config

    def test_deployment_mounts_input_config(self):
        deployment = self.manifests.by_query("kind: Deployment")[0]
        volume_mounts = deployment["spec.template.spec.containers"][0]["volumeMounts"]
        volume_mount = [mount for mount in volume_mounts if mount["name"] == "input-config"][0]
        assert volume_mount
        assert volume_mount["mountPath"] == "/home/logprep/input-config.yaml"
        assert volume_mount["subPath"] == "input-config.yaml"

    def test_input_config_volume_is_populated(self):
        deployment = self.manifests.by_query("kind: Deployment")[0]
        exporter_config = self.manifests.by_query(
            "kind: ConfigMap AND metadata.name: logprep-logprep-input"
        )
        exporter_config_name = exporter_config[0]["metadata"]["name"]
        volumes = deployment["spec.template.spec.volumes"]
        volume = [vol for vol in volumes if vol["name"] == "input-config"][0]
        assert volume
        assert volume["configMap"]["name"] == exporter_config_name

    def test_input_config_is_used_to_start_logprep(self):
        container = self.deployment["spec.template.spec.containers"][0]
        volume_mounts = container["volumeMounts"]
        volume_mount = [mount for mount in volume_mounts if mount["name"] == "input-config"][0]
        assert volume_mount["subPath"] in " ".join(container["command"])

    def test_http_input_config_service_is_created(self):
        self.manifests = self.render_chart("logprep", {"input": http_input_config})
        service = self.manifests.by_query(
            "kind: Service AND metadata.name: logprep-logprep-http-input"
        )
        assert service
        assert service[0]["spec"]["ports"][0]["port"] == 9999
        assert service[0]["spec"]["ports"][0]["targetPort"] == 9999

    def test_http_input_config_sets_deployment_port(self):
        self.manifests = self.render_chart("logprep", {"input": http_input_config})
        ports = self.deployment["spec.template.spec.containers"][0]["ports"]
        for port in ports:
            if port["name"] == "http-input":
                assert port["containerPort"] == 9999
                break
        else:
            assert False, "http-input port not found"
