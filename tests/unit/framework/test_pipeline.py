# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
import logging
import multiprocessing
from copy import deepcopy
from logging import DEBUG
from multiprocessing import Lock
from typing import Iterable, Tuple
from unittest import mock

import pytest
import requests
from _pytest.python_api import raises

from logprep.abc.input import (
    CriticalInputError,
    CriticalInputParsingError,
    FatalInputError,
    InputWarning,
)
from logprep.abc.output import (
    CriticalOutputError,
    FatalOutputError,
    Output,
    OutputWarning,
)
from logprep.abc.processor import ProcessorResult
from logprep.factory import Factory
from logprep.framework.pipeline import Pipeline, PipelineResult
from logprep.processor.base.exceptions import (
    FieldExistsWarning,
    ProcessingCriticalError,
    ProcessingWarning,
)
from logprep.processor.deleter.rule import DeleterRule
from logprep.util.configuration import Configuration

original_create = Factory.create


class ConfigurationForTests:
    logprep_config = Configuration(
        **{
            "version": 1,
            "timeout": 0.001,
            "input": {"dummy": {"type": "dummy_input", "documents": [{"test": "empty"}]}},
            "output": {"dummy": {"type": "dummy_output"}},
            "pipeline": [
                {"mock_processor1": {"proc": "conf"}},
                {"mock_processor2": {"proc": "conf"}},
            ],
            "metrics": {"enabled": False},
        }
    )


def get_mock_create():
    """
    Create a new mock_create magic mock with a default processor result. Is applied for every
    test.
    """
    mock_create = mock.MagicMock()
    mock_component = mock.MagicMock()
    mock_component.process = mock.MagicMock()
    mock_component.process.return_value = ProcessorResult(processor_name="mock_processor")
    mock_create.return_value = mock_component
    return mock_create


