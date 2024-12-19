# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
import multiprocessing
import queue
from copy import deepcopy
from typing import Tuple
from unittest import mock

import pytest
import requests
from _pytest.python_api import raises

from logprep.abc.input import (
    CriticalInputError,
    CriticalInputParsingError,
    FatalInputError,
    Input,
    InputWarning,
)
from logprep.abc.output import (
    CriticalOutputError,
    FatalOutputError,
    Output,
    OutputWarning,
)
from logprep.abc.processor import Processor, ProcessorResult
from logprep.factory import Factory
from logprep.framework.pipeline import Pipeline, PipelineResult
from logprep.processor.base.exceptions import (
    FieldExistsWarning,
    ProcessingCriticalError,
    ProcessingWarning,
)
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
            "error_output": {"dummy": {"type": "dummy_output"}},
        }
    )


def get_mock_create():
    """
    Create a new mock_create magic mock with a default processor result. Is applied for every
    test.
    """

    def create_component(config):
        _, config = config.popitem()
        component = None
        match config:
            case {"type": component_type} if "input" in component_type:
                component = mock.create_autospec(spec=Input)
            case {"type": component_type} if "output" in component_type:
                component = mock.create_autospec(spec=Output)
            case {"type": component_type} if "processor_with_errors" in component_type:
                component = mock.create_autospec(spec=Processor)
                processor_result = mock.create_autospec(spec=ProcessorResult)
                rule = mock.MagicMock()
                rule.id = "test_rule_id"
                error = ProcessingCriticalError("this is a processing critical error", rule)
                processor_result.errors = [error]
                component.process.return_value = processor_result
            case {"type": component_type} if "processor_with_warnings" in component_type:
                component = mock.create_autospec(spec=Processor)
                processor_result = mock.create_autospec(spec=ProcessorResult)
                processor_result.warnings = [mock.MagicMock(), mock.MagicMock()]
                component.process.return_value = processor_result
            case _:
                component = mock.create_autospec(spec=Processor)
                component.process.return_value = mock.create_autospec(spec=ProcessorResult)
        component.metrics = mock.MagicMock()
        component._called_config = config
        return component

    return create_component


@pytest.fixture(name="mock_processor")
def get_mock_processor():
    mock_create = get_mock_create()
    return mock_create({"mock_processor": {"type": "mock_processor"}})


