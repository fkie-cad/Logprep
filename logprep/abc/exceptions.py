""" abstract module for exceptions"""


class LogprepException(Exception):
    """Base class for Logprep related exceptions."""

    def __eq__(self, __value: object) -> bool:
        return type(self) is type(__value) and self.args == __value.args