@mock.patch("logprep.factory.Factory.create", new_callable=get_mock_create)
class TestPipeline(ConfigurationForTests):
    def setup_method(self):
        self._check_failed_stored = None

        self.pipeline = Pipeline(
            pipeline_index=1,
            config=self.logprep_config,
        )

    def test_pipeline_property_returns_pipeline(self, mock_create):
        self.pipeline._setup()
        assert len(self.pipeline._pipeline) == 2
        assert mock_create.call_count == 4  # 2 processors, 1 input, 1 output

    def test_setup_calls_setup_on_pipeline_processors(self, _):
        self.pipeline._setup()
        assert len(self.pipeline._pipeline) == 2
        for processor in self.pipeline._pipeline:
            processor.setup.assert_called()

    def test_shut_down_calls_shut_down_on_pipeline_processors(self, _):
        self.pipeline._setup()
        processors = list(self.pipeline._pipeline)
        self.pipeline._shut_down()
        for processor in processors:
            processor.shut_down.assert_called()

    def test_setup_calls_setup_on_input_and_output(self, _):
        self.pipeline._setup()
        self.pipeline._input.setup.assert_called()
        for _, output in self.pipeline._output.items():
            output.setup.assert_called()

    def test_passes_timeout_parameter_to_inputs_get_next(self, _):
        self.pipeline._setup()
        self.pipeline._input.get_next.return_value = ({}, {})
        self.pipeline.process_pipeline()
        timeout = self.logprep_config.timeout
        self.pipeline._input.get_next.assert_called_with(timeout)

    def test_empty_documents_are_not_forwarded_to_other_processors(self, _):
        input_data = [{"do_not_delete": "1"}, {"delete_me": "2"}, {"do_not_delete": "3"}]
        connector_config = {"dummy": {"type": "dummy_input", "documents": input_data}}
        input_connector = original_create(connector_config)
        self.pipeline._input = input_connector
        self.pipeline._output = {
            "dummy": original_create({"dummy": {"type": "dummy_output"}}),
        }
        deleter_config = {
            "deleter processor": {
                "type": "deleter",
                "specific_rules": [],
                "generic_rules": [],
            }
        }
        deleter_processor = original_create(deleter_config)
        deleter_rule = DeleterRule._create_from_dict(
            {"filter": "delete_me", "deleter": {"delete": True}}
        )
        deleter_processor._specific_tree.add_rule(deleter_rule)
        processor_with_mock_result = mock.MagicMock()
        processor_with_mock_result.process = mock.MagicMock()
        processor_with_mock_result.process.return_value = ProcessorResult(
            processor_name="processor_with_mock_res"
        )
        self.pipeline._pipeline = [
            processor_with_mock_result,
            deleter_processor,
            deepcopy(processor_with_mock_result),
        ]
        logger = logging.getLogger("Pipeline")
        logger.setLevel(DEBUG)
        while self.pipeline._input._documents:
            self.pipeline.process_pipeline()
        assert len(self.pipeline._input._documents) == 0, "all events were processed"
        assert self.pipeline._pipeline[0].process.call_count == 3, "called for all events"
        assert self.pipeline._pipeline[2].process.call_count == 2, "not called for deleted event"
        assert {"delete_me": "2"} not in self.pipeline._output["dummy"].events
        assert len(self.pipeline._output["dummy"].events) == 2

    def test_not_empty_documents_are_stored_in_the_output(self, _):
        self.pipeline._setup()
        self.pipeline._input.get_next.return_value = ({"message": "test"}, None)
        self.pipeline._store_event = mock.MagicMock()
        self.pipeline.process_pipeline()
        assert self.pipeline._store_event.call_count == 1

    def test_empty_documents_are_not_stored_in_the_output(self, _):
        def mock_process_event(event):
            event.clear()
            return PipelineResult(
                event=event, event_received=event, results=[], pipeline=self.pipeline._pipeline
            )

        self.pipeline.process_event = mock_process_event
        self.pipeline._setup()
        self.pipeline._input.get_next.return_value = ({"message": "test"}, None)
        self.pipeline._store_event = mock.MagicMock()
        self.pipeline.process_pipeline()
        assert self.pipeline._store_event.call_count == 0

    def test_shut_down_calls_shut_down_on_input(self, _):
        self.pipeline._setup()
        self.pipeline._shut_down()
        self.pipeline._input.shut_down.assert_called()

    def test_shut_down_calls_shut_down_on_output(self, _):
        self.pipeline._setup()
        self.pipeline._shut_down()
        for _, output in self.pipeline._output.items():
            output.shut_down.assert_called()

    def test_all_events_provided_by_input_arrive_at_output(self, _):
        self.pipeline._setup()
        self.pipeline._setup = mock.MagicMock()
        input_data = [{"test": "1"}, {"test": "2"}, {"test": "3"}]
        expected_output_data = deepcopy(input_data)
        connector_config = {"type": "dummy_input", "documents": input_data}
        self.pipeline._input = original_create({"dummy": connector_config})
        self.pipeline._output = {"dummy": original_create({"dummy": {"type": "dummy_output"}})}
        self.pipeline.run()
        assert self.pipeline._output["dummy"].events == expected_output_data

    @mock.patch("logging.Logger.error")
    def test_critical_output_error_is_logged_and_stored_as_failed(self, mock_error, _):
        self.pipeline._setup()
        self.pipeline._input.get_next.return_value = ({"order": 1}, None)
        raised_error = CriticalOutputError(
            self.pipeline._output["dummy"], "An error message", {"failed": "event"}
        )
        self.pipeline._output["dummy"].store.side_effect = raised_error
        self.pipeline.process_pipeline()
        self.pipeline._output["dummy"].store_failed.assert_called()
        mock_error.assert_called_with(str(raised_error))

    @mock.patch("logging.Logger.warning")
    def test_input_warning_error_is_logged_but_processing_continues(self, mock_warning, _):
        self.pipeline._setup()

        def raise_warning_error(_):
            raise InputWarning(self.pipeline._input, "i warn you")

        self.pipeline._input.metrics = mock.MagicMock()
        self.pipeline._input.metrics.number_of_warnings = 0
        self.pipeline._input.get_next.return_value = ({"order": 1}, None)
        self.pipeline.process_pipeline()
        self.pipeline._input.get_next.side_effect = raise_warning_error
        self.pipeline.process_pipeline()
        self.pipeline._input.get_next.side_effect = None
        self.pipeline.process_pipeline()
        assert self.pipeline._input.get_next.call_count == 3
        mock_warning.assert_called_with(str(InputWarning(self.pipeline._input, "i warn you")))
        assert self.pipeline._output["dummy"].store.call_count == 2

    @mock.patch("logging.Logger.warning")
    def test_output_warning_error_is_logged_but_processing_continues(self, mock_warning, _):
        self.pipeline._setup()
        self.pipeline._input.get_next.return_value = ({"order": 1}, None)
        self.pipeline._output["dummy"].metrics = mock.MagicMock()
        self.pipeline._output["dummy"].metrics.number_of_warnings = 0
        self.pipeline.process_pipeline()
        self.pipeline._output["dummy"].store.side_effect = OutputWarning(
            self.pipeline._output["dummy"], ""
        )
        self.pipeline.process_pipeline()
        self.pipeline._output["dummy"].store.side_effect = None
        self.pipeline.process_pipeline()
        assert self.pipeline._input.get_next.call_count == 3
        assert mock_warning.call_count == 1
        assert self.pipeline._output["dummy"].store.call_count == 3

    @mock.patch("logging.Logger.warning")
    def test_processor_warning_error_is_logged_but_processing_continues(self, mock_warning, _):
        self.pipeline._setup()
        self.pipeline._input.get_next.return_value = ({"message": "test"}, None)
        mock_rule = mock.MagicMock()
        processing_warning = ProcessingWarning("not so bad", mock_rule, {"message": "test"})
        self.pipeline._pipeline[1].process.return_value = ProcessorResult(
            processor_name="mock_processor", warnings=[processing_warning]
        )
        self.pipeline.process_pipeline()
        self.pipeline._input.get_next.return_value = ({"message": "test"}, None)
        result = self.pipeline.process_pipeline()
        assert processing_warning in result.results[0].warnings
        mock_warning.assert_called()
        assert "ProcessingWarning: not so bad" in mock_warning.call_args[0][0]
        assert self.pipeline._output["dummy"].store.call_count == 2, "all events are processed"

    @mock.patch("logging.Logger.error")
    def test_processor_critical_error_is_logged_event_is_stored_in_error_output(
        self, mock_error, _
    ):
        self.pipeline._setup()
        input_event1 = {"message": "first event"}
        input_event2 = {"message": "second event"}
        self.pipeline._input.get_next.return_value = (input_event1, None)
        mock_rule = mock.MagicMock()
        self.pipeline._pipeline[1].process.return_value = ProcessorResult(
            processor_name="",
            errors=[ProcessingCriticalError("really bad things happened", mock_rule, input_event1)],
        )
        self.pipeline.process_pipeline()
        self.pipeline._input.get_next.return_value = (input_event2, None)
        self.pipeline._pipeline[1].process.return_value = ProcessorResult(
            processor_name="",
            errors=[ProcessingCriticalError("really bad things happened", mock_rule, input_event2)],
        )

        self.pipeline.process_pipeline()
        assert self.pipeline._input.get_next.call_count == 2, "2 events gone into processing"
        assert mock_error.call_count == 2, f"two errors occurred: {mock_error.mock_calls}"
        assert "ProcessingCriticalError: really bad things happened" in mock_error.call_args[0][0]
        assert self.pipeline._output["dummy"].store.call_count == 0, "no event in output"
        assert (
            self.pipeline._output["dummy"].store_failed.call_count == 2
        ), "errored events are gone to connector error output handler"

    @mock.patch("logging.Logger.error")
    @mock.patch("logging.Logger.warning")
    def test_processor_logs_processing_error_and_warnings_separately(
        self, mock_warning, mock_error, _
    ):
        self.pipeline._setup()
        input_event1 = {"message": "first event"}
        self.pipeline._input.get_next.return_value = (input_event1, None)
        mock_rule = mock.MagicMock()
        self.pipeline._pipeline[1] = deepcopy(self.pipeline._pipeline[0])
        warning = FieldExistsWarning(mock_rule, input_event1, ["foo"])
        self.pipeline._pipeline[0].process.return_value = ProcessorResult(
            processor_name="", warnings=[warning]
        )
        error = ProcessingCriticalError("really bad things happened", mock_rule, input_event1)
        self.pipeline._pipeline[1].process.return_value = ProcessorResult(
            processor_name="", errors=[error]
        )
        self.pipeline.process_pipeline()
        assert mock_error.call_count == 1, f"one error occurred: {mock_error.mock_calls}"
        assert mock_warning.call_count == 1, f"one warning occurred: {mock_warning.mock_calls}"
        mock_error.assert_called_with(str(error))
        mock_warning.assert_called_with(str(warning))

    @mock.patch("logging.Logger.error")
    def test_critical_input_error_is_logged_error_is_stored_in_failed_events(self, mock_error, _):
        self.pipeline._setup()
        input_event = {"message": "test"}

        def raise_critical(timeout):
            raise CriticalInputError(self.pipeline._input, "mock input error", input_event)

        self.pipeline._input.metrics = mock.MagicMock()
        self.pipeline._input.metrics.number_of_errors = 0
        self.pipeline._input.get_next.return_value = (input_event, None)
        self.pipeline._input.get_next.side_effect = raise_critical
        self.pipeline.process_pipeline()
        self.pipeline._input.get_next.assert_called()
        mock_error.assert_called_with(
            str(CriticalInputError(self.pipeline._input, "mock input error", input_event))
        )
        assert self.pipeline._output["dummy"].store_failed.call_count == 1, "one error is stored"
        self.pipeline._output["dummy"].store_failed.assert_called_with(
            str(self.pipeline), input_event, {}
        )
        assert self.pipeline._output["dummy"].store.call_count == 0, "no event is stored"

    @mock.patch("logging.Logger.warning")
    def test_input_warning_is_logged(self, mock_warning, _):
        def raise_warning(_):
            raise InputWarning(self.pipeline._input, "mock input warning")

        self.pipeline._setup()
        self.pipeline._input.get_next.side_effect = raise_warning
        self.pipeline.process_pipeline()
        self.pipeline._input.get_next.assert_called()
        mock_warning.assert_called_with(
            str(InputWarning(self.pipeline._input, "mock input warning"))
        )

    @mock.patch("logging.Logger.error")
    def test_critical_output_error_is_logged_and_counted(self, mock_log_error, _):
        dummy_output = original_create({"dummy_output": {"type": "dummy_output"}})
        dummy_output.store_failed = mock.MagicMock()

        def raise_critical(event):
            raise CriticalOutputError(dummy_output, "mock output error", event)

        input_event = {"test": "message"}
        dummy_output.store = raise_critical
        dummy_output.metrics.number_of_errors = 0
        self.pipeline._setup()
        self.pipeline._output["dummy"] = dummy_output
        self.pipeline._input.get_next.return_value = (input_event, None)
        self.pipeline.process_pipeline()
        dummy_output.store_failed.assert_called()
        assert dummy_output.metrics.number_of_errors == 1, "counts error metric"
        mock_log_error.assert_called_with(
            str(CriticalOutputError(dummy_output, "mock output error", input_event))
        )

    @mock.patch("logging.Logger.warning")
    def test_warning_output_error_is_logged(self, mock_warning, _):
        dummy_output = original_create({"dummy_output": {"type": "dummy_output"}})

        def raise_warning(event):
            raise OutputWarning(self.pipeline._output["dummy"], "mock output warning")

        input_event = {"test": "message"}
        dummy_output.store = raise_warning
        self.pipeline._setup()
        self.pipeline._output["dummy"] = dummy_output
        self.pipeline._input.get_next.return_value = (input_event, None)
        self.pipeline.process_pipeline()
        mock_warning.assert_called_with(
            str(OutputWarning(self.pipeline._output["dummy"], "mock output warning"))
        )

    @mock.patch("logging.Logger.error")
    def test_processor_fatal_input_error_is_logged_pipeline_is_shutdown(self, mock_error, _):
        self.pipeline._setup()

        def raise_fatal_input_error(event):
            raise FatalInputError(self.pipeline._input, "fatal input error")

        self.pipeline._input = original_create({"dummy": {"type": "dummy_input", "documents": []}})
        self.pipeline._input.get_next = mock.MagicMock(side_effect=raise_fatal_input_error)
        self.pipeline._shut_down = mock.MagicMock()
        self.pipeline.run()
        self.pipeline._input.get_next.assert_called()
        self.pipeline._shut_down.assert_called()
        mock_error.assert_called_with(
            str(FatalInputError(self.pipeline._input, "fatal input error"))
        )

    @mock.patch("logprep.framework.pipeline.Pipeline._shut_down")
    @mock.patch("logging.Logger.error")
    def test_processor_fatal_output_error_is_logged_pipeline_is_shutdown(
        self, mock_log_error, mock_shut_down, _
    ):
        self.pipeline._setup()
        self.pipeline._input.get_next.return_value = ({"some": "event"}, None)
        raised_error = FatalOutputError(mock.MagicMock(), "fatal output error")
        self.pipeline._output["dummy"].store.side_effect = raised_error
        self.pipeline.run()
        self.pipeline._output["dummy"].store.assert_called()
        mock_log_error.assert_called_with(str(raised_error))
        mock_shut_down.assert_called()

    @mock.patch("logging.Logger.error")
    def test_processor_fatal_output_error_in_setup_is_logged(self, mock_log_error, _):
        self.pipeline._output = {"dummy": mock.MagicMock()}
        raised_error = FatalOutputError(mock.MagicMock(), "bad things happened")
        self.pipeline._output["dummy"].setup.side_effect = raised_error
        self.pipeline.run()
        mock_log_error.assert_called_with(str(raised_error))

    def test_extra_data_tuple_is_passed_to_store_custom(self, _):
        self.pipeline._setup()
        self.pipeline._input.get_next.return_value = ({"some": "event"}, None)
        self.pipeline._pipeline[1] = deepcopy(self.pipeline._pipeline[0])
        self.pipeline._pipeline[1].process.return_value = ProcessorResult(
            processor_name="", data=[({"foo": "bar"}, ({"dummy": "target"},))]
        )
        self.pipeline._pipeline.append(deepcopy(self.pipeline._pipeline[0]))
        self.pipeline.process_pipeline()
        assert self.pipeline._input.get_next.call_count == 1
        assert self.pipeline._output["dummy"].store_custom.call_count == 1
        self.pipeline._output["dummy"].store_custom.assert_called_with({"foo": "bar"}, "target")

    def test_store_custom_calls_all_defined_outputs(self, _):
        self.pipeline._output.update({"dummy1": mock.MagicMock()})
        self.pipeline._setup()
        self.pipeline._pipeline[1] = deepcopy(self.pipeline._pipeline[0])
        self.pipeline._pipeline[1].process.return_value = ProcessorResult(
            processor_name="",
            data=[
                (
                    {"foo": "bar"},
                    ({"dummy": "target"}, {"dummy1": "second_target"}),
                )
            ],
        )
        self.pipeline._pipeline.append(deepcopy(self.pipeline._pipeline[0]))
        self.pipeline._input.get_next.return_value = ({"some": "event"}, None)
        self.pipeline.process_pipeline()
        assert self.pipeline._input.get_next.call_count == 1
        assert self.pipeline._output["dummy"].store_custom.call_count == 1
        assert self.pipeline._output["dummy1"].store_custom.call_count == 1
        self.pipeline._output["dummy"].store_custom.assert_called_with({"foo": "bar"}, "target")
        self.pipeline._output["dummy1"].store_custom.assert_called_with(
            {"foo": "bar"}, "second_target"
        )

    def test_extra_data_list_is_passed_to_store_custom(self, _):
        self.pipeline._setup()
        self.pipeline._pipeline[1] = deepcopy(self.pipeline._pipeline[0])
        self.pipeline._pipeline[1].process.return_value = ProcessorResult(
            processor_name="", data=[({"foo": "bar"}, ({"dummy": "target"},))]
        )
        self.pipeline._pipeline.append(deepcopy(self.pipeline._pipeline[0]))
        self.pipeline._input.get_next.return_value = ({"some": "event"}, None)
        self.pipeline.process_pipeline()
        assert self.pipeline._input.get_next.call_count == 1
        assert self.pipeline._output["dummy"].store_custom.call_count == 1
        self.pipeline._output["dummy"].store_custom.assert_called_with({"foo": "bar"}, "target")

    def test_setup_adds_versions_information_to_input_connector_config(self, mock_create):
        self.pipeline._setup()
        called_input_config = mock_create.call_args_list[1][0][0]["dummy"]
        assert "version_information" in called_input_config, "ensure version_information is added"
        assert "logprep" in called_input_config.get("version_information"), "ensure logprep key"
        assert "configuration" in called_input_config.get("version_information"), "ensure config"
        assert called_input_config.get("version_information").get("logprep"), "ensure values"
        assert called_input_config.get("version_information").get("configuration"), "ensure values"

    def test_setup_connects_output_with_input(self, _):
        self.pipeline._setup()
        assert self.pipeline._output["dummy"].input_connector == self.pipeline._input

    def test_setup_connects_input_with_output(self, _):
        self.pipeline._setup()
        assert self.pipeline._input.output_connector == self.pipeline._output["dummy"]

    def test_pipeline_does_not_call_batch_finished_callback_if_output_store_does_not_return_true(
        self, _
    ):
        self.pipeline._setup()
        self.pipeline._input.get_next.return_value = ({"some": "event"}, None)
        self.pipeline._input.batch_finished_callback = mock.MagicMock()
        self.pipeline._output["dummy"].store = mock.MagicMock()
        self.pipeline._output["dummy"].store.return_value = None
        self.pipeline.process_pipeline()
        self.pipeline._input.batch_finished_callback.assert_not_called()

    def test_retrieve_and_process_data_calls_store_failed_for_non_critical_error_message(self, _):
        self.pipeline._setup()
        self.pipeline._input.get_next.return_value = ({"some": "event"}, "This is non critical")
        self.pipeline.process_pipeline()
        self.pipeline._output["dummy"].store_failed.assert_called_with(
            "This is non critical", {"some": "event"}, None
        )

    def test_shut_down_drains_input_queues(self, _):
        self.pipeline._setup()
        input_config = {
            "testinput": {
                "type": "http_input",
                "uvicorn_config": {
                    "host": "127.0.0.1",
                    "port": 9000,
                    "ssl_certfile": "tests/testdata/acceptance/http_input/cert.crt",
                    "ssl_keyfile": "tests/testdata/acceptance/http_input/cert.key",
                },
                "endpoints": {"/json": "json", "/jsonl": "jsonl", "/plaintext": "plaintext"},
            }
        }
        self.pipeline._input = original_create(input_config)
        self.pipeline._input.pipeline_index = 1
        self.pipeline._input.messages = multiprocessing.Queue(-1)
        self.pipeline._input.setup()
        self.pipeline._input.messages.put({"message": "test message"})
        assert self.pipeline._input.messages.qsize() == 1
        self.pipeline._shut_down()
        assert self.pipeline._input.messages.qsize() == 0

    def test_pipeline_raises_http_error_from_factory_create(self, mock_create):
        mock_create.side_effect = requests.HTTPError()
        with raises(requests.HTTPError):
            self.pipeline._setup()

    def test_multiple_outputs(self, _):
        output_config = {"kafka_output": {}, "opensearch_output": {}}
        self.pipeline._logprep_config.output = output_config
        self.pipeline._setup()
        assert isinstance(self.pipeline._output, dict)
        assert len(self.pipeline._output) == 2

    def test_output_creates_real_outputs(self, _):
        self.pipeline._logprep_config.output = {
            "dummy1": {"type": "dummy_output", "default": False},
            "dummy2": {"type": "dummy_output"},
        }
        with mock.patch("logprep.factory.Factory.create", original_create):
            output = self.pipeline._output
            assert isinstance(output, dict)
            for output_connector in output.items():
                assert isinstance(output_connector[1], Output)
        assert not self.pipeline._output["dummy1"].default

    def test_process_pipeline_runs_scheduled_tasks(self, _):
        self.pipeline._logprep_config.output = {
            "dummy": {"type": "dummy_output"},
        }
        with mock.patch("logprep.factory.Factory.create", original_create):
            output = self.pipeline._output

        mock_task = mock.MagicMock()
        self.pipeline._get_event = mock.MagicMock()
        self.pipeline._store_event = mock.MagicMock()
        self.pipeline.process_event = mock.MagicMock()
        output["dummy"]._schedule_task(task=mock_task, seconds=30)
        with mock.patch("schedule.Job.should_run", return_value=True):
            self.pipeline.process_pipeline()
        mock_task.assert_called()

    def test_event_with_critical_input_parsing_error_is_stored_in_error_output(self, _):
        self.pipeline._setup()
        error = CriticalInputParsingError(self.pipeline._input, "test-error", "raw_input")
        self.pipeline._input.get_next = mock.MagicMock()
        self.pipeline._input.get_next.side_effect = error
        self.pipeline._output = {"dummy": mock.MagicMock()}
        self.pipeline.process_pipeline()
        self.pipeline._output["dummy"].store_failed.assert_called()

    def test_stop_breaks_while_loop_and_shutdown_is_called(self, _):
        iterations = [None, None, 1]
        self.pipeline._shut_down = mock.MagicMock()

        def continue_iterating_mock():
            effect = iterations.pop(0)
            if effect is None:
                return True
            self.pipeline.stop()

        self.pipeline.process_pipeline = mock.MagicMock()
        self.pipeline.process_pipeline.side_effect = continue_iterating_mock
        self.pipeline.run()
        self.pipeline._shut_down.assert_called()

    @mock.patch("logging.Logger.error")
    def test_shutdown_logs_fatal_errors(self, mock_error, _):
        error = FatalOutputError(mock.MagicMock(), "fatal error")
        self.pipeline._output["dummy"].shut_down.side_effect = error
        self.pipeline._shut_down()
        self.pipeline._output["dummy"].shut_down.assert_called_once()
        logger_call = f"Couldn't gracefully shut down pipeline due to: {error}"
        mock_error.assert_called_with(logger_call)

    def test_pipeline_result_provides_event_received(self, _):
        self.pipeline._setup()
        event = {"some": "event"}
        self.pipeline._input.get_next.return_value = (event, None)
        generic_adder = original_create(
            {
                "generic_adder": {
                    "type": "generic_adder",
                    "specific_rules": [
                        {"filter": "some", "generic_adder": {"add": {"field": "foo"}}}
                    ],
                    "generic_rules": [],
                }
            }
        )
        self.pipeline._pipeline = [generic_adder]
        result = self.pipeline.process_pipeline()
        assert result.event_received is not event, "event_received is a copy"
        assert result.event_received == {"some": "event"}, "received event is as expected"
        assert result.event == {"some": "event", "field": "foo"}, "processed event is as expected"

    def test_process_event_can_be_bypassed_with_no_pipeline(self, _):
        self.pipeline._pipeline = []
        self.pipeline._input.get_next.return_value = ({"some": "event"}, None)
        with mock.patch("logprep.framework.pipeline.Pipeline.process_event") as mock_process_event:
            mock_process_event.return_value = None
            result = self.pipeline.process_pipeline()
        mock_process_event.assert_not_called()
        assert isinstance(result, type(None))