@mock.patch("logprep.factory.Factory.create", new_callable=get_mock_create)
class TestPipeline(ConfigurationForTests):
    def setup_method(self):
        self._check_failed_stored = None

        self.pipeline = Pipeline(
            pipeline_index=1,
            config=deepcopy(self.logprep_config),
            error_queue=queue.Queue(),
        )

    def test_pipeline_property_returns_pipeline(self, _):
        self.pipeline._setup()
        assert len(self.pipeline._pipeline) == 2
        assert isinstance(self.pipeline._pipeline[0], Processor)
        assert isinstance(self.pipeline._pipeline[1], Processor)

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
        self.pipeline._input.get_next.return_value = {}
        self.pipeline.process_pipeline()
        timeout = self.logprep_config.timeout
        self.pipeline._input.get_next.assert_called_with(timeout)

    def test_empty_documents_are_not_forwarded_to_other_processors(self, _, mock_processor):
        def delete_event(event) -> ProcessorResult:
            event.clear()
            return ProcessorResult(processor_name="deleter", event=event)

        mock_deleter = mock.create_autospec(spec=Processor)
        mock_deleter.process = delete_event
        last_processor = mock.create_autospec(spec=Processor)
        pipeline = [mock_processor, mock_deleter, last_processor]
        event = {"delete_me": "1"}
        _ = PipelineResult(event=event, pipeline=pipeline)
        mock_processor.process.assert_called()
        last_processor.process.assert_not_called()
        assert not event, "event was deleted"

    def test_documents_are_stored_in_the_output(self, _):
        self.pipeline._setup()
        self.pipeline._input.get_next.return_value = {"message": "test"}
        self.pipeline._store_event = mock.MagicMock()
        self.pipeline.process_pipeline()
        assert self.pipeline._store_event.call_count == 1

    def test_empty_documents_are_not_stored_in_the_output(self, _):
        def mock_process_event(event):
            event.clear()
            return PipelineResult(event=event, pipeline=self.pipeline._pipeline)

        self.pipeline.process_event = mock_process_event
        self.pipeline._setup()
        self.pipeline._input.get_next.return_value = {"message": "test"}
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
    def test_critical_output_error_is_logged_and_event_is_stored_to_error_queue(
        self, mock_error, _
    ):
        self.pipeline.enqueue_error = mock.MagicMock()
        self.pipeline._setup()
        self.pipeline._input.get_next.return_value = {"order": 1}
        failed_event = {"failed": "event"}
        raised_error = CriticalOutputError(
            self.pipeline._output["dummy"], "An error message", failed_event
        )
        self.pipeline._output["dummy"].store.side_effect = raised_error
        self.pipeline.process_pipeline()
        self.pipeline.enqueue_error.assert_called_with(raised_error)
        mock_error.assert_called_with(str(raised_error))

    @mock.patch("logging.Logger.warning")
    def test_input_warning_error_is_logged_but_processing_continues(self, mock_warning, _):
        self.pipeline._setup()

        def raise_warning_error(_):
            raise InputWarning(self.pipeline._input, "i warn you")

        self.pipeline._input.metrics = mock.MagicMock()
        self.pipeline._input.metrics.number_of_warnings = 0
        self.pipeline._input.get_next.return_value = {"order": 1}
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
        self.pipeline._input.get_next.return_value = {"order": 1}
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
        self.pipeline._input.get_next.return_value = {"message": "test"}
        mock_rule = mock.MagicMock()
        processing_warning = ProcessingWarning("not so bad", mock_rule, {"message": "test"})
        self.pipeline._pipeline[1].process.return_value = ProcessorResult(
            processor_name="mock_processor", warnings=[processing_warning]
        )
        self.pipeline.process_pipeline()
        self.pipeline._input.get_next.return_value = {"message": "test"}
        self.pipeline.process_pipeline()
        mock_warning.assert_called()
        assert "ProcessingWarning: not so bad" in mock_warning.call_args[0][0]
        assert self.pipeline._output["dummy"].store.call_count == 2, "all events are processed"

    @mock.patch("logging.Logger.error")
    def test_processing_critical_error_is_logged_event_is_stored_in_error_output(
        self, mock_error, _
    ):
        self.pipeline.error_queue = queue.Queue()
        self.pipeline._setup()
        input_event1 = {"message": "first event"}
        input_event2 = {"message": "second event"}
        self.pipeline._input.get_next.return_value = input_event1
        mock_rule = mock.MagicMock()
        self.pipeline._pipeline[1].process.return_value = ProcessorResult(
            processor_name="",
            errors=[ProcessingCriticalError("really bad things happened", mock_rule)],
        )
        self.pipeline.process_pipeline()
        self.pipeline._input.get_next.return_value = input_event2
        self.pipeline._pipeline[1].process.return_value = ProcessorResult(
            processor_name="",
            errors=[ProcessingCriticalError("really bad things happened", mock_rule)],
        )

        self.pipeline.process_pipeline()
        assert self.pipeline._input.get_next.call_count == 2, "2 events gone into processing"
        assert mock_error.call_count == 2, f"two errors occurred: {mock_error.mock_calls}"
        assert "ProcessingCriticalError: 'really bad things happened'" in mock_error.call_args[0][0]
        assert self.pipeline._output["dummy"].store.call_count == 0, "no event in output"
        queued_item = self.pipeline.error_queue.get(0.01)
        assert queued_item["event"] == str(input_event1), "first message was enqueued"
        queued_item = self.pipeline.error_queue.get(0.01)
        assert queued_item["event"] == str(input_event2), "second message was enqueued"

    @mock.patch("logging.Logger.error")
    @mock.patch("logging.Logger.warning")
    def test_processor_logs_processing_error_and_warnings_separately(
        self, mock_warning, mock_error, mock_create
    ):
        self.pipeline._setup()
        input_event1 = {"message": "first event"}
        self.pipeline._input.get_next.return_value = input_event1
        mock_rule = mock.MagicMock()
        self.pipeline._pipeline = [
            mock_create({"mock_processor1": {"type": "mock_processor"}}),
            mock_create({"mock_processor2": {"type": "mock_processor"}}),
        ]
        warning = FieldExistsWarning(mock_rule, input_event1, ["foo"])
        self.pipeline._pipeline[0].process.return_value = ProcessorResult(
            processor_name="", warnings=[warning]
        )
        error = ProcessingCriticalError("really bad things happened", mock_rule)
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
        raised_error = CriticalInputError(self.pipeline._input, "mock input error", input_event)

        def raise_critical(timeout):
            raise raised_error

        self.pipeline._input.metrics = mock.MagicMock()
        self.pipeline._input.metrics.number_of_errors = 0
        self.pipeline._input.get_next.return_value = input_event
        self.pipeline._input.get_next.side_effect = raise_critical
        self.pipeline.enqueue_error = mock.MagicMock()
        self.pipeline.process_pipeline()
        self.pipeline._input.get_next.assert_called()
        mock_error.assert_called_with(str(raised_error))
        self.pipeline.enqueue_error.assert_called_with(raised_error)
        assert self.pipeline.enqueue_error.call_count == 1, "one error is stored"
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
        self.pipeline._input.get_next.return_value = input_event
        self.pipeline.enqueue_error = mock.MagicMock()
        self.pipeline.process_pipeline()
        self.pipeline.enqueue_error.assert_called()
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
        self.pipeline._input.get_next.return_value = input_event
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
        self.pipeline._input.get_next.return_value = {"some": "event"}
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
        self.pipeline._logprep_config.pipeline = [
            {"dummy": {"type": "dummy_processor"}},
            {"dummy": {"type": "dummy_processor"}},
        ]
        self.pipeline._setup()
        self.pipeline._input.get_next.return_value = {"some": "event"}
        self.pipeline._pipeline[1].process.return_value = ProcessorResult(
            processor_name="", data=[({"foo": "bar"}, ({"dummy": "target"},))]
        )
        self.pipeline.process_pipeline()
        assert self.pipeline._input.get_next.call_count == 1
        assert self.pipeline._output["dummy"].store_custom.call_count == 1
        self.pipeline._output["dummy"].store_custom.assert_called_with({"foo": "bar"}, "target")

    def test_store_custom_calls_all_defined_outputs(self, _):
        self.pipeline._logprep_config.pipeline = [
            {"dummy": {"type": "dummy_processor"}},
            {"dummy": {"type": "dummy_processor"}},
        ]
        self.pipeline._logprep_config.output = {
            "dummy": {"type": "dummy_output"},
            "dummy1": {"type": "dummy_output"},
        }
        self.pipeline._setup()
        self.pipeline._pipeline[1].process.return_value = ProcessorResult(
            processor_name="",
            data=[
                (
                    {"foo": "bar"},
                    ({"dummy": "target"}, {"dummy1": "second_target"}),
                )
            ],
        )
        self.pipeline._input.get_next.return_value = {"some": "event"}
        self.pipeline.process_pipeline()
        assert self.pipeline._input.get_next.call_count == 1
        assert self.pipeline._output["dummy"].store_custom.call_count == 1
        assert self.pipeline._output["dummy1"].store_custom.call_count == 1
        self.pipeline._output["dummy"].store_custom.assert_called_with({"foo": "bar"}, "target")
        self.pipeline._output["dummy1"].store_custom.assert_called_with(
            {"foo": "bar"}, "second_target"
        )

    def test_setup_adds_versions_information_to_input_connector_config(self, _):
        self.pipeline._setup()
        called_input_config = self.pipeline._input._called_config
        assert "version_information" in called_input_config, "ensure version_information is added"
        assert "logprep" in called_input_config.get("version_information"), "ensure logprep key"
        assert "configuration" in called_input_config.get("version_information"), "ensure config"
        assert called_input_config.get("version_information").get("logprep"), "ensure values"
        assert called_input_config.get("version_information").get("configuration"), "ensure values"

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

    def test_pipeline_raises_http_error_from_factory_create(self, _):
        with mock.patch("logprep.factory.Factory.create") as mock_create:
            mock_create.side_effect = requests.HTTPError()
            with raises(requests.HTTPError):
                self.pipeline._setup()

    def test_multiple_outputs(self, _):
        output_config = {
            "kafka_output": {"type": "kafka_output"},
            "opensearch_output": {"type": "opensearch_output"},
        }
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
        self.pipeline.enqueue_error = mock.MagicMock()
        self.pipeline.process_pipeline()
        self.pipeline.enqueue_error.assert_called_with(error)

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

    def test_process_event_can_be_bypassed_with_no_pipeline(self, _):
        self.pipeline._pipeline = []
        self.pipeline._input.get_next.return_value = {"some": "event"}
        with mock.patch("logprep.framework.pipeline.Pipeline.process_event") as mock_process_event:
            mock_process_event.return_value = None
            result = self.pipeline.process_pipeline()
        mock_process_event.assert_not_called()
        assert isinstance(result, type(None))

    def test_enqueue_error_logs_warning_if_no_error_queue(self, _):
        error = CriticalInputError(self.pipeline._input, "test-error", "raw_input")
        self.pipeline.error_queue = None
        with mock.patch("logging.Logger.warning") as mock_warning:
            self.pipeline.enqueue_error(error)
        mock_warning.assert_called_with("No error queue defined, event was dropped")

    @pytest.mark.parametrize(
        "item, expected_event",
        [
            (
                CriticalOutputError(mock.MagicMock(), "this is an output error", "raw_input"),
                {"event": "raw_input", "errors": "this is an output error"},
            ),
            (
                CriticalOutputError(mock.MagicMock(), "this is an output error", ["raw_input"]),
                {"event": "raw_input", "errors": "this is an output error"},
            ),
            (
                CriticalOutputError(mock.MagicMock(), "another error", {"foo": "bar"}),
                {"event": "{'foo': 'bar'}", "errors": "another error"},
            ),
            (
                CriticalOutputError(
                    mock.MagicMock(),
                    "another error",
                    {"errors": "some error", "event": {"some": "event"}},
                ),
                {"event": "{'some': 'event'}", "errors": "some error"},
            ),
            (
                CriticalOutputError(
                    mock.MagicMock(), "another error", [{"foo": "bar"}, {"foo": "baz"}]
                ),
                {"event": "{'foo': 'bar'}", "errors": "another error"},
            ),
            (
                CriticalOutputError(
                    mock.MagicMock(),
                    "just another error",
                    [{"event": {"test": "message"}, "errors": {"error": "error_msg"}}],
                ),
                {"event": "{'test': 'message'}", "errors": "{'error': 'error_msg'}"},
            ),
            (
                CriticalOutputError(
                    mock.MagicMock(),
                    "another error message",
                    [
                        {"event": {"test": f"message{i}"}, "errors": {"error": "error_msg"}}
                        for i in range(2)
                    ],
                ),
                {"event": "{'test': 'message0'}", "errors": "{'error': 'error_msg'}"},
            ),
            (
                CriticalInputError(mock.MagicMock(), "this is an input error", "raw_input"),
                {"event": "raw_input", "errors": "this is an input error"},
            ),
            (
                CriticalInputParsingError(
                    mock.MagicMock(), "this is an input parsing error", "raw_input"
                ),
                {"event": "raw_input", "errors": "this is an input parsing error"},
            ),
            (
                PipelineResult(
                    event={"test": "message"},
                    pipeline=[
                        get_mock_create()(
                            {"mock_processor1": {"type": "mock_processor_with_errors"}}
                        )
                    ],
                ),
                {
                    "event": "{'test': 'message'}",
                    "errors": "'this is a processing critical error' -> rule.id: 'test_rule_id'",
                },
            ),
            (
                PipelineResult(
                    event={"test": "message"},
                    pipeline=[
                        get_mock_create()(
                            {"mock_processor1": {"type": "mock_processor_with_errors"}}
                        ),
                        get_mock_create()(
                            {"mock_processor1": {"type": "mock_processor_with_errors"}}
                        ),
                    ],
                ),
                {
                    "event": "{'test': 'message'}",
                    "errors": "'this is a processing critical error' -> rule.id: 'test_rule_id', 'this is a processing critical error' -> rule.id: 'test_rule_id'",
                },
            ),
            (
                "some string",
                {"event": "some string", "errors": "Unknown error"},
            ),
            (
                {"some": "dict"},
                {"event": "{'some': 'dict'}", "errors": "Unknown error"},
            ),
            (
                ["some", "list"],
                {"event": "some", "errors": "Unknown error"},
            ),
        ],
    )
    def test_enqueue_error_handles_items(self, _, item, expected_event):
        self.pipeline.enqueue_error(item)
        enqueued_item = self.pipeline.error_queue.get(0.01)
        assert enqueued_item == expected_event

    def test_enqueue_error_calls_batch_finished_callback(self, _):
        error = CriticalInputError(self.pipeline._input, "test-error", "raw_input")
        self.pipeline._input.batch_finished_callback = mock.MagicMock()
        self.pipeline.error_queue = queue.Queue()
        self.pipeline.enqueue_error(error)
        self.pipeline._input.batch_finished_callback.assert_called()

    def test_enqueue_error_calls_batch_finished_callback_without_error_queue(self, _):
        error = CriticalInputError(self.pipeline._input, "test-error", "raw_input")
        self.pipeline._input.batch_finished_callback = mock.MagicMock()
        self.pipeline.error_queue = None
        self.pipeline.enqueue_error(error)
        self.pipeline._input.batch_finished_callback.assert_called()

    def test_enqueue_error_logs_input_on_exception(self, _):
        error = CriticalInputError(self.pipeline._input, "test-error", "raw_input")
        self.pipeline.error_queue = queue.Queue()
        self.pipeline.error_queue.put = mock.MagicMock(side_effect=Exception)
        with mock.patch("logging.Logger.error") as mock_error:
            self.pipeline.enqueue_error(error)
        mock_error.assert_called()

    def test_enqueue_error_counts_failed_event_for_critical_output_with_single_event(self, _):
        self.pipeline._setup()
        self.pipeline.metrics.number_of_failed_events = 0
        error = CriticalOutputError(self.pipeline._output["dummy"], "error", {"some": "event"})
        self.pipeline.enqueue_error(error)
        assert self.pipeline.metrics.number_of_failed_events == 1

    def test_enqueue_error_counts_failed_event_for_multi_event_output_error(self, _):
        self.pipeline._setup()
        self.pipeline.metrics.number_of_failed_events = 0
        error = CriticalOutputError(
            self.pipeline._output["dummy"], "error", [{"some": "event"}, {"some": "other"}]
        )
        self.pipeline.enqueue_error(error)
        assert self.pipeline.metrics.number_of_failed_events == 2

    def test_enqueue_error_counts_failed_event_for_pipeline_result(self, mock_create):
        self.pipeline.metrics.number_of_failed_events = 0
        mock_result = mock.create_autospec(spec=PipelineResult)
        mock_result.pipeline = self.pipeline._pipeline
        self.pipeline.enqueue_error(mock_result)
        assert self.pipeline.metrics.number_of_failed_events == 1


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

    def test_pipeline_hmac_error_was_send_to_error_queue(self):
        self.config.input["test_input"]["documents"] = [{"applyrule": "yes"}]
        self.config.input["test_input"]["preprocessing"] = {
            "hmac": {"target": "non_existing_field", "key": "secret", "output_field": "hmac"}
        }
        pipeline = Pipeline(config=self.config)
        pipeline.enqueue_error = mock.MagicMock()
        assert pipeline._output is None
        _ = pipeline.process_pipeline()
        expected_error = CriticalInputError(
            pipeline._input,
            "Couldn't find the hmac target field 'non_existing_field'",
            b'{"applyrule":"yes"}',
        )
        pipeline.enqueue_error.assert_called_with(expected_error)

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


