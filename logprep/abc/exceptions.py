"""abstract module for exceptions"""


class LogprepException(Exception):
    """Base class for Logprep related exceptions."""

    def __init__(self, message: str, *args) -> None:
        self.message = message
        super().__init__(message, *args)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, LogprepException):
            return self.args == other.args
        return NotImplemented


class LogprepExceptionGroup(ExceptionGroup):
    """Custom ExceptionGroup for Logprep exceptions to override the default
    string representation."""

    def __str__(self) -> str:
        return f"{self.message}: {self.exceptions}"
