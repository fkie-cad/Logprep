"""
FieldManager
============

The `field_manager` processor copies or moves field from multiple source fields to one target field.
Additionaly it can be used to merge lists or simple values from source fields to
one target field list.

A speaking example:

..  code-block:: yaml
    :linenos:
    :caption: Given field_manager rule

    filter: client.ip
    field_manager:
        source_fields:
            - client.ip
            - destination.ip
            - host.ip
            - observer.ip
            - server.ip
            - source.ip
            - server.nat.ip
            - client.nat.ip
        target_field: related.ip
        extend_target_list: True
    description: '...'

..  code-block:: json
    :linenos:
    :caption: Incoming event

    {
        "client": {"ip": ["127.0.0.1", "fe89::", "192.168.5.1"], "nat": {"ip": "223.2.3.2"}},
        "destination": {"ip": "8.8.8.8"},
        "host": {"ip": ["192.168.5.1", "180.22.66.3"]},
        "observer": {"ip": "10.10.2.33"},
        "server": {"ip": "10.10.2.33", "nat": {"ip": "180.22.66.1"}},
        "source": {"ip": "10.10.2.33"}
    }

..  code-block:: json
    :linenos:
    :caption: Processed event

    {
        "client": {"ip": ["127.0.0.1", "fe89::", "192.168.5.1"], "nat": {"ip": "223.2.3.2"}},
        "destination": {"ip": "8.8.8.8"},
        "host": {"ip": ["192.168.5.1", "180.22.66.3"]},
        "observer": {"ip": "10.10.2.33"},
        "server": {"ip": "10.10.2.33", "nat": {"ip": "180.22.66.1"}},
        "source": {"ip": "10.10.2.33"},
        "related": {
            "ip": [
                "10.10.2.33",
                "127.0.0.1",
                "180.22.66.1",
                "180.22.66.3",
                "192.168.5.1",
                "223.2.3.2",
                "8.8.8.8",
                "fe89::"
            ]
        }
    }


.. autoclass:: logprep.processor.field_manager.rule.FieldManagerRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

Examples for field_manager:
------------------------------------------------

.. datatemplate:import-module:: tests.unit.processor.field_manager.test_field_manager
   :template: testcase-renderer.tmpl

"""
from functools import partial
from attrs import define, field, validators
from logprep.util.validators import min_len_validator
from logprep.processor.base.rule import Rule


class FieldManagerRule(Rule):
    """Interface for a simple Rule with source_fields and target_field"""

    @define(kw_only=True)
    class Config(Rule.Config):
        """Config for FieldManagerRule"""

        source_fields: list = field(
            validator=[
                validators.instance_of(list),
                validators.deep_iterable(member_validator=validators.instance_of(str)),
                partial(min_len_validator, min_length=1),
            ]
        )
        """The fields from where to get the values which should be processed"""
        target_field: str = field(validator=validators.instance_of(str))
        """The field where to write the processed values to"""
        delete_source_fields: str = field(validator=validators.instance_of(bool), default=False)
        """Whether to delete all the source fields or not. Defaults to :code:`False`"""
        overwrite_target: str = field(validator=validators.instance_of(bool), default=False)
        """Overwrite the target field value if exists. Defaults to :code:`False`"""
        extend_target_list: bool = field(validator=validators.instance_of(bool), default=False)
        """If the target field exists and is a list, the list will be extended with the values
        of the source fields. If the source field is a list, the lists will be merged.
        If the target field does not exist, a new field will be added with the
        source field value as list. Defaults to :code:`False`.
        """

    # pylint: disable=missing-function-docstring
    @property
    def delete_source_fields(self):
        if hasattr(self, "_config"):
            return self._config.delete_source_fields
        return False

    @property
    def source_fields(self):
        if hasattr(self, "_config"):
            return self._config.source_fields
        return []

    @property
    def target_field(self):
        return self._config.target_field

    @property
    def overwrite_target(self):
        return self._config.overwrite_target

    @property
    def extend_target_list(self):
        return self._config.extend_target_list

    # pylint: enable=missing-function-docstring
