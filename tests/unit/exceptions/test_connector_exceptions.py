# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
# pylint: disable=line-too-long

from logprep.abc.input import (
    CriticalInputError,
    CriticalInputParsingError,
    FatalInputError,
    InputError,
    InputWarning,
    SourceDisconnectedWarning,
)
from logprep.abc.output import (
    CriticalOutputError,
    FatalOutputError,
    OutputError,
    OutputWarning,
)
from logprep.factory import Factory
from tests.unit.exceptions.base import ExceptionBaseTest


class TestFatalOutputError(ExceptionBaseTest):
    exception = FatalOutputError

    error_message = r"FatalOutputError in DummyOutput \(test connector\): the error message"

    counted_metric_name = "number_of_errors"

    def setup_method(self):
        self.object = Factory.create({"test connector": {"type": "dummy_output", "default": False}})
        self.exception_args = (self.object, "the error message")


class TestCriticalOutputError(ExceptionBaseTest):
    exception = CriticalOutputError

    error_message = r"CriticalOutputError in DummyOutput \(test connector\): the error message"

    counted_metric_name = "number_of_errors"

    def setup_method(self):
        self.object = Factory.create({"test connector": {"type": "dummy_output", "default": False}})
        self.exception_args = (self.object, "the error message", b"raw input")

    def test_init_copies_raw_input(self):
        self.object = Factory.create({"test connector": {"type": "dummy_output", "default": False}})
        raw_input = {"key": "value"}
        exception = self.exception(self.object, "the error message", raw_input)
        assert exception.raw_input == raw_input
        assert exception.raw_input is not raw_input

    def test_init_deepcopy_raw_input(self):
        self.object = Factory.create({"test connector": {"type": "dummy_output", "default": False}})
        raw_input = [{"key": "value"}, {"key": {"key": "value"}}]
        exception = self.exception(self.object, "the error message", raw_input)
        assert exception.raw_input == raw_input
        assert exception.raw_input is not raw_input


class TestOutputError(ExceptionBaseTest):
    exception = OutputError

    error_message = r"OutputError in DummyOutput \(test connector\): the error message"

    counted_metric_name = "number_of_errors"

    def setup_method(self):
        self.object = Factory.create({"test connector": {"type": "dummy_output", "default": False}})
        self.exception_args = (self.object, "the error message")


class TestOutputWarning(ExceptionBaseTest):
    exception = OutputWarning

    error_message = r"OutputWarning in DummyOutput \(test connector\): the error message"

    counted_metric_name = "number_of_warnings"

    def setup_method(self):
        self.object = Factory.create({"test connector": {"type": "dummy_output", "default": False}})
        self.exception_args = (self.object, "the error message")


class TestInputError(ExceptionBaseTest):
    exception = InputError

    error_message = r"InputError in DummyInput \(test connector\): the error message"

    counted_metric_name = "number_of_errors"

    def setup_method(self):
        self.object = Factory.create({"test connector": {"type": "dummy_input", "documents": []}})
        self.exception_args = (self.object, "the error message")


class TestCriticalInputError(ExceptionBaseTest):
    exception = CriticalInputError

    error_message = r"CriticalInputError in DummyInput \(test connector\): the error message"

    counted_metric_name = "number_of_errors"

    def setup_method(self):
        self.object = Factory.create({"test connector": {"type": "dummy_input", "documents": []}})
        self.exception_args = (self.object, "the error message", b"raw input")

    def test_init_copies_raw_input(self):
        self.object = Factory.create({"test connector": {"type": "dummy_input", "documents": []}})
        raw_input = {"key": "value"}
        exception = self.exception(self.object, "the error message", raw_input)
        assert exception.raw_input == raw_input
        assert exception.raw_input is not raw_input

    def test_init_deepcopy_raw_input(self):
        self.object = Factory.create({"test connector": {"type": "dummy_input", "documents": []}})
        raw_input = [{"key": "value"}, {"key": {"key": "value"}}]
        exception = self.exception(self.object, "the error message", raw_input)
        assert exception.raw_input == raw_input
        assert exception.raw_input is not raw_input


class TestCriticalInputParsingError(ExceptionBaseTest):
    exception = CriticalInputParsingError

    error_message = r"CriticalInputParsingError in DummyInput \(test connector\): the error message"

    counted_metric_name = "number_of_errors"

    def setup_method(self):
        self.object = Factory.create({"test connector": {"type": "dummy_input", "documents": []}})
        self.exception_args = (self.object, "the error message", b"raw input")

    def test_init_copies_raw_input(self):
        self.object = Factory.create({"test connector": {"type": "dummy_input", "documents": []}})
        raw_input = {"key": "value"}
        exception = self.exception(self.object, "the error message", raw_input)
        assert exception.raw_input == raw_input
        assert exception.raw_input is not raw_input

    def test_init_deepcopy_raw_input(self):
        self.object = Factory.create({"test connector": {"type": "dummy_input", "documents": []}})
        raw_input = [{"key": "value"}, {"key": {"key": "value"}}]
        exception = self.exception(self.object, "the error message", raw_input)
        assert exception.raw_input == raw_input
        assert exception.raw_input is not raw_input


class TestFatalInputError(ExceptionBaseTest):
    exception = FatalInputError

    error_message = r"FatalInputError in DummyInput \(test connector\): the error message"

    counted_metric_name = "number_of_errors"

    def setup_method(self):
        self.object = Factory.create({"test connector": {"type": "dummy_input", "documents": []}})
        self.exception_args = (self.object, "the error message")


class TestInputWarning(ExceptionBaseTest):
    exception = InputWarning

    error_message = r"InputWarning in DummyInput \(test connector\): the error message"

    counted_metric_name = "number_of_warnings"

    def setup_method(self):
        self.object = Factory.create({"test connector": {"type": "dummy_input", "documents": []}})
        self.exception_args = (self.object, "the error message")


class TestSourceDisconnectedWarning(ExceptionBaseTest):
    exception = SourceDisconnectedWarning

    error_message = r"SourceDisconnectedWarning in DummyInput \(test connector\): the error message"

    counted_metric_name = "number_of_warnings"

    def setup_method(self):
        self.object = Factory.create({"test connector": {"type": "dummy_input", "documents": []}})
        self.exception_args = (self.object, "the error message")
