# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access


from tests.unit.charts.test_base import TestBaseChartTest


class TestIngressGateway(TestBaseChartTest):

    def test_ingress_gateway_is_rendered(self):
        logprep_values = {"ingress": {"enabled": True}}
        self.manifests = self.render_chart("logprep", logprep_values)
        ingress_gateway = self.manifests.by_query(
            "kind: Gateway AND apiVersion: networking.istio.io/v1alpha3"
        )
        assert ingress_gateway
        assert len(ingress_gateway) == 1
        ingress_gateway = ingress_gateway[0]
        assert ingress_gateway["metadata"]["name"] == "logprep-logprep"

    def test_ingress_gateway_is_not_rendered(self):
        logprep_values = {"ingress": {"enabled": False}}
        self.manifests = self.render_chart("logprep", logprep_values)
        ingress_gateway = self.manifests.by_query(
            "kind: Gateway AND apiVersion: networking.istio.io/v1alpha3"
        )
        assert not ingress_gateway
