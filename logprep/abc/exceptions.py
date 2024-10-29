""" abstract module for exceptions"""


class LogprepException(Exception):
    """Base class for Logprep related exceptions."""

    def __init__(self, message: str, *args) -> None:
        self.message = message
        super().__init__(message, *args)

    def __eq__(self, __value: object) -> bool:
        return type(self) is type(__value) and self.args == __value.args
