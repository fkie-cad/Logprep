"""
Pseudonymizer
=============

The pseudonymizer requires the additional field :code:`pseudonymizer.pseudonyms`.
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
        pseudonyms:
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

"""

from typing import List
import warnings
from attrs import define, field, validators

from logprep.util.helper import pop_dotted_field_value, add_and_overwrite
from logprep.processor.base.rule import Rule


class PseudonymizeRule(Rule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(Rule.Config):
        """RuleConfig for Pseudonymizer"""

        pseudonyms: dict = field(
            validator=validators.deep_mapping(
                key_validator=validators.instance_of(str),
                value_validator=validators.instance_of(str),
            )
        )
        """mapping of field to regex string"""
        url_fields: list = field(
            validator=validators.deep_iterable(member_validator=validators.instance_of(str)),
            factory=list,
        )
        """url fields to pseudonymize"""

    @classmethod
    def normalize_rule_dict(cls, rule):
        if rule.get("pseudonymizer", {}).get("pseudonyms") is None:
            pseudonyms = pop_dotted_field_value(rule, "pseudonymize")
        if pseudonyms is not None:
            add_and_overwrite(rule, "pseudonymize.pseudonyms", pseudonyms)
            warnings.warn(
                "pseudonymize is deprecated. Use pseudonymizer.pseudonyms instead",
                DeprecationWarning,
            )
        if rule.get("pseudonymizer", {}).get("url_fields") is None:
            url_fields = pop_dotted_field_value(rule, "url_fields")
        if url_fields is not None:
            add_and_overwrite(rule, "pseudonymize.url_fields", url_fields)
            warnings.warn(
                "url_fields is deprecated. Use pseudonymizer.url_fields instead",
                DeprecationWarning,
            )

    # pylint: disable=C0111
    @property
    def pseudonyms(self) -> dict:
        return self._config.pseudonyms

    @property
    def url_fields(self) -> List[str]:
        return self._config.url_fields

    # pylint: enable=C0111
