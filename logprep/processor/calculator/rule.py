"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

A speaking example:

..  code-block:: yaml
    :linenos:
    :caption: Given calculator rule

    filter: 'duration'
    calculator:
      target_field: duration
      calc: ${duration} * 10e5
      overwrite_target: True
    description: '...'

..  code-block:: json
    :linenos:
    :caption: Incoming event

    {"duration": "0.01"}

..  code-block:: json
    :linenos:
    :caption: Processed event

    {"duration": 10000.0}

.. autoclass:: logprep.processor.calculator.rule.CalculatorRule.Config
   :noindex:
   :members:
   :inherited-members:
   :no-undoc-members:

Expression syntax for |PROCESSOR_NAME|:
------------------------------------------------

The |PROCESSOR_NAME| can handle the following atomic expressions:

.. list-table:: Available expressions
   :header-rows: 1

   * - Type
     - Examples
     - Description
   * - Numeric Values
     - :code:`123`, :code:`- 0.123`, :code:`1e-5`
     - Integers or floats (with scientific notation).
   * - Variables
     - :code:`${field1}`, :code:`${nested.field}`
     - A value to be read from the event, specified via its path. Will be parsed
       to numeric values.
   * - Constants
     - :code:`pi`, :code:`e`, :code:`PI`. :code:`E`
     - The values for pi and the euler number (case insensitive).
   * - Hex-Numbers (as constants)
     - :code:`0xFF`, :code:`from_hex(FF)`, :code:`FROM_HEX(FF)`
     - Integer can be given in in hex format either via the :code:`0x`-prefix
       or the build-in :code:`from_hex` function.
   * - Hex-Numbers (as variables)
     - :code:`from_hex(${path.to.field})`, :code:`from_hex(0x${field})` (legacy)
     - Read a hex number from string found on the event at the specified path.

The |PROCESSOR_NAME| supports the following arithmetic operators:

* :code:`+` addition
* :code:`-` subtraction
* :code:`*` multiplication
* :code:`/` division
* :code:`%` modulo
* :code:`^` exponentiation

These take numeric values as operands and return a numeric value as a result.

The |PROCESSOR_NAME| supports the following comparison operators:

* :code:`>` greater than
* :code:`<` less than
* :code:`>=` greater than or equal
* :code:`<=` less than or equal
* :code:`==` equal
* :code:`!=` not equal

These take numeric values as operands and return a boolean value (:code:`True`
or :code:`False`) as a result.

Furthermore the following range checks are supported

* :code:`a < b < c`
* :code:`a <= b < c`
* :code:`a < b <= c`
* :code:`a <= b <= c`

Where :code:`a`, :code:`b` and :code:`c` are numeric values and the yielded
result is a boolean.

Arithmetic expression are evaluated before comparisons and range checks.

.. warning::
    Comparisons, range checks and some functions return boolean values.
    Because unary minus, operators, range checks and most functions can only
    accept numbers not booleans the following examples would result in
    a syntax error:

    * :code:`(1 < 2) < 3`
    * :code:`1 < 2 == 2`
    * :code:`-(1 < 2)`
    * :code:`(1 < 2) + 1`
    * :code:`(1 < 2) == (2 < 3)`
    * :code:`all(1, 1) * 2`


The following functions are available, where the function names a case-insensitive:

.. datatemplate:import-module:: logprep.processor.calculator.ast.function_registry
   :template: calculator/function-renderer.tmpl


.. warning::

   The operators :code:`==` and :code:`!=` perform exact comparisons. Avoid using them to compare
   calculated floating-point values, because many decimal values cannot be represented exactly as
   binary floating-point numbers.

   For example, :code:`0.1 + 0.2 == 0.3` may evaluate to :code:`False`.

Following is a list of example calculation expressions. All factors and operators can be retrieved
from a field using the schema :code:`${your.dotted.field}`:

.. datatemplate:import-module:: tests.unit.processor.calculator.test_ast
   :template: calculator/examples-renderer.tmpl

The calc expression is not whitespace or case sensitive.


Examples for |PROCESSOR_NAME|:
------------------------------------------------

.. datatemplate:import-module:: tests.unit.processor.calculator.test_calculator
   :template: testcase-renderer.tmpl


"""

import re

from attrs import define, field, validators

from logprep.processor.calculator.ast.node import ASTNode
from logprep.processor.calculator.ast.parse import parse_expression
from logprep.processor.field_manager.rule import FIELD_PATTERN, FieldManagerRule
from logprep.util.context_managers import timeout


class CalculatorRule(FieldManagerRule):
    """CalculatorRule"""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Config for Calculator"""

        calc: str = field(validator=(validators.instance_of(str), validators.min_len(3)))
        """The calculation expression. Fields from the event can be used by
        surrounding them with :code:`${` and :code:`}`."""
        source_fields: list = field(factory=list, init=False, repr=False, eq=False)
        merge_with_target: bool = field(validator=validators.instance_of(bool), default=False)
        """If the target field exists and is a list, the list will be extended with the values
        of the source fields.
        """
        timeout: int = field(validator=validators.instance_of(int), converter=int, default=1)
        """The maximum time in seconds for the calculation. Defaults to :code:`1`"""
        ignore_missing_fields: bool = field(validator=validators.instance_of(bool), default=False)
        """If set to :code:`True` missing fields will be ignored, no warning is logged,
        and the event is not tagged with the a failure tag. As soon as one field is missing
        no calculation is performed at all. Defaults to :code:`False`"""
        mapping: dict = field(default="", init=False, repr=False, eq=False)

        def __attrs_post_init__(self):
            self.source_fields = re.findall(FIELD_PATTERN, self.calc)
            super().__attrs_post_init__()

    def __init__(self, filter_rule, config, processor_name):
        super().__init__(filter_rule, config, processor_name)
        assert isinstance(self._config, CalculatorRule.Config)
        with timeout(seconds=self.timeout):
            compiled_expression = parse_expression(self._config.calc)
            self.__parsed_expression = compiled_expression.optimize()

    @property
    def parsed_expression(self) -> ASTNode:
        """The parsed and optimized calculation expression"""
        return self.__parsed_expression

    @property
    def timeout(self):
        """Returns the timeout"""
        return self._config.timeout
