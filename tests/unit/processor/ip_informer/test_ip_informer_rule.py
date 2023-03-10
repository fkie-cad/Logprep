# pylint: disable=protected-access
# pylint: disable=missing-docstring
import pytest
from logprep.processor.ip_informer.rule import IpInformerRule


class TestIpInformerRule:
    def test_create_from_dict_returns__rule(self):
        rule = {
            "filter": "message",
            "ip_informer": {"source_fields": ["message"], "target_field": "new_field"},
        }
        rule_dict = IpInformerRule._create_from_dict(rule)
        assert isinstance(rule_dict, IpInformerRule)

    @pytest.mark.parametrize(
        ["rule", "error", "message"],
        [
            (
                {
                    "filter": "message",
                    "ip_informer": {"source_fields": ["message"], "target_field": "result"},
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "ip_informer": {
                        "source_fields": ["message"],
                        "target_field": "result",
                        "properties": ["is_loopback"],
                    },
                },
                None,
                None,
            ),
            (
                {
                    "filter": "message",
                    "ip_informer": {
                        "source_fields": ["message"],
                        "target_field": "result",
                        "properties": ["not_a_property"],
                    },
                },
                ValueError,
                "must be in",
            ),
        ],
    )
    def test_create_from_dict_validates_config(self, rule, error, message):
        if error:
            with pytest.raises(error, match=message):
                IpInformerRule._create_from_dict(rule)
        else:
            rule_instance = IpInformerRule._create_from_dict(rule)
            assert hasattr(rule_instance, "_config")
            for key, value in rule.get("ip_informer").items():
                assert hasattr(rule_instance._config, key)
                assert value == getattr(rule_instance._config, key)
