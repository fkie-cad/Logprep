"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

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
        merge_with_target: True
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

from attrs import define, field, validators

from logprep.processor.base.rule import Rule
from logprep.util.helper import get_dotted_field_value

FIELD_PATTERN = r"\$\{([+&?]?[^${}]*)\}"


class FieldManagerRule(Rule):
    """Interface for a simple Rule with source_fields and target_field"""

    @define(kw_only=True)
    class Config(Rule.Config):
        """Config for FieldManagerRule"""

        source_fields: list = field(
            validator=[
                validators.instance_of(list),
                validators.deep_iterable(member_validator=validators.instance_of(str)),
            ],
            default=[],
        )
        """The fields from where to get the values which should be processed, requires
        :code:`target_field`."""
        target_field: str = field(validator=validators.instance_of(str), default="")
        """The field where to write the processed values to. Can be used to move/copy single values,
        merge multiple values to one list or extend a list. Requires :code:`source_field`."""
        mapping: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.instance_of(str),
                ),
            ],
            default={},
        )
        """A key-value mapping from source fields to target fields. Can be used to copy/move
        multiple fields at once. If you want to move fields set :code:`delete_source_fields` to
        true. Works independent of :code:`source_fields` and :code:`target_field`."""
        delete_source_fields: bool = field(validator=validators.instance_of(bool), default=False)
        """Whether to delete all the source fields or not. Defaults to :code:`False`"""
        overwrite_target: bool = field(validator=validators.instance_of(bool), default=False)
        """Overwrite the target field value if exists. Defaults to :code:`False`"""
        merge_with_target: bool = field(validator=validators.instance_of(bool), default=False)
        """If the target field exists and is a list, the list will be extended with the values
        of the source fields. If the source field is a list, the lists will be merged by appending
        the source fields list to the target list. If the source field is a dict, the dict will be
        merged with the target dict. If the source keys exist in the target dict, the values will be
        overwritten. So this is not e deep merge.
        If the target field does not exist, a new field will be added with the
        source field value as list or dict. Defaults to :code:`False`.
        """
        ignore_missing_fields: bool = field(validator=validators.instance_of(bool), default=False)
        """If set to :code:`True` missing fields will be ignored, no warning is logged and the event
        is not tagged with the failure tag. Defaults to :code:`False`"""

        def __attrs_post_init__(self):
            # ensures no split operations during processing
            for dotted_field in self.source_fields:  # pylint: disable=not-an-iterable
                get_dotted_field_value({}, dotted_field)
            get_dotted_field_value({}, self.target_field)

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
    def mapping(self):
        return self._config.mapping

    @property
    def overwrite_target(self):
        return self._config.overwrite_target

    @property
    def merge_with_target(self):
        return self._config.merge_with_target

    @property
    def ignore_missing_fields(self):
        return self._config.ignore_missing_fields

    # pylint: enable=missing-function-docstring
