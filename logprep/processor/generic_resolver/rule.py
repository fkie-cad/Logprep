r"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

The generic resolver requires the additional field :code:`generic_resolver`.
Configurable fields are being checked by regex patterns and a configurable value will be added
if a pattern matches.
The parameters within :code:`generic_resolver` must be of the form
:code:`field_mapping: {SOURCE_FIELD: DESTINATION_FIELD},
resolve_list: {REGEX_PATTERN_0: ADDED_VALUE_0, ..., REGEX_PATTERN_N: ADDED_VALUE_N}`.
SOURCE_FIELD will be checked by the regex patterns REGEX_PATTERN_[0-N] and
a new field DESTINATION_FIELD with the value ADDED_VALUE_[0-N] will be added if there is a match.
Adding the option :code:`"merge_with_target": True` makes the generic resolver write resolved values
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

:code:`ignore_case` can be set to ignore the case when matching values that will be resolved.
It is disabled by default. In the following example :code:`to_resolve: heLLo` would be resolved,
since :code:`ignore_case` is set to true.

..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: to_resolve
    generic_resolver:
      field_mapping:
        to_resolve: resolved
      resolve_list:
        .*Hello.*: Greeting
      ignore_case: true

It is furthermore possible to resolve into dictionaries. In the following example
:code:`{"to_resolve": "Hello!"}` would be resolved to :code:`{"resolved": {"Greeting": "Hello"}}`.

..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: to_resolve
    generic_resolver:
      field_mapping:
        to_resolve: resolved
      resolve_list:
        .*Hello.*: {"Greeting": "Hello"}

Resolved dictionaries can be merged into existing dictionaries. In the following example
:code:`{"to": {"resolve": "Hello!"}}` would be resolved to
:code:`{"to": {"Greeting": "Hello", "resolve": "Hello!"}}`.

..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: to_resolve
    generic_resolver:
      field_mapping:
        to.resolve: to
      resolve_list:
        .*Hello.*: {"Greeting": "Hello"}

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

.. autoclass:: logprep.processor.generic_resolver.rule.GenericResolverRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:
"""

import re
from functools import cached_property
from pathlib import Path
from typing import List, Optional, Tuple, Union

from attrs import define, field, validators

from logprep.factory_error import InvalidConfigurationError
from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.util.getter import GetterFactory, RefreshableGetter


class GenericResolverRule(FieldManagerRule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
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
        resolve_list: dict = field(validator=(validators.instance_of(dict)), factory=dict)
        """lookup mapping in form of
        :code:`{REGEX_PATTERN_0: ADDED_VALUE_0, ..., REGEX_PATTERN_N: ADDED_VALUE_N}`"""
        resolve_from_file: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.in_(["path", "pattern"]),
                    value_validator=validators.instance_of(Union[str, int]),
                ),
            ],
            factory=dict,
        )
        """Mapping with a `path` key to a YML file (for string format see :ref:`getters`)
        with a resolve list and a `pattern` key with
        a regex pattern which can be used to resolve values.
        The resolve list in the file at :code:`path` is then used in conjunction with
        the regex pattern in :code:`pattern`.

        .. security-best-practice::
           :title: Processor - Generic Resolver Resolve From File Memory Consumption

           Be aware that all values of the remote file were loaded into memory. Consider to avoid
           dynamic increasing lists without setting limits for Memory consumption. Additionally
           avoid loading large files all at once to avoid exceeding http body limits.

        .. security-best-practice::
           :title: Processor - Generic Resolver Authenticity and Integrity

           Consider to use TLS protocol with authentication via mTLS or Oauth to ensure
           authenticity and integrity of the loaded values.

        """
        ignore_case: Optional[str] = field(validator=validators.instance_of(bool), default=False)
        """(Optional) Ignore case when matching resolve values. Defaults to :code:`False`."""

        additions: dict = field(default={}, eq=False, init=False)
        """Contains a dictionary of field names and values that should be added."""

        @property
        def _file_path(self):
            """Returns the file path"""
            return self.resolve_from_file.get("path")

        def __attrs_post_init__(self):
            if self._file_path:
                getter = GetterFactory.from_string(self._file_path)
                if isinstance(getter, RefreshableGetter):
                    getter.add_callback(self._add_from_path)
                self._add_from_path()

        def _add_from_path(self):
            self._raise_if_pattern_is_invalid()
            self._raise_if_file_does_not_exist()
            additions = self._get_additions()
            if self.ignore_case:
                additions = {key.upper(): value for key, value in additions.items()}
            self.additions = additions

        def _get_additions(self) -> dict:
            try:
                additions = GetterFactory.from_string(self._file_path).get_dict()
            except ValueError as error:
                raise InvalidConfigurationError(
                    f"Error loading additions from '{self._file_path}': {error}"
                ) from error
            return additions

        def _raise_if_pattern_is_invalid(self):
            if "?P<mapping>" not in self.resolve_from_file["pattern"]:
                raise InvalidConfigurationError(
                    f"Mapping group is missing in mapping file pattern! (Rule ID: '{self.id}')"
                )

        def _raise_if_file_does_not_exist(self):
            if not (self._file_path.startswith("http") or Path(self._file_path).is_file()):
                raise InvalidConfigurationError(
                    f"Additions file '{self._file_path}' not found! (Rule ID: '{self.id}')",
                )

    @property
    def field_mapping(self) -> dict:
        """Returns the field mapping"""
        return self._config.field_mapping

    @property
    def resolve_list(self) -> dict:
        """Returns the resolve list"""
        return self._config.resolve_list

    @cached_property
    def compiled_resolve_list(self) -> List[Tuple[re.Pattern, str]]:
        """Returns the resolve list with tuple pairs of compiled patterns and values"""
        return [
            (re.compile(pattern, re.I if self.ignore_case else 0), val)
            for pattern, val in self._config.resolve_list.items()
        ]

    @property
    def resolve_from_file(self) -> dict:
        """Returns the resolve file"""
        return self._config.resolve_from_file

    @property
    def ignore_case(self) -> bool:
        """Returns if the matching should be case-sensitive or not"""
        return self._config.ignore_case

    @cached_property
    def pattern(self) -> re.Pattern:
        """Pattern used to resolve from file"""
        return re.compile(f'^{self.resolve_from_file["pattern"]}$', re.I if self.ignore_case else 0)

    @property
    def additions(self) -> dict:
        """Returns additions from the resolve file"""
        return self._config.additions
