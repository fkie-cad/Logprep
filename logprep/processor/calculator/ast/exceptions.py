"""Exceptions used on formula parsing and evaluation"""

from logprep.abc.exceptions import LogprepException


class CalculatorError(LogprepException):
    """Base class for calculator.ast related exceptions"""


class InvalidSyntaxError(CalculatorError):
    """Exception thrown when an encountering invalid syntax while parsing"""


class ParsingError(CalculatorError):
    """Exception thrown on input that can not be parsed to the expected format"""


class MissingValueError(CalculatorError):
    """Exception thrown if values are missing during evaluation"""


class UnknownFunctionError(CalculatorError):
    """Exception thrown if a function is unknown"""


class DivisionByZeroError(CalculatorError):
    """Exception thrown on a division by zero on runtime of evaluation"""
