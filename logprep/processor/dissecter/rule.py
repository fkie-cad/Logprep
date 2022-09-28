"""
Dissecter Rule
--------------

The dissecter processor tokenizes values from fields into new fields or appends the value to
existing fields. Additionaly it can be used to convert datatypes in field values.

A speaking example:

..  code-block:: yaml
    :linenos:
    :caption: Given dissecter rule

    filter: message
    dissecter:
        mapping:
            message: "%{}of %{extracted.message_float} and a int of %{extracted.message_int}"
        convert_datatype:
            extracted.message_int: "int"
            extracted.message_float: "float"
    description: '...'

..  code-block:: json
    :linenos:
    :caption: Incomming event

    {"message": "This message has a float of 1.23 and a int of 1337"}

..  code-block:: json
    :linenos:
    :caption: Processed event

    {
        "message": "This message has a float of 1.23 and a int of 1337",
        "extracted": {"message_float": 1.23, "message_int": 1337},
    }

Dissect Pattern Language
------------------------

The dissect pattern describes the textual format of the source field.

Given a dissect pattern of :code:`%{field1} %{field2}` the source field value will be dissected into
everything before the first whitespace which would be written into the field `field1` and everything
after the first whitespace which would be written into the field `field2`.

The string surrounded by :code:`%{}` is the desired target field. This can be declared in dotted
field notation. (e.g. :code:`%{target.subfield1.subfield2}`). Every subfield between the first and
the last subfield will be created.

In default the target field will always be overwritten with the captured value. If you want to
append to a preexisting target field value as string or list you have to use the :code:`+` operator.

It is possible to capture the target field name from the source field value with the notation
:code:`%{?<your name for the reference>}` (e.g. :code:`%{?key1}`). This can be referred to with the
notation :code:`%{&<the reference>}` (e.g. :code:`%{&key1}`) afterwards in the same dissection
pattern. References can be combined with the append operator.

.. autoclass:: logprep.processor.dissecter.rule.DissecterRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

Examples for dissection and datatype conversion:
------------------------------------------------

.. datatemplate:import-module:: tests.unit.processor.dissecter.test_dissecter
   :template: testcase-renderer.tmpl

"""
from functools import partial
import re
from typing import Callable, List, Tuple
from attrs import define, validators, field, Factory
from logprep.processor.base.rule import Rule
from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.util.helper import add_field_to, get_dotted_field_value

DISSECT = r"(%\{[+&?]?[^%{]*\})"
SEPERATOR = r"((?!%\{.*\}).+)"

append_as_list = partial(add_field_to, extends_lists=True)


def add_and_overwrite(event, target_field, content, *_):
    """wrapper for add_field_to"""
    add_field_to(event, target_field, content, overwrite_output_field=True)


def append(event, target_field, content, seperator):
    """appends to event"""
    target_value = get_dotted_field_value(event, target_field)
    if isinstance(target_value, str):
        seperator = " " if seperator is None else seperator
        target_value = f"{seperator}".join([target_value, content])
        add_and_overwrite(event, target_field, target_value)
    else:
        append_as_list(event, target_field, content)


class DissecterRule(Rule):
    """dissecter rule"""

    @define(kw_only=True)
    class Config:
        """Config for Dissecter"""

        mapping: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.matches_re(rf"^({DISSECT}{SEPERATOR})+{DISSECT}$"),
                ),
            ],
            default=Factory(dict),
        )
        """A mapping from source fields to a dissect pattern [optional]
        Dotted field notation is possible in key and in the dissect pattern.
        """
        convert_datatype: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.in_(["float", "int", "string"]),
                ),
            ],
            default=Factory(dict),
        )
        """A mapping from source field and desired datatype [optional]
        the datatypes could be [`float`, `int`, `string`]
        """
        tag_on_failure: list = field(
            validator=validators.instance_of(list), default=["_dissectfailure"]
        )
        """A list of tags which will be appended to the event on non critical errors [default=`_dissectfailure`]
        """

    _actions_mapping: dict = {
        "": add_and_overwrite,
        "+": append,
    }

    _converter_mapping: dict = {"int": int, "float": float, "string": str}

    _config: "DissecterRule.Config"

    actions: List[Tuple[str, str, str, Callable, int]]
    """list tuple format (<source_field>, <seperator>, <target_field>, <function>), <position> """

    convert_actions: List[Tuple[str, Callable]]
    """list tuple format <target_field>, <converter callable>"""

    @property
    def failure_tags(self):
        """Returns the failure tags"""
        return self._config.tag_on_failure

    def __init__(self, filter_rule: FilterExpression, config: "DissecterRule.Config"):
        super().__init__(filter_rule)
        self._config = config
        self._set_mapping_actions()
        self._set_convert_actions()

    def __eq__(self, other: "DissecterRule") -> bool:
        return all((self._filter == other._filter, self._config == other._config))

    @staticmethod
    def _create_from_dict(rule: dict) -> "DissecterRule":
        filter_expression = Rule._create_filter_expression(rule)
        config = rule.get("dissecter")
        if not isinstance(config, dict):
            raise InvalidRuleDefinitionError("config is not a dict")
        config = DissecterRule.Config(**config)
        return DissecterRule(filter_expression, config)

    def _set_mapping_actions(self):
        self.actions = []
        for source_field, pattern in self._config.mapping.items():
            sections = re.findall(r"%\{[^%]+", pattern)
            for section in sections:
                section_match = re.match(
                    r"%\{(?P<action>[+]?)(?P<target_field>[^\/]*)(\/(?P<position>\d*))?\}(?P<seperator>.*)",
                    section,
                )
                seperator = (
                    section_match.group("seperator") if section_match.group("seperator") else None
                )
                action = (
                    section_match.group("action") if "action" in section_match.groupdict() else None
                )
                target_field = (
                    section_match.group("target_field")
                    if "target_field" in section_match.groupdict()
                    else None
                )
                position = (
                    section_match.group("position")
                    if "position" in section_match.groupdict()
                    else None
                )
                if target_field:
                    action = self._actions_mapping.get(action)
                else:
                    action = lambda *args: None
                position = int(position) if position is not None else 0
                self.actions.append((source_field, seperator, target_field, action, position))

    def _set_convert_actions(self):
        self.convert_actions = []
        for target_field, converter_string in self._config.convert_datatype.items():
            self.convert_actions.append(
                (target_field, self._converter_mapping.get(converter_string))
            )