class TestPipelineResult:

    @pytest.mark.parametrize(
        "parameters, error, message",
        [
            (
                {
                    "event": {"some": "event"},
                    "pipeline": [],
                },
                ValueError,
                "Length of 'pipeline' must be >= 1",
            ),
            (
                {
                    "event": {"some": "event"},
                    "pipeline": [],
                    "results": [],
                },
                TypeError,
                "got an unexpected keyword argument 'results'",
            ),
            (
                {
                    "event": {"some": "event"},
                    "pipeline": [
                        Factory.create(
                            {
                                "dummy": {
                                    "type": "dropper",
                                    "rules": [],
                                }
                            }
                        )
                    ],
                    "results": [],
                },
                TypeError,
                "got an unexpected keyword argument 'results'",
            ),
            (
                {
                    "event": {"some": "event"},
                    "pipeline": [
                        Factory.create(
                            {
                                "dummy": {
                                    "type": "dropper",
                                    "rules": [],
                                }
                            }
                        )
                    ],
                },
                None,
                None,
            ),
            (
                {
                    "event": {"some": "event"},
                    "pipeline": [
                        mock.MagicMock(),
                    ],
                },
                TypeError,
                "'pipeline' must be <class 'logprep.abc.processor.Processor'",
            ),
        ],
    )
    def test_sets_attributes(self, parameters, error, message):
        if error:
            with pytest.raises(error, match=message):
                _ = PipelineResult(**parameters)
        else:
            pipeline_result = PipelineResult(**parameters)
            assert pipeline_result.event == parameters["event"]
            assert pipeline_result.pipeline == parameters["pipeline"]
            assert isinstance(pipeline_result.results[0], ProcessorResult)

    def test_pipeline_result_instantiation_produces_results(self, mock_processor):
        pipeline_result = PipelineResult(
            event={"some": "event"},
            pipeline=[
                mock_processor,
                mock_processor,
            ],
        )
        assert isinstance(pipeline_result.results[0], ProcessorResult)
        assert len(pipeline_result.results) == 2

    def test_pipeline_result_collects_errors(self, mock_processor):
        mock_processor_result = mock.create_autospec(spec=ProcessorResult)
        mock_processor_result.errors = [mock.MagicMock(), mock.MagicMock()]
        mock_processor.process.return_value = mock_processor_result
        assert len(mock_processor.process({"event": "test"}).errors) == 2
        pipeline_result = PipelineResult(
            event={"some": "event"},
            pipeline=[mock_processor],
        )
        assert isinstance(pipeline_result.results[0], ProcessorResult)
        assert len(pipeline_result.errors) == 2

    def test_pipeline_result_collects_warnings(self, mock_processor):
        mock_processor_result = mock.create_autospec(spec=ProcessorResult)
        mock_processor_result.warnings = [mock.MagicMock(), mock.MagicMock()]
        mock_processor.process.return_value = mock_processor_result
        assert len(mock_processor.process({"event": "test"}).warnings) == 2
        pipeline_result = PipelineResult(
            event={"some": "event"},
            pipeline=[mock_processor],
        )
        assert isinstance(pipeline_result.results[0], ProcessorResult)
        assert len(pipeline_result.warnings) == 2

    def test_pipeline_result_collects_data(self, mock_processor):
        mock_processor_result = mock.create_autospec(spec=ProcessorResult)
        mock_processor_result.data = [mock.MagicMock(), mock.MagicMock()]
        mock_processor.process.return_value = mock_processor_result
        assert len(mock_processor.process({"event": "test"}).data) == 2
        pipeline_result = PipelineResult(
            event={"some": "event"},
            pipeline=[mock_processor],
        )
        assert isinstance(pipeline_result.results[0], ProcessorResult)
        assert len(pipeline_result.data) == 2