class TestPipelineWithActualInput:
    def setup_method(self):
        self.config = Configuration.from_sources(["tests/testdata/config/config.yml"])
        self.config.output = {}
        self.config.process_count = 1
        self.config.input = {
            "test_input": {
                "type": "dummy_input",
                "documents": [],
                "preprocessing": {"log_arrival_time_target_field": "arrival_time"},
            }
        }

    def test_pipeline_without_output_connector_and_one_input_event_and_preprocessors(self):
        self.config.input["test_input"]["documents"] = [{"applyrule": "yes"}]
        pipeline = Pipeline(config=self.config)
        assert pipeline._output is None
        result = pipeline.process_pipeline()
        assert result.event["label"] == {"reporter": ["windows"]}
        assert "arrival_time" in result.event

    def test_process_event_processes_without_input_and_without_output(self):
        event = {"applyrule": "yes"}
        expected_event = {"applyrule": "yes", "label": {"reporter": ["windows"]}}
        self.config.input = {}
        pipeline = Pipeline(config=self.config)
        assert pipeline._output is None
        assert pipeline._input is None
        pipeline.process_event(event)
        assert event == expected_event

    def test_pipeline_without_output_connector_and_two_input_events_and_preprocessors(self):
        input_events = [
            {"applyrule": "yes"},
            {"winlog": {"event_data": {"IpAddress": "123.132.113.123"}}},
        ]
        self.config.input["test_input"]["documents"] = input_events
        pipeline = Pipeline(config=self.config)
        assert pipeline._output is None
        result = pipeline.process_pipeline()
        assert result.event["label"] == {"reporter": ["windows"]}
        assert "arrival_time" in result.event
        result = pipeline.process_pipeline()
        assert "pseudonym" in result.event.get("winlog", {}).get("event_data", {}).get("IpAddress")
        assert "arrival_time" in result.event

    def test_pipeline_hmac_error_message_without_output_connector(self):
        self.config.input["test_input"]["documents"] = [{"applyrule": "yes"}]
        self.config.input["test_input"]["preprocessing"] = {
            "hmac": {"target": "non_existing_field", "key": "secret", "output_field": "hmac"}
        }
        pipeline = Pipeline(config=self.config)
        assert pipeline._output is None
        result = pipeline.process_pipeline()
        assert result.event["hmac"]["hmac"] == "error"

    def test_pipeline_run_raises_assertion_when_run_without_input(self):
        self.config.input = {}
        pipeline = Pipeline(config=self.config)
        with pytest.raises(
            AssertionError, match="Pipeline should not be run without input connector"
        ):
            pipeline.run()

    def test_pipeline_run_raises_assertion_when_run_without_output(self):
        pipeline = Pipeline(config=self.config)
        with pytest.raises(
            AssertionError, match="Pipeline should not be run without output connector"
        ):
            pipeline.run()

    def test_stop_sets_continue_iterating_to_false(self):
        pipeline = Pipeline(config=self.config)
        pipeline._continue_iterating.value = True
        pipeline.stop()
        assert not pipeline._continue_iterating.value

    def test_health_returns_health_functions_without_output(self):
        pipeline = Pipeline(config=self.config)
        assert pipeline._output is None
        health = pipeline.get_health_functions()
        assert isinstance(health, Tuple)
        assert len(health) > 0
        assert all(callable(health_function) for health_function in health)

    def test_health_returns_health_functions_with_output(self):
        self.config.output = {
            "dummy_output": {"type": "dummy_output"},
        }
        pipeline = Pipeline(config=self.config)
        assert pipeline._output is not None
        health = pipeline.get_health_functions()
        assert isinstance(health, Tuple)
        assert len(health) > 0
        assert all(callable(health_function) for health_function in health)

    def test_health_returns_health_functions_with_multiple_outputs(self):
        self.config.output = {
            "dummy_output1": {"type": "dummy_output"},
            "dummy_output2": {"type": "dummy_output"},
        }
        pipeline = Pipeline(config=self.config)
        assert pipeline._output is not None
        health = pipeline.get_health_functions()
        assert isinstance(health, Tuple)
        assert len(health) > 0
        assert all(callable(health_function) for health_function in health)
