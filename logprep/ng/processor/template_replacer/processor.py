"""
TemplateReplacer
================

The `template_replacer` is a processor that can replace parts of a text field to anonymize those
parts. The replacement is based on a template file.

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - templatereplacername:
        type: template_replacer
        rules:
            - tests/testdata/rules/rules
        template: /tmp/template.yml
        pattern:
            delimiter: ","
            fields:
                - field.name.a
                - field.name.b
            allowed_delimiter_field: field.name.b
            target_field: target.field

.. autoclass:: logprep.processor.template_replacer.processor.TemplateReplacer.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.template_replacer.rule
"""

from typing import Any

from attr import define, field, validators

from logprep.ng.processor.field_manager.processor import FieldManager
from logprep.processor.template_replacer.rule import TemplateReplacerRule
from logprep.util.getter import GetterFactory
from logprep.util.helper import add_fields_to, get_dotted_field_value


class TemplateReplacerError(Exception):
    """Base class for TemplateReplacer related exceptions."""

    def __init__(self, name: str, message: str) -> None:
        super().__init__(f"TemplateReplacer ({name}): {message}")


class TemplateReplacer(FieldManager):
    """Resolve values in documents by referencing a mapping list."""

    @define(kw_only=True)
    class Config(FieldManager.Config):
        """TemplateReplacer config"""

        template: str = field(validator=validators.instance_of(str))
        """
        Path to a YML file (for path format see :ref:`getters`) with a list of replacements in the
        format `%{provider_name}-%{event_id}: %{new_message}`.
        """

        pattern: dict = field(validator=validators.instance_of(dict))
        """
        Configures how to use the template file by specifying the following subfields:

        - `delimiter` - Delimiter to use to split the template
        - `fields` - A list of dotted fields that are being checked by the template.
        - `allowed_delimiter_field` - One of the fields in the fields list can contain the
          delimiter. This must be specified here.
        - `target_field` - The field that gets replaced by the template.
        """

    __slots__ = ["_target_field", "_fields", "_mapping"]

    _target_field: str

    _fields: list

    _mapping: dict[str, Any]

    rule_class = TemplateReplacerRule

    def _apply_rules(self, event: dict, rule: TemplateReplacerRule) -> None:
        source_field_values = self._get_field_values(event, self._fields)
        if self._handle_missing_fields(event, rule, self._fields, source_field_values):
            return

        replacement = self._get_replacement_value(source_field_values)
        if replacement is not None:
            self._perform_replacement(event, replacement, rule)

    def _resolve_to_last_node(self, mapping: dict, path: list[str]) -> dict | None:
        """
        Resolves a nested dictionary by traversing the given path to last node (dict).

        Parameters
        ----------
        mapping : dict
            The dictionary to resolve keys against.
        path : list[str]
            A list of string keys forming the path to the nested value.

        Returns
        -------
        Any
            The resolved value (dict) at the end of the path, or None if resolution fails.
        """

        current: dict | None = mapping

        for key in path:
            if not isinstance(current, dict):
                return None

            current = current.get(key)

            if current is None:
                return None

        return current

    def _get_replacement_value(self, field_values: list) -> str | None:
        """
        Attempts to resolve a replacement string from a nested mapping
        using a list of field values as lookup keys.

        Parameters
        ----------
        field_values : list
            The list of field names used to traverse the internal self._mapping.

        Returns
        -------
        str or None
            The resolved replacement string if found, otherwise None.
        """

        *path, last_key = [str(field_value) for field_value in field_values]
        last_node = self._resolve_to_last_node(mapping=self._mapping, path=path)

        if not isinstance(last_node, dict):
            return None

        value = last_node.get(last_key)
        return value if isinstance(value, str) else None

    def _perform_replacement(
        self, event: dict, replacement: str, rule: TemplateReplacerRule
    ) -> None:
        """Replace the target value, but not its parent fields.

        If target field is None, then its parents could be non-dict/None and might be replaced.
        Addition is performed without replacement to prevent that.
        It fails if parents aren't dicts and succeeds otherwise.

        If target value isn't None, then it exists and its parents must be dicts.
        Therefore, they wouldn't be replaced, and we can overwrite the existing target field.
        """
        overwrite = get_dotted_field_value(event, self._target_field) is not None
        add_fields_to(
            event,
            fields={self._target_field: replacement},
            rule=rule,
            overwrite_target=overwrite,
        )

    def setup(self) -> None:
        super().setup()
        self._target_field = self._config.pattern["target_field"]
        self._fields = self._config.pattern["fields"]
        self._initialize_replacement_mapping()

    def _initialize_replacement_mapping(self) -> None:
        allow_delimiter_field = self._config.pattern["allowed_delimiter_field"]
        allow_delimiter_index = self._fields.index(allow_delimiter_field)
        self._mapping = {}
        template = GetterFactory.from_string(self._config.template).get_yaml()
        for keys_string, value in template.items():
            recombined_keys = self._recombine_keys(allow_delimiter_index, keys_string)
            try:
                self._set_value_for_recombined_keys(recombined_keys, value)
            except ValueError as error:
                raise TemplateReplacerError(
                    self.name, "template_replacer template is invalid!"
                ) from error

    def _recombine_keys(self, allow_delimiter_index: int, keys_string: str) -> list[str]:
        split_key = keys_string.split(self._config.pattern["delimiter"])
        left, middle_and_right = (
            split_key[:allow_delimiter_index],
            split_key[allow_delimiter_index:],
        )
        middle = middle_and_right[: -(len(self._fields) - allow_delimiter_index - 1)]
        right = middle_and_right[-(len(self._fields) - allow_delimiter_index - 1) :]
        recombined_key = left + ["-".join(middle)] + right
        if len(recombined_key) != len(self._fields):
            raise TemplateReplacerError(
                self.name,
                f"Not enough delimiters in '{self._config.template}' "
                f"to populate {self._fields}",
            )
        return recombined_key

    def _set_value_for_recombined_keys(self, recombined_keys: list[str], value: Any) -> None:
        mapping = self._mapping
        for idx, recombined_key in enumerate(recombined_keys):
            if idx < len(self._fields) - 1:
                if not mapping.get(recombined_key):
                    mapping[recombined_key] = {}
                mapping = mapping[recombined_key]
            else:
                mapping[recombined_key] = value
