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

from attrs import define, field, validators
from logprep.processor.base.rule import Rule

class IpInformerRule(Rule):
    """..."""

    @define(kw_only=True)
    class Config(Rule.Config):
        """Config for IpInformerRule"""
        ...