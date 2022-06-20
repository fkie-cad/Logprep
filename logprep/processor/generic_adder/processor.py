"""
GenericAdder
------------
The `generic_adder` is a processor that adds new fields and values to documents based on a list.
The list can reside inside a rule or inside a file.


Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - genericaddername:
        type: generic_adder
        specific_rules:
            - tests/testdata/rules/specific/
        generic_rules:
            - tests/testdata/rules/generic/
"""
from typing import List


from logprep.abc import Processor
from logprep.processor.generic_adder.rule import GenericAdderRule


class GenericAdderError(BaseException):
    """Base class for GenericAdder related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"GenericAdder ({name}): {message}")


class DuplicationError(GenericAdderError):
    """Raise if field already exists."""

    def __init__(self, name: str, skipped_fields: List[str]):
        message = (
            "The following fields already existed and were not overwritten by the GenericAdder: "
        )
        message += " ".join(skipped_fields)

        super().__init__(name, message)


class GenericAdder(Processor):
    """Resolve values in documents by referencing a mapping list."""

    rule_class = GenericAdderRule

    def _apply_rules(self, event, rule):
        conflicting_fields = list()

        for dotted_field, value in rule.add.items():
            keys = dotted_field.split(".")
            dict_ = event
            for idx, key in enumerate(keys):
                if key not in dict_:
                    if idx == len(keys) - 1:
                        dict_[key] = value
                        break
                    dict_[key] = {}

                if isinstance(dict_[key], dict):
                    dict_ = dict_[key]
                else:
                    conflicting_fields.append(keys[idx])

        if conflicting_fields:
            raise DuplicationError(self.name, conflicting_fields)
