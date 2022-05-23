"""This module provides the abstract base class for all processors.

New processors are created by implementing it.

"""

from logprep.util.helper import camel_to_snake


class ProcessingError(BaseException):
    """Base class for exceptions related to processing events."""

    def __init__(self, name: str, message: str):
        super().__init__(f"{name}: ({message})")


class ProcessingWarning(ProcessingError):
    """An minor error occurred - log the error but continue processing the event."""

    def __init__(self, message: str):
        super().__init__("ProcessingWarning", message)


class ProcessingWarningCollection(ProcessingError):
    """A collection of ProcessingWarnings."""

    def __init__(self, name: str, message: str, processing_warnings):
        super().__init__(name, message)
        self.processing_warnings = processing_warnings


class SnakeType(type):
    """
    If set as a metaclass it rewrites the type(cls) call to return the snake case version
    of the class
    """

    def __repr__(cls):
        return camel_to_snake(cls.__name__)
