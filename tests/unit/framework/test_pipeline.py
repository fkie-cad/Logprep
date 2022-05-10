# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
from copy import deepcopy
from logging import DEBUG, WARNING, ERROR, getLogger
from multiprocessing import active_children, Lock
from queue import Empty

from _pytest.outcomes import fail
from _pytest.python_api import raises

from logprep.framework.pipeline import (
    MultiprocessingPipeline,
    MustProvideAnMPLogHandlerError,
    Pipeline,
    MustProvideALogHandlerError,
    SharedCounter,
)
from logprep.input.dummy_input import DummyInput
from logprep.input.input import (
    SourceDisconnectedError,
    FatalInputError,
    WarningInputError,
    CriticalInputError,
)
from logprep.output.dummy_output import DummyOutput
from logprep.output.output import FatalOutputError, WarningOutputError, CriticalOutputError
from logprep.processor.base.processor import BaseProcessor, ProcessingWarning
from logprep.util.multiprocessing_log_handler import MultiprocessingLogHandler
from logprep.util.processor_stats import StatsClassesController, StatusLoggerCollection
from tests.util.testhelpers import AssertEmitsLogMessage


class ConfigurationForTests:
    connector_config = {"type": "dummy", "input": [{"test": "empty"}]}
    pipeline_config = [{"donothing1": {"type": "donothing"}}, {"donothing2": {"type": "donothing"}}]
    status_logger_config = {
        "period": 300,
        "enabled": False,
    }
    log_handler = MultiprocessingLogHandler(WARNING)
    timeout = 0.001
    print_processed_period = 600
    lock = Lock()
    shared_dict = {}
    status_logger = StatusLoggerCollection(file_logger=getLogger("Mock"), prometheus_exporter=None)
    counter = SharedCounter()


class NotJsonSerializableMock:
    pass


class ProcessorWarningMockError(ProcessingWarning):
    def __init__(self):
        super().__init__("ProcessorWarningMockError")


class PipelineForTesting(Pipeline):
    ##
    # "Officially" expose the processors
    def get_processors(self):
        return self._pipeline

    ##
    # Do not remove the processors when shutting down - this allows us to
    # check their state after calling run()
    def _shut_down(self):
        self._input.shut_down()
        self._output.shut_down()

        for processor in self._pipeline:
            processor.shut_down()


