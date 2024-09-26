"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

The pseudonymizer requires the additional field :code:`pseudonymizer.mapping`.
It contains key value pairs that define what will be pseudonymized.

They key represents the field that will be pseudonymized and the value contains a regex keyword.
The regex keyword defines which parts of the value are being pseudonymized.
Only the regex matches are being pseudonymized that are also in a capture group.
An arbitrary amount of capture groups can be used.
The definitions of regex keywords are located in a separate file.

In the following the field :code:`event_data.param1` is being completely pseudonymized.
This is achieved by using the predefined keyword :code:`RE_WHOLE_FIELD`,
which will be resolved to a regex expression.
:code:`RE_WHOLE_FIELD` resolves to :code:`(.*)` which puts the whole match
in a capture group and therefore pseudonymizes it completely.

..  code-block:: yaml
    :linenos:
    :caption: Example - Rule

    filter: 'event_id: 1 AND source_name: "Test"'
    pseudonymizer:
        mapping:
            event_data.param1: RE_WHOLE_FIELD
    description: '...'

..  code-block:: json
    :linenos:
    :caption: Example - Regex mapping file

    {
      "RE_WHOLE_FIELD": "(.*)",
      "RE_DOMAIN_BACKSLASH_USERNAME": "\\w+\\\\(.*)",
      "RE_IP4_COLON_PORT": "([\\d.]+):\\d+"
    }

.. autoclass:: logprep.processor.pseudonymizer.rule.PseudonymizerRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:
"""

import re
from typing import List

from attrs import define, field, validators

from logprep.processor.field_manager.rule import FieldManagerRule


class PseudonymizerRule(FieldManagerRule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """RuleConfig for Pseudonymizer"""

        mapping: dict = field(
            validator=[
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.instance_of((str, re.Pattern)),
                ),
                validators.min_len(1),
            ]
        )
        """mapping of field to regex string"""
        url_fields: list = field(
            validator=[
                validators.deep_iterable(
                    member_validator=validators.instance_of((str, type(None)))
                ),
            ],
            factory=list,
        )
        """url fields to pseudonymize"""

    # pylint: disable=C0111
    @property
    def pseudonyms(self) -> dict[str, re.Pattern]:
        return self._config.mapping

    @property
    def url_fields(self) -> List[str]:
        return self._config.url_fields

    # pylint: enable=C0111
