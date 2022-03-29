"""
TemplateReplacer
----------------

The `template_replacer` is a processor that can replace parts of a text field to anonymize those
parts. The replacement is based on a template file.


Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - templatereplacername:
        type: template_replacer
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
        template: /tmp/template.yml
        pattern:
            delimiter: ","
            fields:
                - field.name.a
                - field.name.b
            allowed_delimiter_field: field.name.b
            target_field: target.field
"""
from logging import Logger
from attr import define, field, validators

from ruamel.yaml import YAML

from logprep.abc import Processor
from logprep.processor.template_replacer.rule import TemplateReplacerRule
from logprep.util.validators import file_validator

yaml = YAML(typ="safe", pure=True)


class TemplateReplacerError(BaseException):
    """Base class for TemplateReplacer related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"TemplateReplacer ({name}): {message}")


class TemplateReplacer(Processor):
    """Resolve values in documents by referencing a mapping list."""

    @define(kw_only=True)
    class Config(Processor.Config):
        """TemplateReplacer config"""

        template: str = field(validator=file_validator)
        """
        Path to a YML file with a list of replacements in the format
        `%{provider_name}-%{event_id}: %{new_message}`.
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

    __slots__ = ["_target_field", "_target_field_split", "_fields", "_mapping"]

    _target_field: str

    _target_field_split: str

    _fields: list

    _mapping: dict

    rule_class = TemplateReplacerRule

    def __init__(self, name: str, configuration: Processor.Config, logger: Logger):
        super().__init__(name=name, configuration=configuration, logger=logger)
        pattern = configuration.pattern
        template_path = configuration.template
        self._target_field = pattern["target_field"]
        self._target_field_split = self._target_field.split(".")
        self._fields = pattern["fields"]
        delimiter = pattern["delimiter"]
        allow_delimiter_field = pattern["allowed_delimiter_field"]
        allow_delimiter_index = self._fields.index(allow_delimiter_field)

        self._mapping = {}
        with open(template_path, "r", encoding="utf8") as template_file:
            template = yaml.load(template_file)

        for key, value in template.items():
            split_key = key.split(delimiter)
            left, middle_and_right = (
                split_key[:allow_delimiter_index],
                split_key[allow_delimiter_index:],
            )
            middle = middle_and_right[: -(len(self._fields) - allow_delimiter_index - 1)]
            right = middle_and_right[-(len(self._fields) - allow_delimiter_index - 1) :]
            recombined_keys = left + ["-".join(middle)] + right

            if len(recombined_keys) != len(self._fields):
                raise TemplateReplacerError(
                    self.name,
                    f"Not enough delimiters in '{template_path}' " f"to populate {self._fields}",
                )

            try:
                _dict = self._mapping
                for idx, recombined_key in enumerate(recombined_keys):
                    if idx < len(self._fields) - 1:
                        if not _dict.get(recombined_key):
                            _dict[recombined_key] = {}
                        _dict = _dict[recombined_key]
                    else:
                        _dict[recombined_key] = value

            except ValueError as error:
                raise TemplateReplacerError(
                    self.name, "template_replacer template is invalid!"
                ) from error

    def _apply_rules(self, event, rule):
        _dict = self._mapping
        for field_ in self._fields:
            dotted_field_value = self._get_dotted_field_value(event, field_)
            if dotted_field_value is None:
                return

            value = str(dotted_field_value)
            _dict = _dict.get(value, None)
            if _dict is None:
                return

        if _dict is not None:
            _event = event
            for subfield in self._target_field_split[:-1]:
                event_sub = _event.get(subfield)
                if isinstance(event_sub, dict):
                    _event = event_sub
                elif event_sub is None:
                    _event[subfield] = {}
                    _event = _event[subfield]
                else:
                    raise TemplateReplacerError(
                        self.name,
                        f"Parent field '{subfield}' of target field '{self._target_field}' "
                        f"exists and is not a dict!",
                    )
            _event[self._target_field_split[-1]] = _dict

    @staticmethod
    def _field_exists(event: dict, dotted_field: str) -> bool:
        fields = dotted_field.split(".")
        dict_ = event
        for field_ in fields:
            if field_ in dict_:
                dict_ = dict_[field_]
            else:
                return False
        return True