class TestPipeline(ConfigurationForTests):
    def setup_method(self):
        self._check_failed_stored = None

        self.pipeline = Pipeline(
            self.connector_config,
            self.pipeline_config,
            self.status_logger_config,
            self.timeout,
            self.counter,
            self.log_handler,
            self.lock,
            self.shared_dict,
            self.status_logger,
        )
        self.clear_log_handler_queue()

    def test_fails_if_log_handler_is_not_of_type_loghandler(self):
        for not_a_log_handler in [None, 123, 45.67, TestPipeline()]:
            with raises(MustProvideALogHandlerError):
                _ = Pipeline(
                    self.connector_config,
                    self.pipeline_config,
                    self.status_logger_config,
                    self.timeout,
                    self.counter,
                    not_a_log_handler,
                    self.lock,
                    self.shared_dict,
                )

    def test_setup_builds_pipeline(self):
        assert len(self.pipeline._pipeline) == 0

        self.pipeline._setup()

        assert len(self.pipeline._pipeline) == 2
        for processor in self.pipeline._pipeline:
            assert isinstance(processor, BaseProcessor)

    def test_setup_calls_setup_on_pipeline_processors(self):
        self.pipeline._setup()

        assert len(self.pipeline._pipeline) == 2

        for processor in self.pipeline._pipeline:
            assert processor.setup_called_count == 1

    def test_shut_down_calls_shut_down_on_pipeline_processors(self):
        self.pipeline._setup()
        processors = list(self.pipeline._pipeline)

        self.pipeline._shut_down()

        for processor in processors:
            assert processor.shut_down_called_count == 1

    def test_setup_creates_connectors(self):
        assert self.pipeline._input is None
        assert self.pipeline._output is None

        self.pipeline._setup()

        assert isinstance(self.pipeline._input, DummyInput)
        assert isinstance(self.pipeline._output, DummyOutput)

    def test_setup_calls_setup_on_input_and_output(self):
        self.pipeline._setup()

        assert self.pipeline._input.setup_called_count == 1
        assert self.pipeline._output.setup_called_count == 1

    def test_passes_timeout_parameter_to_inputs_get_next(self):
        self.pipeline._setup()
        assert self.pipeline._input.last_timeout is None

        self.pipeline._retrieve_and_process_data()

        assert self.pipeline._input.last_timeout == self.timeout

    def test_empty_documents_are_not_forwarded_to_other_processors(self):
        input_data = [{"test": "1"}, {"test": "2"}, {"test": "3"}]
        pipeline = self.create_pipeline(input_data, ["donothing", "delete", "donothing"])

        for _ in range(len(input_data)):
            pipeline._retrieve_and_process_data()

        assert pipeline._pipeline[0].ps.processed_count == 3
        assert pipeline._pipeline[2].ps.processed_count == 0

    def test_empty_documents_are_not_stored_in_the_output(self):
        pipeline = self.create_pipeline([{"test": "1"}], ["delete"])

        pipeline._retrieve_and_process_data()

        assert pipeline._pipeline[0].ps.processed_count == 1
        assert len(pipeline._output.events) == 0

    def test_retrieve_and_process_data_raises_exceptions_that_occur_while_retrieving_data(self):
        pipeline = self.create_pipeline([ValueError], ["donothing"])

        with raises(ValueError):
            pipeline._retrieve_and_process_data()

    def test_stops_processing_after_receiving_source_disconnected_error(self):
        input_data = [{"test": "1"}, SourceDisconnectedError, {"test": "2"}, {"test": "3"}]
        pipeline = self.create_pipeline(input_data, ["donothing"])
        pipeline.run()

        assert len(pipeline._output.events) == 1

    def test_calls_setup_and_shut_down_on_input(self):
        pipeline = self.create_pipeline([], ["donothing"])
        pipeline.run()

        assert pipeline._input.setup_called_count == 1
        assert pipeline._input.shut_down_called_count == 1

    def test_calls_setup_and_shut_down_on_output(self):
        pipeline = self.create_pipeline([], ["donothing"])
        pipeline.run()

        assert pipeline._output.setup_called_count == 1
        assert pipeline._output.shut_down_called_count == 1

    def test_logs_source_disconnected_error_as_warning(self):
        pipeline = self.create_pipeline([{"order": 0}], ["donothing"])

        with AssertEmitsLogMessage(
            self.log_handler, WARNING, prefix="Lost or failed to establish connection to "
        ):
            pipeline.run()

    def test_all_events_provided_by_input_arrive_at_output(self):
        event_count = 5
        pipeline = self.create_pipeline([{"order": i} for i in range(event_count)], ["donothing"])

        pipeline.run()

        assert len(pipeline._output.events) == event_count
        for i in range(event_count):
            assert pipeline._output.events[i] == {"order": i}

    def test_enable_iteration_sets_iterate_to_true_stop_to_false(self):
        assert not self.pipeline._iterate()

        self.pipeline._enable_iteration()
        assert self.pipeline._iterate()

        self.pipeline.stop()
        assert not self.pipeline._iterate()

    def test_critical_input_error_is_logged_and_stored_as_failed(self):
        event = {"does_not_matter": "mock"}
        pipeline = self.create_pipeline([event], ["donothing"])

        def raise_critical_input_error(event):
            raise CriticalInputError("An error message", event)

        pipeline._output.store = raise_critical_input_error

        def check_if_failed_was_stored(msg, raw_input, event):
            self._check_failed_stored = {"msg": msg, "raw_input": raw_input, "event": event}

        pipeline._output.store_failed = check_if_failed_was_stored

        with AssertEmitsLogMessage(
            self.log_handler, ERROR, contains="A critical error occurred for input"
        ):
            pipeline._retrieve_and_process_data()
            assert (
                self._check_failed_stored["msg"]
                == "A critical error occurred for input dummy: An error message"
            )
            assert self._check_failed_stored["raw_input"] == event
            assert self._check_failed_stored["event"] == event

        assert len(pipeline._output.events) == 0
        assert pipeline._input.shut_down_called_count == 0
        assert pipeline._output.shut_down_called_count == 0

    def test_critical_output_error_is_logged_and_stored_as_failed(self):
        event = {"does_not_matter": "mock"}
        original_event = deepcopy(event)
        pipeline = self.create_pipeline([event], ["donothing"])

        def invalidate_event(event):
            event["does_not_matter"] = NotJsonSerializableMock()

        pipeline._process_event = invalidate_event

        def raise_critical_output_error(event):
            raise CriticalOutputError("An error message", original_event)

        pipeline._output.store = raise_critical_output_error

        def check_if_failed_was_stored(msg, raw_input, event):
            self._check_failed_stored = {"msg": msg, "raw_input": raw_input, "event": event}

        pipeline._output.store_failed = check_if_failed_was_stored

        with AssertEmitsLogMessage(
            self.log_handler, ERROR, contains="A critical error occurred for output"
        ):
            pipeline._retrieve_and_process_data()
            assert (
                self._check_failed_stored["msg"]
                == "A critical error occurred for output dummy: An error message"
            )
            assert self._check_failed_stored["raw_input"] == original_event
            assert self._check_failed_stored["event"] == {}

        assert len(pipeline._output.events) == 0
        assert pipeline._input.shut_down_called_count == 0
        assert pipeline._output.shut_down_called_count == 0

    def test_fatal_input_error_is_logged_and_pipeline_shuts_down(self):
        pipeline = self.create_pipeline(
            [FatalInputError, {"event": "never processed"}], ["donothing"]
        )

        with AssertEmitsLogMessage(self.log_handler, ERROR, contains="Input dummy failed"):
            pipeline.run()

        assert len(pipeline._output.events) == 0
        assert pipeline._input.shut_down_called_count == 1
        assert pipeline._output.shut_down_called_count == 1

    def test_input_warning_error_is_logged_but_processing_continues(self):
        pipeline = self.create_pipeline(
            [{"order": 0}, WarningInputError, {"order": 1}], ["donothing"]
        )

        with AssertEmitsLogMessage(
            self.log_handler, WARNING, contains="An error occurred for input dummy"
        ):
            pipeline.run()

        assert pipeline._output.events == [{"order": 0}, {"order": 1}]

    def test_fatal_output_error_is_logged_and_pipeline_shuts_down(self):
        pipeline = self.create_pipeline([{"order": 0}], ["donothing"], [FatalOutputError])

        with AssertEmitsLogMessage(self.log_handler, ERROR, contains="Output dummy failed"):
            pipeline.run()

        assert len(pipeline._output.events) == 0
        assert pipeline._input.shut_down_called_count == 1
        assert pipeline._output.shut_down_called_count == 1

    def test_output_warning_error_is_logged_but_processing_continues(self):
        pipeline = self.create_pipeline(
            [{"order": 0}, {"order": 1}], ["donothing"], [WarningOutputError]
        )

        with AssertEmitsLogMessage(
            self.log_handler, WARNING, contains="An error occurred for output dummy"
        ):
            pipeline.run()

        assert pipeline._output.events == [{"order": 1}]

    def test_processor_warning_error_is_logged_but_processing_continues(self):
        input_data = [{"order": 0}, {"order": 1}]
        pipeline_config = [
            {"before": {"type": "donothing"}},
            {"failing": {"type": "donothing", "errors": [ProcessorWarningMockError]}},
            {"after": {"type": "donothing"}},
        ]

        pipeline = PipelineForTesting(
            {"type": "dummy", "input": input_data},
            pipeline_config,
            self.status_logger_config,
            self.timeout,
            self.counter,
            self.log_handler,
            self.lock,
            self.shared_dict,
        )
        with AssertEmitsLogMessage(self.log_handler, WARNING, contains="ProcessorWarningMockError"):
            pipeline.run()

        assert len(pipeline._output.events) == 2
        assert pipeline.get_processors()[0].ps.processed_count == 2
        assert pipeline.get_processors()[1].ps.processed_count == 1  # failing
        assert pipeline.get_processors()[2].ps.processed_count == 2

    def test_processor_critical_error_is_logged_event_is_stored_in_error_output(self):
        input_data = [{"order": 0}, {"order": 1}]
        pipeline_config = [
            {"before": {"type": "donothing"}},
            {"failing": {"type": "donothing", "errors": [Exception]}},
            {"after": {"type": "donothing"}},
        ]

        pipeline = PipelineForTesting(
            {"type": "dummy", "input": input_data},
            pipeline_config,
            self.status_logger_config,
            self.timeout,
            self.counter,
            self.log_handler,
            self.lock,
            self.shared_dict,
        )
        with AssertEmitsLogMessage(
            self.log_handler,
            ERROR,
            contains="A critical error occurred for processor DoNothing when processing an event, processing was aborted:",
        ):
            pipeline.run()

        assert len(pipeline._output.events) == 1
        assert len(pipeline._output.failed_events) == 1
        assert pipeline.get_processors()[0].ps.processed_count == 2
        assert pipeline.get_processors()[1].ps.processed_count == 1  # failing
        assert pipeline.get_processors()[2].ps.processed_count == 1  # does not receive first event

    def test_processor_fatal_error_is_logged_event_is_stored_in_error_output_pipeline_is_rebuilt(
        self,
    ):
        input_data = [{"order": 0}, {"order": 1}]
        pipeline_config = [
            {"before": {"type": "donothing"}},
            {"failing": {"type": "donothing", "errors": [None, Exception]}},
            {"after": {"type": "donothing"}},
        ]

        pipeline = PipelineForTesting(
            {"type": "dummy", "input": input_data},
            pipeline_config,
            self.status_logger_config,
            self.timeout,
            self.counter,
            self.log_handler,
            self.lock,
            self.shared_dict,
        )
        with AssertEmitsLogMessage(
            self.log_handler,
            ERROR,
            contains="A critical error occurred for processor DoNothing when processing an event, processing was aborted:",
        ):
            pipeline.run()

        assert len(pipeline._output.events) == 1
        assert len(pipeline._output.failed_events) == 1

    def test_extra_data_is_passed_to_store_custom(self):
        input_data = [{"order": 0}, {"order": 1}]
        extra_data = ([{"foo": "bar"}], "target")
        pipeline_config = [
            {"pipe_with_extra_data": {"type": "donothing", "extra_data": extra_data}}
        ]

        pipeline = PipelineForTesting(
            {"type": "dummy", "input": input_data},
            pipeline_config,
            self.status_logger_config,
            self.timeout,
            self.counter,
            self.log_handler,
            self.lock,
            self.shared_dict,
        )
        pipeline.run()

        assert len(pipeline._output.events) == 4
        assert pipeline._output.events[0] == {"foo": "bar"}
        assert pipeline._output.events[1] == {"order": 0}
        assert pipeline._output.events[2] == {"foo": "bar"}
        assert pipeline._output.events[3] == {"order": 1}

    def create_pipeline(self, input_data, processors, output_exceptions=None):
        connector_config = {"type": "dummy", "input": input_data}
        if not output_exceptions is None:
            connector_config["output"] = output_exceptions

        pipeline_config = []
        for item in processors:
            if item == "donothing":
                config = {"type": "donothing"}
            elif item == "delete":
                config = {"type": "delete", "i_really_want_to_delete_all_log_events": "I really do"}
            else:
                raise ValueError("No template for processor " + item)
            pipeline_config.append({f"pipeline{len(pipeline_config)}": config})

        StatsClassesController.ENABLED = True
        pipeline = Pipeline(
            connector_config,
            pipeline_config,
            self.status_logger_config,
            self.timeout,
            self.counter,
            self.log_handler,
            self.lock,
            self.shared_dict,
        )
        pipeline._setup()

        return pipeline

    def clear_log_handler_queue(self):
        try:
            while True:
                self.log_handler._queue.get(block=False)
        except Empty:
            pass


