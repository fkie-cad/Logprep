"""
IpInformer
============

The `ip_informer` processor is a processor to enrich events with ip information.

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


Examples for ip_informer:
------------------------------------------------

.. datatemplate:import-module:: tests.unit.processor.ip_informer.test_ip_informer
   :template: testcase-renderer.tmpl

"""

from logprep.processor.field_manager.rule import FieldManagerRule


class IpInformerRule(FieldManagerRule):
    """IpInformerRule"""
