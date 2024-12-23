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

Following a list with example calculation expressions, where all factors and the operators can be
retrieved from a field with the schema :code:`${your.dotted.field}`:

* :code:`9` => :code:`9`
* :code:`-9` => :code:`-9`
* :code:`--9` => :code:`9`
* :code:`-E` => :code:`-math.e`
* :code:`9 + 3 + 6` => :code:`9 + 3 + 6`
* :code:`9 + 3 / 11` => :code:`9 + 3.0 / 11`
* :code:`(9 + 3)` => :code:`(9 + 3)`
* :code:`(9+3) / 11` => :code:`(9 + 3.0) / 11`
* :code:`9 - 12 - 6` => :code:`9 - 12 - 6`
* :code:`9 - (12 - 6)` => :code:`9 - (12 - 6)`
* :code:`2*3.14159` => :code:`2 * 3.14159`
* :code:`3.1415926535*3.1415926535 / 10` => :code:`3.1415926535 * 3.1415926535 / 10`
* :code:`PI * PI / 10` => :code:`math.pi * math.pi / 10`
* :code:`PI*PI/10` => :code:`math.pi * math.pi / 10`
* :code:`PI^2` => :code:`math.pi ** 2`
* :code:`round(PI^2)` => :code:`round(math.pi ** 2)`
* :code:`6.02E23 * 8.048` => :code:`6.02e23 * 8.048`
* :code:`e / 3` => :code:`math.e / 3`
* :code:`sin(PI/2)` => :code:`math.sin(math.pi / 2)`
* :code:`10+sin(PI/4)^2` => :code:`10 + math.sin(math.pi / 4) ** 2`
* :code:`trunc(E)` => :code:`int(math.e)`
* :code:`trunc(-E)` => :code:`int(-math.e)`
* :code:`round(E)` => :code:`round(math.e)`
* :code:`round(-E)` => :code:`round(-math.e)`
* :code:`E^PI` => :code:`math.e ** math.pi`
* :code:`exp(0)` => :code:`1`
* :code:`exp(1)` => :code:`math.e`
* :code:`2^3^2` => :code:`2 ** 3 ** 2`
* :code:`(2^3)^2` => :code:`(2 ** 3) ** 2`
* :code:`2^3+2` => :code:`2 ** 3 + 2`
* :code:`2^3+5` => :code:`2 ** 3 + 5`
* :code:`2^9` => :code:`2 ** 9`
* :code:`sgn(-2)` => :code:`-1`
* :code:`sgn(0)` => :code:`0`
* :code:`sgn(0.1)` => :code:`1`
* :code:`round(E, 3)` => :code:`round(math.e, 3)`
* :code:`round(PI^2, 3)` => :code:`round(math.pi ** 2, 3)`
* :code:`sgn(cos(PI/4))` => :code:`1`
* :code:`sgn(cos(PI/2))` => :code:`0`
* :code:`sgn(cos(PI*3/4))` => :code:`-1`
* :code:`+(sgn(cos(PI/4)))` => :code:`1`
* :code:`-(sgn(cos(PI/4)))` => :code:`-1`
* :code:`hypot(3, 4)` => :code:`5`
* :code:`multiply(3, 7)` => :code:`21`
* :code:`all(1,1,1)` => :code:`True`
* :code:`all(1,1,1,1,1,0)` => :code:`False`

The calc expression is not whitespace sensitive.

"""

import re

from attrs import define, field, validators

from logprep.processor.field_manager.rule import FIELD_PATTERN, FieldManagerRule


class CalculatorRule(FieldManagerRule):
    """CalculatorRule"""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Config for Calculator"""

        calc: str = field(
            validator=[validators.instance_of(str), validators.min_len(3)],
        )
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

    @property
    def calc(self):
        """Returns the calculation expression"""
        return self._config.calc

    @property
    def timeout(self):
        """Returns the timeout"""
        return self._config.timeout
