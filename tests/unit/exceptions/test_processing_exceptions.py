# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
# pylint: disable=line-too-long

from logprep.processor.base.exceptions import (
    FieldExistsWarning,
    ProcessingCriticalError,
    ProcessingError,
    ProcessingWarning,
)
from tests.unit.exceptions.base import ExceptionBaseTest


class TestProcessingWarning(ExceptionBaseTest):
    exception = ProcessingWarning

    error_message = (
        r"ProcessingWarning: the error message, rule.id='.*',"
        r" rule.description='', event=\{'message': 'test_event'\}"
    )

    counted_metric_name = "number_of_warnings"


class TestFieldExistsWarning(ExceptionBaseTest):
    exception = FieldExistsWarning
    error_message = (
        r"FieldExistsWarning: The following fields could not be written,"
        r" because one or more subfields existed and could not be extended: "
        r"my_field, rule.id='.+', rule.description='', event=\{'message': 'test_event'\}"
    )

    counted_metric_name = "number_of_warnings"

    def setup_method(self):
        super().setup_method()
        self.exception_args = (self.object, self.event, ["my_field"])


class TestProcessingCriticalError(ExceptionBaseTest):
    exception = ProcessingCriticalError

    error_message = (
        r"ProcessingCriticalError: 'the error message' -> "
        r"rule.id: '.*' -> "
        r"event was send to error output and further processing stopped"
    )

    counted_metric_name = "number_of_errors"

    def setup_method(self):
        super().setup_method()
        self.exception_args = ("the error message", self.object)


class TestProcessingError(ExceptionBaseTest):
    exception = ProcessingError

    error_message = r"ProcessingError: the error message"

    counted_metric_name = "number_of_errors"

    def setup_method(self):
        super().setup_method()
        self.exception_args = ("the error message", self.object)
