"""
Replacer
============

The `replacer` is a processor that replaces parts of a string with strings defined in rules.

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - samplename:
        type: replacer
        rules:
            - tests/testdata/rules/

.. autoclass:: logprep.processor.replacer.processor.Replacer.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.replacer.rule
"""

from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.replacer.rule import ReplacerRule, ReplacementTemplate, Replacement
from logprep.util.helper import add_fields_to


class Replacer(FieldManager):
    """A processor that replaces parts of a string via templates defined in rules."""

    rule_class = ReplacerRule

    def _apply_rules(self, event: dict, rule: ReplacerRule):
        for source_field in rule.mapping:
            template = rule.templates.get(source_field)
            if template is None:
                continue

            value_to_replace = str(event.get(source_field))
            if not value_to_replace.startswith(template.prefix):
                continue

            result = self.replace_by_templates(template, value_to_replace)

            if result is not None:
                add_fields_to(event, {source_field: result}, rule, overwrite_target=True)

    @staticmethod
    def replace_by_templates(template: ReplacementTemplate, to_replace: str):
        """Replace parts of `to_replace` by strings defined in `template`."""
        result = ""
        if template.prefix and not template.replacements[0].is_wildcard:
            result = template.prefix

        for idx, replacement in enumerate(template.replacements):
            replacement = Replacer._handle_wildcard(replacement, to_replace)
            if replacement is None:
                return None

            if replacement.next == "":
                return result + replacement.value

            _, delimiter, to_replace = to_replace.partition(replacement.next)
            if delimiter == "":
                return None

            # Ensure to replace as much as possible if next is contained in string to replace
            while to_replace != replacement.next and replacement.next in to_replace:
                _, delimiter, to_replace = to_replace.partition(replacement.next)

            if idx == len(template.replacements) - 1 and not replacement.next.endswith(to_replace):
                return None

            result += replacement.value + replacement.next

        return result

    @staticmethod
    def _handle_wildcard(replacement: Replacement, to_replace: str):
        """Do not replace anything if replacement value is `*`.

        This is used to match a variable string without having to replace it.
        A pattern consisting of a single `*` can be escaped with a backslash to replace with `*`.
        Other patterns require no escaping of `*`.
        """
        if replacement.is_wildcard:
            match_idx = to_replace.find(replacement.next)
            if match_idx < 0:
                return None
            original = to_replace[:match_idx] if match_idx else to_replace
            return Replacement(original, replacement.next, replacement.is_wildcard)
        return replacement
