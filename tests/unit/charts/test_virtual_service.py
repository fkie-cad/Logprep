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
        "port": 9000,
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


class TestIstioVirtualService(TestBaseChartTest):

    def test_virtual_service_is_rendered(self):
        logprep_values = {"ingress": {"enabled": True}, "input": http_input_config}
        self.manifests = self.render_chart("logprep", logprep_values)
        virtual_service = self.manifests.by_query(
            "kind: VirtualService AND apiVersion: networking.istio.io/v1alpha3"
        )
        assert virtual_service
        assert len(virtual_service) == 1
        virtual_service = virtual_service[0]
        assert virtual_service["metadata"]["name"] == "logprep-logprep"

    def test_virtual_service_has_endpoint_routes(self):
        logprep_values = {"ingress": {"enabled": True}, "input": http_input_config}
        self.manifests = self.render_chart("logprep", logprep_values)
        virtual_service = self.manifests.by_query(
            "kind: VirtualService AND apiVersion: networking.istio.io/v1alpha3"
        )[0]
        defined_routes = [
            route["match"][0]["uri"]["regex"] for route in virtual_service["spec.http"]
        ]
        for endpoint in http_input_config["endpoints"]:
            assert endpoint in defined_routes

    def test_virtual_service_routes_have_response_header(self):
        logprep_values = {"ingress": {"enabled": True}, "input": http_input_config}
        self.manifests = self.render_chart("logprep", logprep_values)
        virtual_service = self.manifests.by_query(
            "kind: VirtualService AND apiVersion: networking.istio.io/v1alpha3"
        )[0]
        response_headers_for_routes = [
            route["route"][0]["headers"]["response"]["set"]
            for route in virtual_service["spec.http"]
        ]
        expected_headers = {
            "Cache-Control": "no-cache",
            "Content-Security-Policy": "default-src 'none'; script-src 'self'; connect-src 'self'; img-src 'self'; style-src 'self'; frame-ancestors 'self'; form-action 'self';",
            "Cross-Origin-Resource-Policy": "same-site",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Strict-Transport-Security": "max-age=31536000; includeSubdomains",
            "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
            "X-XSS-Protection": "1; mode=block",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        }
        for headers in response_headers_for_routes:
            assert headers == expected_headers
