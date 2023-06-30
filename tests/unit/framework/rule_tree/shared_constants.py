# pylint: disable=missing-docstring
from logprep.filter.expression.filter_expression import StringFilterExpression, Exists

sfe_1 = StringFilterExpression(["key1"], "value1")
sfe_2 = StringFilterExpression(["key2"], "value2")
sfe_3 = StringFilterExpression(["key3"], "value3")
sfe_4 = StringFilterExpression(["key4"], "value4")
sfe_5 = StringFilterExpression(["key5", "subkey5"], "value5")

ex_1 = Exists(["ABC.def"])
ex_2 = Exists(["xyz"])
