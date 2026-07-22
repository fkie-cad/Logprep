"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

The network comparison enricher can match IPs to IP strings and networks in CIDR notation.

The network comparison enricher requires the additional field :code:`network_comparison`.
The mandatory keys under :code:`network_comparison` are :code:`source_fields`
(as list with one element) and :code:`target_field`. Former
is used to identify the field which is to be checked against the provided lists.
And the latter is used to define the parent field where the results should
be written to. Both fields can be dotted subfields.

Additionally, a list or array of lists can be provided underneath the
required field :code:`list_file_paths`.

In the following example, the field :code:`ip` will be checked against the provided list
(:code:`networks.txt`).
Assuming that the value :code:`127.0.0.1` will match the provided list,
the result of the network comparison (:code:`in_list`) will be added to the
target field :code:`network_comparison.example`.

..  code-block:: yaml
    :linenos:
    :caption: Example Rule to compare a single field against a provided list.

    filter: 'ip'
    network_comparison:
        source_fields: ['ip']
        target_field: 'network_comparison.example'
        list_file_paths:
            - lists/networks.txt
    description: '...'

.. note::

    Currently, it is not possible to check in more than one :code:`source_field` per rule.

.. autoclass:: logprep.processor.network_comparison.rule.NetworkComparisonRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:


Examples for network_comparison:
--------------------------------

.. datatemplate:import-module:: tests.unit.processor.network_comparison.test_network_comparison
   :template: testcase-renderer.tmpl

"""

from ipaddress import ip_network

from attrs import define, field, validators

from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.processor.list_comparison.rule import ListComparisonRule, ListName

# def _fix_inherited_pydoc(cls, fields):
#     cls.__doc__ = cls.bases[0].__doc__.replace("ListComparisonRule", "NetworkComparisonRule")
#     for f in fields:
#         f.__doc__ = "BLALA"
#     return fields


class NetworkComparisonRule(ListComparisonRule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """RuleConfig for NetworkComparisonRule"""

        list_file_paths: list[str] = field(
            validator=validators.deep_iterable(member_validator=validators.instance_of(str)),
            factory=list,
        )
        """List of files. For string format see :ref:`getters`.

        .. security-best-practice::
           :title: Processor - Network Comparison list file paths Memory Consumption

           Be aware that all values of the remote files were loaded into memory. Consider to avoid
           dynamic increasing lists without setting limits for Memory consumption. Additionally
           avoid loading large files all at once to avoid exceeding http body limits.

        .. security-best-practice::
           :title: Processor - Network Comparison list file paths Authenticity and Integrity

           Consider to use TLS protocol with authentication via mTLS or Oauth to ensure
           authenticity and integrity of the loaded values.

        """

        list_paths: dict[ListName, str] = field(
            validator=validators.deep_mapping(
                key_validator=validators.instance_of(ListName),
                value_validator=validators.instance_of(str),
                mapping_validator=validators.instance_of(dict),
            ),
            factory=dict,
        )
        """
        Mapping for configuring list paths with representative names.
        Keys represent the names on which results will be reported.
        Values represent the paths which populates `${LOGPREP_LIST}`.

        Example:

        ..  code-block:: yaml

            list_paths:
                BLACKLISTED_HOSTS: blacklists/malicious_hosts
            list_search_base_path: http://example.tld/api/${LOGPREP_LIST}


        .. security-best-practice::
           :title: Processor - Network Comparison list file paths Memory Consumption

           Be aware that all values of the remote files were loaded into memory. Consider to avoid
           dynamic increasing lists without setting limits for Memory consumption. Additionally
           avoid loading large files all at once to avoid exceeding http body limits.

        .. security-best-practice::
           :title: Processor - Network Comparison list file paths Authenticity and Integrity

           Consider to use TLS protocol with authentication via mTLS or Oauth to ensure
           authenticity and integrity of the loaded values.

        """

        list_search_base_path: str | None = field(
            default=None, validator=validators.optional(validators.instance_of(str))
        )
        """
        Base path used to resolve this rule's relative ``list_file_paths``.

        If unset, the processor-level ``list_search_base_path`` is used. A base path must
        be configured either on the rule or on the processor.

        The value may use getter syntax and ``string.Template`` placeholders.
        Environment variables and ``${LOGPREP_LIST}`` are resolved during setup. For
        HTTP(S) paths, unresolved placeholders are resolved from event fields during
        processing.
        """
        mapping: dict = field(default={}, init=False, repr=False, eq=False)
        ignore_missing_fields: bool = field(default=False, init=False, repr=False, eq=False)
        content_field: str | None = field(
            validator=validators.optional(validators.instance_of(str)),
            converter=lambda value: None if value == "" else value,
            default=None,
        )
        """
        Optional JSON key used to extract the list values from loaded content.

        Example:
            Given the following JSON content:

            .. code-block:: json

               {
                   "content": ["Jane", "Julia"]
               }

            Set ``content_field`` to ``"content"`` to use the value of this key
            as the comparison list.

        Note:
            Setting ``content_field`` requires mapping-like JSON content. Non-JSON
            content, or JSON content that does not resolve to a mapping, fails with an
            error.

            An empty ``content_field`` is treated as unset, so the list is expected at
            the root of the JSON content.

            Examples:
                ``content_field: ""``
                    Is converted to ``None`` and reads the list from the JSON root.

                ``content_field: null``
                    Is treated as ``None`` and reads the list from the JSON root.

                ``content_field: "content"``
                    Reads the list from the ``"content"`` key of the JSON object.
        """

        def __attrs_post_init__(self):
            if self.list_file_paths and self.list_paths:
                raise ValueError("`list_file_paths` and `list_paths` must not both be specified")
            if not self.list_file_paths and not self.list_paths:
                raise ValueError("one of `list_file_paths` or `list_paths` needs to be specified")

    def _transform_and_filter_list_element(self, elem):
        elem = super()._transform_and_filter_list_element(elem)
        if elem is not None:
            elem = ip_network(elem)
        return elem