class TestMultiprocessingPipeline(ConfigurationForTests):
    def setup_class(self):
        self.log_handler = MultiprocessingLogHandler(DEBUG)

    def test_fails_if_log_handler_is_not_a_MultiprocessingLogHandler(self):
        for not_a_log_handler in [None, 123, 45.67, TestMultiprocessingPipeline()]:
            with raises(MustProvideAnMPLogHandlerError):
                MultiprocessingPipeline(
                    {},
                    [{}],
                    self.status_logger_config,
                    self.timeout,
                    not_a_log_handler,
                    self.print_processed_period,
                    self.lock,
                    self.shared_dict,
                )

    def test_does_not_fail_if_log_handler_is_a_MultiprocessingLogHandler(self):
        try:
            MultiprocessingPipeline(
                self.connector_config,
                self.pipeline_config,
                self.status_logger_config,
                self.timeout,
                self.log_handler,
                self.print_processed_period,
                self.lock,
                self.shared_dict,
            )
        except MustProvideAnMPLogHandlerError:
            fail("Must not raise this error for a correct handler!")

    def test_creates_a_new_process(self):
        children_before = active_children()
        children_running = self.start_and_stop_pipeline(
            MultiprocessingPipeline(
                self.connector_config,
                self.pipeline_config,
                self.status_logger_config,
                self.timeout,
                self.log_handler,
                self.print_processed_period,
                self.lock,
                self.shared_dict,
            )
        )

        assert len(children_running) == (len(children_before) + 1)

    def test_stop_terminates_the_process(self):
        children_running = self.start_and_stop_pipeline(
            MultiprocessingPipeline(
                self.connector_config,
                self.pipeline_config,
                self.status_logger_config,
                self.timeout,
                self.log_handler,
                self.print_processed_period,
                self.lock,
                self.shared_dict,
            )
        )
        children_after = active_children()

        assert len(children_after) == (len(children_running) - 1)

    def test_enable_iteration_sets_iterate_to_true_stop_to_false(self):
        pipeline = MultiprocessingPipeline(
            self.connector_config,
            self.pipeline_config,
            self.status_logger_config,
            self.timeout,
            self.log_handler,
            self.print_processed_period,
            self.lock,
            self.shared_dict,
        )
        assert not pipeline._iterate()

        pipeline._enable_iteration()
        assert pipeline._iterate()

        pipeline.stop()
        assert not pipeline._iterate()

    @staticmethod
    def start_and_stop_pipeline(wrapper):
        wrapper.start()
        children_running = active_children()

        wrapper.stop()
        wrapper.join()

        return children_running
