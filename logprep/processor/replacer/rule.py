r"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

A speaking example:

..  code-block:: yaml
    :linenos:
    :caption: Given replacer rule

    filter: message
    replacer:
        mapping:
            message: "Message %{*} was created by user %{USER_ID}."
    description: '...'

..  code-block:: json
    :linenos:
    :caption: Incoming event

    {"message": "Message 123 was created by user 456."}

..  code-block:: json
    :linenos:
    :caption: Processed event

    { "message": "Message 123 was created by user USER_ID." }


.. autoclass:: logprep.processor.replacer.rule.ReplacerRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

Replacement Pattern Language
----------------------------

The replacement pattern describes the textual format of the source field.

Given a replacement pattern of :code:`%{replaced_1}and%{replaced_2}` the source field value
will be replaced with a value where everything before :code:`and` will be replaced with
:code:`replaced_1` and everything after :code:`and` will be replaced with :code:`replaced_2`.

The string between :code:`%{` and :code:`}` is the desired replacement value.

The special replacement value :code:`%{*}` acts as a wildcard that allows to match a string without
replacing it.
If you want to use the symbol :code:`*` as a replacement value, you have to escape it with
:code:`\\` (e.g. :code:`%{\\*}`).
:code:`*` does not have to be escaped if it occurs in combination with other values
(e.g. :code:`%{**}` or :code:`%{foo*}`).
The exception is if a single wildcard gets escaped multiple times
(e.g. :code:`%{\\\\*}` becomes :code:`\\*` and :code:`%{\\\\\\*}` becomes :code:`\\\\*`).

An empty replacement value :code:`%{}` will remove the matching parts from the new value.

.. autoclass:: logprep.processor.dissector.rule.DissectorRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

Examples for replacer:
------------------------------------------------

.. datatemplate:import-module:: tests.unit.processor.replacer.test_replacer
   :template: testcase-renderer.tmpl

"""

from typing import NamedTuple, List

from attrs import define, field, validators

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.base.rule import Rule
from logprep.processor.field_manager.rule import FieldManagerRule

REPLACEMENT_PATTERN = r".*%{.*}.*"

START = "%{"
END = "}"


class Replacement(NamedTuple):
    value: str
    next: str
    is_wildcard: bool


class ReplacementTemplate(NamedTuple):
    prefix: str
    replacements: List[Replacement]


class ReplacerRule(FieldManagerRule):
    """replacer rule"""

    @define(kw_only=True)
    class Config(Rule.Config):
        """Config for ReplacerRule"""

        mapping: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.min_len(1),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.matches_re(REPLACEMENT_PATTERN),
                ),
            ]
        )
        """A mapping of fieldnames to patterns to replace"""

    def __init__(
        self, filter_rule: FilterExpression, config: "ReplacerRule.Config", processor_name: str
    ):
        super().__init__(filter_rule, config, processor_name)
        self.templates = {}
        for source, template in self._config.mapping.items():
            self.templates[source] = self._get_replacement_strings(template)

    @staticmethod
    def _get_replacement_strings(template):
        first = ""
        end = ""
        replacements = []
        idx = 0
        while template:
            pre_start, _, post_start = template.partition(START)
            if idx == 0:
                first = pre_start
            pre_end, end_part, post_end = post_start.partition(END)
            if end_part:
                replacement = pre_end
                if idx > 0:
                    replacements[idx - 1].append(pre_start)
                replacements.append([replacement])
            else:
                end = template
            template = post_end
            idx += 1

        if replacements:
            replacements[-1].append(end)

        replacements = ReplacerRule._get_replacements_with_wildcard_state(replacements)
        ReplacerRule._unescape_single_star_symbol(replacements)
        replacements = [Replacement(**replacement) for replacement in replacements]

        return ReplacementTemplate(first, replacements)

    @staticmethod
    def _get_replacements_with_wildcard_state(replacements: list):
        replacements_with_wildcard_state = []
        for value, replace_next in replacements:
            replacements_with_wildcard_state.append(
                {"value": value, "next": replace_next, "is_wildcard": value == "*"}
            )
        return replacements_with_wildcard_state

    @staticmethod
    def _unescape_single_star_symbol(replacements: list):
        for replacement in replacements:
            if not replacement["is_wildcard"] and replacement["value"].endswith("*"):
                pre_wildcard = replacement["value"][:-1]
                if pre_wildcard == len(pre_wildcard) * "\\":
                    replacement["value"] = replacement["value"][1:]
