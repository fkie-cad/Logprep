"""This module is used to add fields to documents via a list."""

from os.path import isfile

from ruamel.yaml import YAML

from logprep.filter.expression.filter_expression import FilterExpression

from logprep.processor.base.rule import Rule, InvalidRuleDefinitionError

yaml = YAML(typ="safe", pure=True)


class GenericAdderRuleError(InvalidRuleDefinitionError):
    """Base class for GenericAdder rule related exceptions."""

    def __init__(self, message: str):
        super().__init__(f"GenericAdder rule ({message})")


class InvalidGenericAdderDefinition(GenericAdderRuleError):
    """Raise if GenericAdder definition invalid."""

    def __init__(self, definition):
        message = f"The following GenericAdder definition is invalid: {definition}"
        super().__init__(message)


class GenericAdderRule(Rule):
    """Check if documents match a filter."""

    def __init__(self, filter_rule: FilterExpression, generic_adder_cfg: dict):
        super().__init__(filter_rule)

        self._add = generic_adder_cfg.get("add", {})
        self._add_from_file = {}

        only_first_existing = generic_adder_cfg.get("only_first_existing_file", False)

        add_paths = generic_adder_cfg.get("add_from_file")
        if add_paths is not None:
            self._add_from_path(only_first_existing, add_paths)

        self._add.update(self._add_from_file)

    def _add_from_path(self, only_first_existing, add_paths):
        """reads add fields from file"""
        missing_files = []
        existing_files = []

        if isinstance(add_paths, str):
            add_paths = [add_paths]

        for add_path in add_paths:
            if not isfile(add_path):
                missing_files.append(add_path)
            else:
                existing_files.append(add_path)

        if only_first_existing:
            if existing_files:
                existing_files = existing_files[:1]
            else:
                raise InvalidGenericAdderDefinition(
                    f"At least one of the following files must " f"exist: '{missing_files}'"
                )
        else:
            if missing_files:
                raise InvalidGenericAdderDefinition(
                    f"The following required files do " f"not exist: '{missing_files}'"
                )

        for add_path in existing_files:
            with open(add_path, "r", encoding="utf8") as add_file:
                add_dict = yaml.load(add_file)
                if isinstance(add_dict, dict) and all(
                    isinstance(value, str) for value in add_dict.values()
                ):
                    self._add_from_file.update(add_dict)
                else:
                    error_msg = (
                        f"Additions file '{add_path}' must be a dictionary " f"with string values!"
                    )
                    raise InvalidGenericAdderDefinition(error_msg)

    def __eq__(self, other: "GenericAdderRule") -> bool:
        return all(
            [
                other.filter == self._filter,
                self._add == other.add,
            ]
        )

    # pylint: disable=C0111
    @property
    def add(self) -> dict:
        return self._add

    @property
    def add_from_file(self) -> dict:
        return self._add_from_file

    # pylint: enable=C0111

    @staticmethod
    def _create_from_dict(rule: dict) -> "GenericAdderRule":
        GenericAdderRule._check_rule_validity(rule, "generic_adder")
        GenericAdderRule._check_if_valid(rule)

        filter_expression = Rule._create_filter_expression(rule)
        return GenericAdderRule(filter_expression, rule["generic_adder"])

    @staticmethod
    def _check_if_valid(rule: dict):
        generic_adder_cfg = rule["generic_adder"]

        if not ("add_from_file" in generic_adder_cfg or "add" in generic_adder_cfg):
            raise InvalidGenericAdderDefinition(
                '"generic_adder" must contain "add" or ' '"add_from_file"!'
            )
        for field in ("add",):
            if generic_adder_cfg.get(field) and not isinstance(generic_adder_cfg[field], dict):
                raise InvalidGenericAdderDefinition(
                    '"{}" value "{}" is not a dict!'.format(field, generic_adder_cfg[field])
                )
        for field in ("add_from_file",):
            if generic_adder_cfg.get(field):
                error_msg = (
                    f'"{field}" value "{generic_adder_cfg[field]}" is not a string or a'
                    f" list of strings!"
                )
                if not isinstance(generic_adder_cfg[field], (str, list)):
                    raise InvalidGenericAdderDefinition(error_msg)
                if isinstance(generic_adder_cfg[field], list):
                    if not all([isinstance(item, str) for item in generic_adder_cfg[field]]):
                        raise InvalidGenericAdderDefinition(error_msg)
