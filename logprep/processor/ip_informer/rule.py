"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

A speaking example:

..  code-block:: yaml
    :linenos:
    :caption: Given ip_informer rule

    filter: message
    ip_informer:
        source_fields: ["ip"]
        target_field: result
    description: '...'

..  code-block:: json
    :linenos:
    :caption: Incoming event

    {"ip": "192.168.5.1"}

..  code-block:: json
    :linenos:
    :caption: Processed event

    {
        "ip": "192.168.5.1",
        "result": {
            "192.168.5.1": {
                "compressed": "192.168.5.1",
                "exploded": "192.168.5.1",
                "is_global": false,
                "is_link_local": false,
                "is_loopback": false,
                "is_multicast": false,
                "is_private": true,
                "is_reserved": false,
                "is_unspecified": false,
                "max_prefixlen": 32,
                "reverse_pointer": "1.5.168.192.in-addr.arpa",
                "version": 4
            }
        }
    }

.. autoclass:: logprep.processor.ip_informer.rule.IpInformerRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

Examples for ip_informer:
------------------------------------------------

.. datatemplate:import-module:: tests.unit.processor.ip_informer.test_ip_informer
   :template: testcase-renderer.tmpl

"""

from ipaddress import IPv4Address, IPv6Address

from attrs import define, field, validators

from logprep.processor.field_manager.rule import FieldManagerRule


def get_ip_property_names(cls):
    """Returns all property names"""
    return [
        prop_name
        for prop_name in filter(lambda x: x not in ("packed", "ipv6_mapped"), dir(cls))
        if isinstance(getattr(cls, prop_name), property)
    ]  # we have to remove the property `packed` because it is not json serializable


IP_PROPERTIES = [*get_ip_property_names(IPv4Address), *get_ip_property_names(IPv6Address)]


class IpInformerRule(FieldManagerRule):
    """IpInformerRule"""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Config for IPInformer"""

        properties: list = field(
            validator=[
                validators.instance_of(list),
                validators.deep_iterable(member_validator=validators.instance_of(str)),
                validators.deep_iterable(
                    member_validator=validators.in_(["default", *IP_PROPERTIES])
                ),
            ],
            default=["default"],
        )
        """(Optional) configures the properties to extract. Default is to extract all
        properties. Possible properties are: :code:`['compressed', 'exploded', 'is_global',
        'is_link_local', 'is_loopback', 'is_multicast', 'is_private', 'is_reserved',
        'is_unspecified', 'max_prefixlen',
        'reverse_pointer', 'version', 'compressed', 'exploded', 'ipv4_mapped', 'is_global',
        'is_link_local', 'is_loopback', 'is_multicast', 'is_private', 'is_reserved',
        'is_site_local', 'is_unspecified', 'max_prefixlen', 'reverse_pointer', 'scope_id',
        'sixtofour', 'teredo', 'version']`.

        Default is to extract all available properties. If you explicitly want to extract
        a property, which does not exist for an IPAddress
        (e.g. toredo which is only given for IPv4Addresses),
        the property will be extracted with the value :code:`False`.
        """
        mapping: dict = field(default="", init=False, repr=False, eq=False)

    @property
    def properties(self):
        """return the configured properties"""
        return self._config.properties
