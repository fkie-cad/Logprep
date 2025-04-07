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

Additionally, there exists a colon notation :code:`MATCH_VALUE:REPLACE_VALUE` to achieve more
specific results.
:code:`MATCH_VALUE` is a specific value that will be replaced and :code:`REPLACE_VALUE` is the value
it will be replaced with.
The value :code:`:` needs to be escaped with :code:`\` if it is to be used as a character.
The escaping works like sigma wildcard escaping.

:code:`foo {VAL1\:VAL2} bar` results in :code:`foo VAL1\:VAL2 bar` for input :code:`foo SOME bar`.
:code:`foo {VAL1\\:VAL2} bar` results in :code:`foo VAL2 bar` only for input :code:`foo VAL1\ bar`.

:code:`{REPLACE_VALUE}` is a shorthand for :code:`{*:REPLACE_VALUE}`.
:code:`{*}` is a shorthand for :code:`{*:*}`.

The special replacement value :code:`%{*}` acts as a wildcard that allows to match a string without
replacing it.
If you want to use the symbol :code:`*` as a replacement value, you have to escape it with
:code:`\\` (e.g. :code:`%{\\*}`).
:code:`*` does not have to be escaped if it occurs in combination with other values
(e.g. :code:`%{**}` or :code:`%{foo*}`).
The exception is if a single wildcard gets escaped multiple times
(e.g. :code:`%{\\\\*}` becomes :code:`\\*` and :code:`%{\\\\\\*}` becomes :code:`\\\\*`).

The character :code:`%{|g}` at the end of a replacement means that values will be matched greedily.
Given an input :code:`1.2.3.4.` and a pattern :code:`%{IP}.` it would replace to :code:`IP.2.3.4.`.
Given an input :code:`1.2.3.4.` and a pattern :code:`%{IP|g}.` it would replace to :code:`IP.`.

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

import re
from typing import NamedTuple, List

from attrs import define, field, validators

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.field_manager.rule import FieldManagerRule

REPLACEMENT_PATTERN = r".*%{.*}.*"

START = "%{"
END = "}"


class Replacement(NamedTuple):
    """Contains information how to replace the target text"""

    value: str
    next: str
    match: str | None
    keep_original: bool
    greedy: bool


class ReplacementTemplate(NamedTuple):
    """Contains list of Replacement tuples and prefix that should not be replaced"""

    prefix: str
    replacements: List[Replacement]


class ReplacerRule(FieldManagerRule):
    """replacer rule"""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Config for ReplacerRule"""

        source_fields: list = field(factory=list, init=False, repr=False, eq=False)
        extend_target_list: bool = field(factory=bool, init=False, repr=False, eq=False)

        target_field: str = field(default="", repr=False, eq=False)
        """The field where to write the processed values to.
        Defaults to the source fields in mapping."""
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
        overwrite_target: bool = field(validator=validators.instance_of(bool), default=True)
        """Overwrite the target field value if exists. Defaults to :code:`True`"""

    def __init__(
        self, filter_rule: FilterExpression, config: "ReplacerRule.Config", processor_name: str
    ) -> None:
        super().__init__(filter_rule, config, processor_name)
        self.templates = {}
        for source, template in self._config.mapping.items():
            self.templates[source] = self._get_replacement_strings(template)

    @staticmethod
    def _get_replacement_strings(template: str) -> ReplacementTemplate:
        prefix, replacements = ReplacerRule._get_replacements(template)
        ReplacerRule._parse_colon_notation(replacements)
        ReplacerRule._get_greedy_state(replacements)
        replacements = ReplacerRule._get_replacements_with_wildcard_state(replacements)
        ReplacerRule._unescape_single_star_symbol(replacements)
        replacements = [Replacement(**replacement) for replacement in replacements]
        return ReplacementTemplate(prefix, replacements)

    @staticmethod
    def _get_replacements(template: str) -> tuple[str, list]:
        prefix = ""
        end = ""
        replacements: list[dict] = []
        idx = 0
        while template:
            replacement: dict = {}
            pre_start, _, post_start = template.partition(START)
            if idx == 0:
                prefix = pre_start
            pre_end, end_part, post_end = post_start.partition(END)
            if end_part:
                replacement["value"] = pre_end
                if idx > 0:
                    replacements[idx - 1]["replace_next"] = pre_start
                replacements.append(replacement)
            else:
                end = template
            template = post_end
            idx += 1
        if replacements:
            replacements[-1]["replace_next"] = end
        return prefix, replacements

    @staticmethod
    def _parse_colon_notation(replacements: list[dict]) -> None:
        for idx, replacement in enumerate(replacements):
            col_pos = ReplacerRule._find_not_escaped_character(replacement["value"], ":")

            if col_pos is None:
                replacement["match"] = None
                replacement["value"] = ReplacerRule._unescape_character(replacement["value"], ":")
                continue

            replacement["match"] = ReplacerRule._get_colon_match_value(col_pos, replacement)
            replacement["value"] = ReplacerRule._get_colon_replacement_value(col_pos, replacement)

            if idx > 0:
                replacements[idx - 1]["replace_next"] += replacement["match"]

    @staticmethod
    def _get_colon_match_value(colon_pos: int, replacement: dict) -> str:
        match = replacement["value"][:colon_pos]
        match = ReplacerRule._unescape_backslashes_at_end_of_string(match)
        match = ReplacerRule._unescape_character(match, ":")

        match = None if match == "*" else match
        if match and match.endswith("*"):
            pre_wildcard = match[:-1]
            if pre_wildcard == len(pre_wildcard) * "\\":
                match = match[1:]
        return match

    @staticmethod
    def _get_colon_replacement_value(colon_pos: int, replacement: dict) -> str:
        value = replacement["value"][colon_pos + 1 :]
        return ReplacerRule._unescape_character(value, ":")

    @staticmethod
    def _unescape_character(text: str, target_character: str) -> str:
        matches = re.findall(rf"\\+{re.escape(target_character)}", text)
        for match in matches:
            pre, separator, post = text.partition(match)
            backslashes = "\\" * int((len(separator) - 2) / 2)
            text = f"{pre}{backslashes}{target_character}{post}"
        return text

    @staticmethod
    def _find_not_escaped_character(text: str, target_character: str) -> int | None:
        backslashes = 0
        for idx, char in enumerate(text):
            if char == target_character and backslashes % 2 == 0:
                return idx
            backslashes = backslashes + 1 if char == "\\" else 0
        return None

    @staticmethod
    def _get_replacements_with_wildcard_state(replacements: list[dict]) -> list[dict]:
        replacements_with_wildcard_state: list[dict] = []
        for replacement in replacements:
            replacements_with_wildcard_state.append(
                {
                    "value": replacement["value"],
                    "next": replacement["replace_next"],
                    "match": replacement["match"],
                    "keep_original": replacement["value"] == "*",
                    "greedy": replacement["greedy"],
                }
            )
        return replacements_with_wildcard_state

    @staticmethod
    def _unescape_single_star_symbol(replacements: list) -> None:
        for replacement in replacements:
            if not replacement["keep_original"] and replacement["value"].endswith("*"):
                pre_wildcard = replacement["value"][:-1]
                if pre_wildcard == len(pre_wildcard) * "\\":
                    replacement["value"] = replacement["value"][1:]

    @staticmethod
    def _get_greedy_state(replacements: list) -> None:
        for replacement in replacements:
            pipe_pos = ReplacerRule._find_not_escaped_character(replacement["value"], "|")

            if pipe_pos is None:
                replacement["greedy"] = False
                replacement["value"] = ReplacerRule._unescape_character(replacement["value"], "|")
                continue

            modifier = replacement["value"][pipe_pos + 1 :]
            value = replacement["value"][:pipe_pos]
            replacement["greedy"] = modifier == "g"

            value = ReplacerRule._unescape_backslashes_at_end_of_string(value)
            replacement["value"] = value

    @staticmethod
    def _unescape_backslashes_at_end_of_string(text: str) -> str:
        found = re.search(r"\\+$", text)
        if found:
            pre, separator, post = text.partition(found.group())
            text = pre + "\\" * int((len(separator) / 2)) + post
        return text
