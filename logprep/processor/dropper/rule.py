"""
Dropper
=======

Which fields are removed is defined in the additional field :code:`drop`.
It contains a list of fields in dot notation.
For nested fields all subfields are also removed if they are empty.
If only the specified subfield should be removed, then this can be achieved by setting
the option :code:`drop_full: false`.

In the following example the field :code:`keep_me.drop_me` is deleted while
the fields :code:`keep_me` and :code:`keep_me.keep_me_too` are kept.

..  code-block:: yaml
    :linenos:
    :caption: Example - Rule

    filter: keep_me.drop_me
    dropper:
        drop:
        - keep_me.drop_me

..  code-block:: json
    :linenos:
    :caption: Example - Input document

    [{
        "keep_me": {
            "drop_me": "something",
            "keep_me_too": "something"
        }
    }]

..  code-block:: json
    :linenos:
    :caption: Example - Expected output after application of the rule

    [{
        "keep_me": {
            "keep_me_too": "something"
        }
    }]
"""

from typing import List
import warnings
from attrs import define, field, validators

from logprep.processor.base.rule import Rule
from logprep.util.helper import pop_dotted_field_value, add_and_overwrite


class DropperRule(Rule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(Rule.Config):
        """RuleConfig for DropperRule"""

        drop: list = field(validator=validators.instance_of(list))
        """List of fields to drop"""
        drop_full: bool = field(validator=validators.instance_of(bool), default=True)
        """Drop recursive? defaults to [True]"""

    @classmethod
    def normalize_rule_dict(cls, rule: dict) -> None:
        if rule.get("dropper") is None:
            drop_fields = pop_dotted_field_value(rule, "drop")
            if drop_fields is not None:
                add_and_overwrite(rule, "dropper.drop", drop_fields)
                warnings.warn("drop is deprecated. Use dropper.drop instead", DeprecationWarning)
            drop_full = pop_dotted_field_value(rule, "drop_full")
            if drop_full is not None:
                add_and_overwrite(rule, "dropper.drop_full", drop_full)
                warnings.warn(
                    "drop_full is deprecated. Use dropper.drop_full instead", DeprecationWarning
                )

    @property
    def fields_to_drop(self) -> List[str]:
        """Returns fields_to_drop"""
        return self._config.drop

    @property
    def drop_full(self) -> bool:
        """Returns drop_full"""
        return self._config.drop_full
