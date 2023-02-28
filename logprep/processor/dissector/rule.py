"""
Dissector
=========

The dissector processor tokenizes values from fields into new fields or appends the value to
existing fields. Additionally it can be used to convert datatypes of field values.

A speaking example:

..  code-block:: yaml
    :linenos:
    :caption: Given dissector rule

    filter: message
    dissector:
        mapping:
            message: "%{}of %{extracted.message_float} and an int of %{extracted.message_int}"
        convert_datatype:
            extracted.message_int: "int"
            extracted.message_float: "float"
    description: '...'

..  code-block:: json
    :linenos:
    :caption: Incoming event

    {"message": "This message has a float of 1.23 and an int of 1337"}

..  code-block:: json
    :linenos:
    :caption: Processed event

    {
        "message": "This message has a float of 1.23 and an int of 1337",
        "extracted": {"message_float": 1.23, "message_int": 1337},
    }

Dissect Pattern Language
------------------------

The dissect pattern describes the textual format of the source field.

Given a dissect pattern of :code:`%{field1} %{field2}` the source field value will be dissected into
everything before the first whitespace which would be written into the field `field1` and everything
after the first whitespace which would be written into the field `field2`.

The string surrounded by :code:`%{` and :code:`}` is the desired target field. This can be declared
in dotted field notation (e.g. :code:`%{target.subfield1.subfield2}`). Every subfield between the
first and the last subfield will be created if necessary.

By default the target field will always be overwritten with the captured value. If you want to
append to a preexisting target field value, as string or list, you have to use
the :code:`+` operator. If you want to use a prefix before the appended string use this notation
:code:`+( )`. In this example a whitespace would be added before the extracted string is added.
If you want to use the symbols :code:`(` or :code:`)` as your separator, you have to escape with
:code:`\` (e.g. :code:`+(\()`)

It is possible to capture the target field name from the source field value with the notation
:code:`%{?<your name for the reference>}` (e.g. :code:`%{?key1}`). In the same dissection pattern
this can be referred to with the notation :code:`%{&<the reference>}` (e.g. :code:`%{&key1}`).
References can be combined with the append operator.

Optional convert datatype can be provided after the key using :code:`|` as separator
to convert the value from string to :code:`int`, :code:`float` or :code:`bool`.
The conversion to :code:`bool` is interpreted by meaning.
(e.g. :code:`yes` is translated to :code:`True`)

.. autoclass:: logprep.processor.dissector.rule.DissectorRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

Examples for dissection and datatype conversion:
------------------------------------------------

.. datatemplate:import-module:: tests.unit.processor.dissector.test_dissector
   :template: testcase-renderer.tmpl

"""
import re
from typing import Callable, List, Tuple

from attrs import define, validators, field, Factory

from logprep.filter.expression.filter_expression import FilterExpression
from logprep.processor.field_manager.rule import FieldManagerRule
from logprep.util.helper import append, add_and_overwrite

START = r"%\{"
END = r"\}"
VALID_TARGET_FIELD = r"[^\}\%\{\}\+\/\|]*"
APPEND_WITH_SEPERATOR = r"(\+\([^%]+\))"
APPEND_WITHOUT_SEPERATOR = r"(\+(?!\([^%]))"
INDIRECT_FIELD_NOTATION = r"([&\?]))"
VALID_ACTION = rf"({APPEND_WITH_SEPERATOR}|{APPEND_WITHOUT_SEPERATOR}|{INDIRECT_FIELD_NOTATION}"
VALID_POSITION = r"(\/\d*)"
VALID_DATATYPE = r"(\|(int|float|str|bool))"
POSITION_OR_DATATYPE = rf"({VALID_POSITION}|{VALID_DATATYPE})"
DISSECT = rf"{START}{VALID_ACTION}?{VALID_TARGET_FIELD}{POSITION_OR_DATATYPE}?{END}"
DELIMETER = r"([^%]+)"
ACTION = r"(?P<action>[+])?"
SEPERATOR = r"(\((?P<separator>.+)\))?"
TARGET_FIELD = r"(?P<target_field>[^\/\|]*)"
POSITION = r"(\/(?P<position>\d*))?"
DATATYPE = r"(\|(?P<datatype>int|float|bool))?"
SECTION_MATCH = (
    rf"{START}{ACTION}{SEPERATOR}{TARGET_FIELD}{POSITION}{DATATYPE}{END}(?P<delimeter>.*)"
)


def _do_nothing(*_):
    return


def str_to_bool(input_str: str) -> bool:
    """converts an input string to bool by meaning"""
    try:
        if input_str.lower() in ("yes", "true", "on", "y"):
            return True
        return bool(int(input_str))
    except (ValueError, AttributeError):
        pass
    return False


class DissectorRule(FieldManagerRule):
    """dissector rule"""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Config for Dissector"""

        source_fields: list = field(factory=list)
        target_field: str = field(default="")

        mapping: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.matches_re(
                        rf"^({DELIMETER})?({DISSECT}{DELIMETER})+({DISSECT})?$"
                    ),
                ),
            ],
            default=Factory(dict),
        )
        """A mapping from source fields to a dissect pattern [optional].
        Dotted field notation is possible in key and in the dissect pattern.
        """
        convert_datatype: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.in_(["float", "int", "bool", "string"]),
                ),
            ],
            default=Factory(dict),
        )
        """A mapping from source field and desired datatype [optional].
        The datatypes could be :code:`float`, :code:`int`, :code:`bool`, :code:`string`
        """

        def __attrs_post_init__(self):
            self.source_fields = list(self.mapping.keys())  # pylint: disable=no-member

    _actions_mapping: dict = {
        None: add_and_overwrite,
        "+": append,
    }

    _converter_mapping: dict = {"int": int, "float": float, "string": str, "bool": str_to_bool}

    _config: "DissectorRule.Config"

    actions: List[Tuple[str, str, str, Callable, int]]
    """list tuple format (<source_field>, <separator>, <target_field>, <function>), <position> """

    convert_actions: List[Tuple[str, Callable]]
    """list tuple format <target_field>, <converter callable>"""

    @property
    def failure_tags(self):
        """Returns the failure tags"""
        return self._config.tag_on_failure

    def __init__(self, filter_rule: FilterExpression, config: "DissectorRule.Config"):
        super().__init__(filter_rule, config)
        self._set_mapping_actions()
        self._set_convert_actions()

    def _set_mapping_actions(self):
        self.actions = []
        for source_field, pattern in self._config.mapping.items():
            if not re.match(rf"^{DISSECT}.*", pattern):
                pattern = "%{}" + pattern
            sections = re.findall(r"%\{[^%]+", pattern)
            for section in sections:
                section_match = re.match(SECTION_MATCH, section)
                separator = section_match.group("separator")
                separator = "" if separator is None else separator
                separator = separator.replace("\\(", "(")
                separator = separator.replace("\\)", ")")
                action_key = section_match.group("action")
                target_field = section_match.group("target_field")
                datatype = section_match.group("datatype")
                position = section_match.group("position")
                if datatype is not None:
                    self._config.convert_datatype.update({target_field: datatype})
                delimeter = section_match.group("delimeter")
                delimeter = None if delimeter == "" else delimeter
                position = int(position) if position is not None else 0
                action = self._actions_mapping.get(action_key) if target_field else _do_nothing
                self.actions.append(
                    (source_field, delimeter, target_field, action, separator, position)
                )

    def _set_convert_actions(self):
        self.convert_actions = []
        for target_field, converter_string in self._config.convert_datatype.items():
            self.convert_actions.append(
                (target_field, self._converter_mapping.get(converter_string))
            )
