"""
.. _generic-resolver-rule:

Generic Resolver
================

The generic resolver requires the additional field :code:`generic_resolver`.
It works similarly to the hyperscan resolver, which utilizes hyperscan to process resolve lists.
Configurable fields are being checked by regex patterns and a configurable value will be added
if a pattern matches.
The parameters within :code:`generic_resolver` must be of the form
:code:`field_mapping: {SOURCE_FIELD: DESTINATION_FIELD},
resolve_list: {REGEX_PATTERN_0: ADDED_VALUE_0, ..., REGEX_PATTERN_N: ADDED_VALUE_N}`.
SOURCE_FIELD will be checked by the regex patterns REGEX_PATTERN_[0-N] and
a new field DESTINATION_FIELD with the value ADDED_VALUE_[0-N] will be added if there is a match.
Adding the option :code:`"append_to_list": True` makes the generic resolver write resolved values
into a list so that multiple different values can be written into the same field.

In the following example :code:`to_resolve` will be checked by the regex pattern :code:`.*Hello.*`.
:code:`"resolved": "Greeting"` will be added to the event if the pattern matches
the value in :code:`to_resolve`.

..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: to_resolve
    generic_resolver:
      field_mapping:
        to_resolve: resolved
      resolve_list:
        .*Hello.*: Greeting

Alternatively, a YML file with a resolve list and a regex pattern can be used to resolve values.
For this, a field :code:`resolve_from_file` with the subfields :code:`path` and :code:`pattern`
must be added.
The resolve list in the file at :code:`path` is then used in conjunction with the regex pattern
in :code:`pattern`.
:code:`pattern` must be a regex pattern with a capture group that is named :code:`mapping`.
The resolver will check for the pattern and get value captured by the :code:`mapping` group.
This captured value is then used in the list from the file.

In the following example :code:`to_resolve` will be checked by the
regex pattern :code:`\d*(?P<mapping>[a-z]+)\d*` and the list in :code:`path/to/resolve_mapping.yml`
will be used to add new fields.
:code:`"resolved": "resolved foo"` will be added to the event if the value
in :code:`to_resolve` begins with number, ends with numbers and contains foo.
Furthermore, :code:`"resolved": "resolved bar"` will be added to the event
if the value in :code:`to_resolve` begins with number, ends with numbers and contains bar.

..  code-block:: yaml
    :linenos:
    :caption: Example resolving with list from file

    filter: to_resolve
    generic_resolver:
      field_mapping:
        to_resolve: resolved
      resolve_from_file:
        path: path/to/resolve_mapping.yml
        pattern: \d*(?P<mapping>[a-z]+)\d*

..  code-block:: yaml
    :linenos:
    :caption: Example file with resolve list

    foo: resolved foo
    bar: resolved bar

"""
from attrs import define, field, validators

from logprep.processor.base.rule import Rule


class GenericResolverRule(Rule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(Rule.Config):
        """RuleConfig for GenericResolver"""

        field_mapping: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.instance_of(str),
                ),
            ]
        )
        """Mapping in form of :code:`{SOURCE_FIELD: DESTINATION_FIELD}`"""
        resolve_list: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.instance_of(str),
                ),
            ],
            factory=dict,
        )
        """lookup mapping in form of
        :code:`{REGEX_PATTERN_0: ADDED_VALUE_0, ..., REGEX_PATTERN_N: ADDED_VALUE_N}`"""
        resolve_from_file: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.in_(["path", "pattern"]),
                    value_validator=validators.instance_of(str),
                ),
            ],
            factory=dict,
        )
        """Mapping with a `path` key to a YML file with a resolve list and a `pattern` key with
        a regex pattern which can be used to resolve values.
        The resolve list in the file at :code:`path` is then used in conjunction with
        the regex pattern in :code:`pattern`."""
        append_to_list: bool = field(validator=validators.instance_of(bool), default=False)
        """Makes the generic resolver write resolved values
        into a list so that multiple different values can be written into the same field."""

    @property
    def field_mapping(self) -> dict:
        """Returns the field mapping"""
        return self._config.field_mapping

    @property
    def resolve_list(self) -> dict:
        """Returns the resolve list"""
        return self._config.resolve_list

    @property
    def resolve_from_file(self) -> dict:
        """Returns the resolve file"""
        return self._config.resolve_from_file

    @property
    def append_to_list(self) -> bool:
        """Returns if it should append to a list"""
        return self._config.append_to_list
