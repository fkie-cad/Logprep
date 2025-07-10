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

from logprep.ng.processor.field_manager.processor import FieldManager
from logprep.processor.replacer.rule import ReplacerRule, ReplacementTemplate, Replacement
from logprep.util.helper import add_fields_to, get_dotted_field_value


class Replacer(FieldManager):
    """A processor that replaces parts of a string via templates defined in rules."""

    rule_class = ReplacerRule

    def _apply_rules(self, event: dict, rule: ReplacerRule) -> None:
        for source_field in rule.mapping:
            template = rule.templates.get(source_field)
            if template is None:
                continue

            value_to_replace = get_dotted_field_value(event, source_field)
            if value_to_replace is None and not rule.ignore_missing_fields:
                error = BaseException(f"replacer: mapping field '{source_field}' does not exist")
                self._handle_warning_error(event, rule, error)
            value_to_replace = str(value_to_replace)

            if not value_to_replace.startswith(template.prefix):
                continue

            result = self.replace_by_templates(template, value_to_replace)

            if result is not None:
                target = rule.target_field if rule.target_field else source_field
                add_fields_to(event, {target: result}, rule, overwrite_target=rule.overwrite_target)

    @staticmethod
    def replace_by_templates(template: ReplacementTemplate, to_replace: str) -> str | None:
        """Replace parts of `to_replace` by strings defined in `template`."""
        first_replacement = template.replacements[0]
        result = "" if first_replacement.keep_original else template.prefix
        if first_replacement.match:
            if not to_replace.startswith(template.prefix + first_replacement.match):
                return None
            result += first_replacement.match

        replacement: Replacement | None
        for idx, replacement in enumerate(template.replacements):
            replacement = Replacer._handle_wildcard(replacement, to_replace)
            if replacement is None:
                return None

            if replacement.match:
                pre, match, _ = result.rpartition(replacement.match)
                if not match:
                    return None
                result = pre + replacement.value + replacement.next
                continue

            if not replacement.next:
                result += replacement.value
                break

            _, separator, to_replace = to_replace.partition(replacement.next)
            if not separator:
                return None

            if replacement.greedy:
                to_replace = Replacer._partition_greedily(replacement, to_replace)

            if idx == len(template.replacements) - 1 and not replacement.next.endswith(to_replace):
                return None

            result += replacement.value + replacement.next

        return result

    @staticmethod
    def _partition_greedily(replacement: Replacement, to_replace: str) -> str:
        """Ensure to replace as much as possible if next is contained in string to replace"""
        last_index = to_replace.rfind(replacement.next)
        return to_replace[last_index + len(replacement.next) :] if last_index != -1 else to_replace

    @staticmethod
    def _handle_wildcard(replacement: Replacement, to_replace: str) -> Replacement | None:
        """Do not replace anything if replacement value is `*`.

        This is used to match a variable string without having to replace it.
        A pattern consisting of a single `*` can be escaped with a backslash to replace with `*`.
        Other patterns require no escaping of `*`.
        """
        if replacement.keep_original:
            if replacement.greedy:
                match_idx = to_replace.rfind(replacement.next)
            else:
                match_idx = to_replace.find(replacement.next)
            if match_idx < 0:
                return None
            original = to_replace[:match_idx] if match_idx else to_replace
            return Replacement(
                original,
                replacement.next,
                replacement.match,
                replacement.keep_original,
                replacement.greedy,
            )
        return replacement
