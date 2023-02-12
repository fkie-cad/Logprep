"""
IpInformer
============

The `ip_informer` processor ...

A speaking example:

..  code-block:: yaml
    :linenos:
    :caption: Given ip_informer rule

    filter: message
    ip_informer:
        ...
    description: '...'

..  code-block:: json
    :linenos:
    :caption: Incoming event

    <INCOMMING_EVENT>

..  code-block:: json
    :linenos:
    :caption: Processed event

    <PROCESSED_EVENT>


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

from logprep.processor.field_manager.rule import FieldManagerRule


class IpInformerRule(FieldManagerRule):
    """IpInformerRule"""
