# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
from copy import deepcopy
from logging import DEBUG, WARNING, getLogger
from multiprocessing import active_children, Lock
from unittest import mock

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
from logprep.processor.base.exceptions import ProcessingWarning
from logprep.processor.processor_configuration import ProcessorConfiguration
from logprep.processor.delete.processor import Delete
from logprep.processor.delete.rule import DeleteRule
from logprep.util.multiprocessing_log_handler import MultiprocessingLogHandler
from logprep.util.processor_stats import StatusLoggerCollection


class ConfigurationForTests:
    connector_config = {"type": "dummy", "input": [{"test": "empty"}]}
    pipeline_config = ["mock_processor", "mock_processor"]
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


@mock.patch("logprep.processor.processor_factory.ProcessorFactory.create")
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

    def test_fails_if_log_handler_is_not_of_type_loghandler(self, _):
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

    def test_setup_builds_pipeline(self, mock_create):
        assert len(self.pipeline._pipeline) == 0
        self.pipeline._setup()
        assert len(self.pipeline._pipeline) == 2
        assert mock_create.call_count == 2

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

    def test_setup_creates_connectors(self, _):
        assert self.pipeline._input is None
        assert self.pipeline._output is None

        self.pipeline._setup()

        assert isinstance(self.pipeline._input, DummyInput)
        assert isinstance(self.pipeline._output, DummyOutput)

    def test_setup_calls_setup_on_input_and_output(self, _):
        self.pipeline._setup()

        assert self.pipeline._input.setup_called_count == 1
        assert self.pipeline._output.setup_called_count == 1

    def test_passes_timeout_parameter_to_inputs_get_next(self, _):
        self.pipeline._setup()
        assert self.pipeline._input.last_timeout is None

        self.pipeline._retrieve_and_process_data()

        assert self.pipeline._input.last_timeout == self.timeout

    def test_empty_documents_are_not_forwarded_to_other_processors(self, _):
        assert len(self.pipeline._pipeline) == 0
        input_data = [{"do_not_delete": "1"}, {"delete_me": "2"}, {"do_not_delete": "3"}]
        connector_config = {"type": "dummy", "input": input_data}
        self.pipeline._connector_config = connector_config
        self.pipeline._setup()
        delete_config = {
            "type": "delete",
            "specific_rules": ["tests/testdata/unit/delete/rules/specific"],
            "generic_rules": ["tests/testdata/unit/delete/rules/generic"],
        }
        processor_configuration = ProcessorConfiguration.create("delete processor", delete_config)
        delete_processor = Delete("delete processor", processor_configuration, mock.MagicMock())
        delete_rule = DeleteRule._create_from_dict({"filter": "delete_me", "delete": True})
        delete_processor._specific_tree.add_rule(delete_rule)
        self.pipeline._pipeline = [mock.MagicMock(), delete_processor, mock.MagicMock()]
        self.pipeline._create_logger()
        self.pipeline._logger.setLevel(DEBUG)
        while self.pipeline._input._documents:
            self.pipeline._retrieve_and_process_data()
        assert len(input_data) == 0, "all events were processed"
        assert self.pipeline._pipeline[0].process.call_count == 3, "called for all events"
        assert self.pipeline._pipeline[2].process.call_count == 2, "not called for deleted event"
        assert {"delete_me": "2"} not in self.pipeline._output.events
        assert len(self.pipeline._output.events) == 2

    def test_empty_documents_are_not_stored_in_the_output(self, _):
        self.pipeline._process_event = lambda x: x.clear()
        self.pipeline.run()
        assert len(self.pipeline._output.events) == 0, "output is emty after processing events"

    @mock.patch("logprep.input.dummy_input.DummyInput.setup")
    def test_setup_calls_setup_on_input(self, mock_setup, _):
        self.pipeline.run()
        mock_setup.assert_called()

    @mock.patch("logprep.output.dummy_output.DummyOutput.setup")
    def test_setup_calls_setup_on_output(self, mock_setup, _):
        self.pipeline.run()
        mock_setup.assert_called()

    @mock.patch("logprep.input.dummy_input.DummyInput.shut_down")
    def test_shut_down_calls_shut_down_on_input(self, mock_shut_down, _):
        self.pipeline.run()
        mock_shut_down.assert_called()

    @mock.patch("logprep.output.dummy_output.DummyOutput.shut_down")
    def test_shut_down_calls_shut_down_on_output(self, mock_shut_down, _):
        self.pipeline.run()
        mock_shut_down.assert_called()

    @mock.patch("logging.Logger.warning")
    @mock.patch("logprep.input.dummy_input.DummyInput.get_next")
    def test_logs_source_disconnected_error_as_warning(self, mock_get_next, mock_warning, _):
        mock_get_next.side_effect = SourceDisconnectedError
        self.pipeline.run()
        mock_warning.assert_called()
        assert "Lost or failed to establish connection to dummy" in mock_warning.call_args[0]

    def test_all_events_provided_by_input_arrive_at_output(self, _):
        input_data = [{"test": "1"}, {"test": "2"}, {"test": "3"}]
        expected_output_data = deepcopy(input_data)
        connector_config = {"type": "dummy", "input": input_data}
        self.pipeline._connector_config = connector_config
        self.pipeline._setup()
        self.pipeline.run()
        assert self.pipeline._output.events == expected_output_data

    def test_enable_iteration_sets_iterate_to_true_stop_to_false(self, _):
        assert not self.pipeline._iterate()

        self.pipeline._enable_iteration()
        assert self.pipeline._iterate()

        self.pipeline.stop()
        assert not self.pipeline._iterate()

    @mock.patch("logging.Logger.error")
    @mock.patch("logprep.input.dummy_input.DummyInput.get_next")
    def test_critical_input_error_is_logged_and_stored_as_failed(
        self, mock_get_next, mock_error, _
    ):
        def raise_critical_input_error(event):
            raise CriticalInputError("An error message", event)

        mock_get_next.side_effect = raise_critical_input_error
        self.pipeline._setup()
        self.pipeline._retrieve_and_process_data()
        assert len(self.pipeline._output.events) == 0
        mock_error.assert_called()
        assert (
            "A critical error occurred for input dummy: An error message" in mock_error.call_args[0]
        )
        assert len(self.pipeline._output.failed_events) == 1

    @mock.patch("logging.Logger.error")
    @mock.patch("logprep.output.dummy_output.DummyOutput.store")
    @mock.patch("logprep.input.dummy_input.DummyInput.get_next")
    def test_critical_output_error_is_logged_and_stored_as_failed(
        self, mock_get_next, mock_store, mock_error, _
    ):
        mock_get_next.return_value = {"order": 1}

        def raise_critical_output_error(event):
            raise CriticalOutputError("An error message", event)

        mock_store.side_effect = raise_critical_output_error
        self.pipeline._setup()
        self.pipeline._retrieve_and_process_data()
        assert len(self.pipeline._output.events) == 0
        mock_error.assert_called()
        assert (
            "A critical error occurred for output dummy: An error message"
            in mock_error.call_args[0]
        )
        assert len(self.pipeline._output.failed_events) == 1

    @mock.patch("logging.Logger.warning")
    @mock.patch("logprep.input.dummy_input.DummyInput.get_next")
    def test_input_warning_error_is_logged_but_processing_continues(
        self, mock_get_next, mock_warning, _
    ):
        mock_get_next.return_value = {"order": 1}
        self.pipeline._setup()
        self.pipeline._retrieve_and_process_data()
        mock_get_next.side_effect = WarningInputError
        self.pipeline._retrieve_and_process_data()
        mock_get_next.side_effect = None
        self.pipeline._retrieve_and_process_data()
        assert mock_get_next.call_count == 3
        assert mock_warning.call_count == 1
        assert len(self.pipeline._output.events) == 2

    @mock.patch("logging.Logger.warning")
    @mock.patch("logprep.output.dummy_output.DummyOutput.store")
    @mock.patch("logprep.input.dummy_input.DummyInput.get_next")
    def test_output_warning_error_is_logged_but_processing_continues(
        self, mock_get_next, mock_store, mock_warning, _
    ):
        mock_get_next.return_value = {"order": 1}
        self.pipeline._setup()
        self.pipeline._retrieve_and_process_data()
        mock_store.side_effect = WarningOutputError
        self.pipeline._retrieve_and_process_data()
        mock_store.side_effect = None
        self.pipeline._retrieve_and_process_data()
        assert mock_get_next.call_count == 3
        assert mock_warning.call_count == 1
        assert mock_store.call_count == 3

    @mock.patch("logging.Logger.warning")
    def test_processor_warning_error_is_logged_but_processing_continues(self, mock_warning, _):
        input_data = [{"order": 0}, {"order": 1}]
        connector_config = {"type": "dummy", "input": input_data}
        self.pipeline._connector_config = connector_config
        self.pipeline._create_logger()
        self.pipeline._create_connectors()
        error_mock = mock.MagicMock()
        error_mock.process = mock.MagicMock()
        error_mock.process.side_effect = ProcessorWarningMockError
        self.pipeline._pipeline = [
            mock.MagicMock(),
            error_mock,
            mock.MagicMock(),
        ]
        self.pipeline._retrieve_and_process_data()
        self.pipeline._retrieve_and_process_data()
        mock_warning.assert_called()
        assert (
            "ProcessorWarningMockError" in mock_warning.call_args[0][0]
        ), "the log message was written"
        assert len(self.pipeline._output.events) == 2, "all events are processed"

    @mock.patch("logging.Logger.error")
    def test_processor_critical_error_is_logged_event_is_stored_in_error_output(
        self, mock_error, _
    ):
        input_data = [{"order": 0}, {"order": 1}]
        connector_config = {"type": "dummy", "input": input_data}
        self.pipeline._connector_config = connector_config
        self.pipeline._create_logger()
        self.pipeline._create_connectors()
        error_mock = mock.MagicMock()
        error_mock.process = mock.MagicMock()
        error_mock.process.side_effect = Exception
        self.pipeline._pipeline = [
            mock.MagicMock(),
            error_mock,
            mock.MagicMock(),
        ]
        self.pipeline._output.store_failed = mock.MagicMock()
        self.pipeline._retrieve_and_process_data()
        self.pipeline._retrieve_and_process_data()
        mock_error.assert_called()
        assert (
            "A critical error occurred for processor" in mock_error.call_args[0][0]
        ), "the log message was written"
        assert len(self.pipeline._output.events) == 0, "no event in output"
        assert (
            self.pipeline._output.store_failed.call_count == 2
        ), "errored events are gone to connector error output handler"

    @mock.patch("logprep.input.dummy_input.DummyInput.get_next")
    @mock.patch("logging.Logger.error")
    def test_critical_input_error_is_logged_error_is_stored_in_failed_events(
        self, mock_error, mock_get_next, _
    ):
        def raise_critical(args):
            raise CriticalInputError("mock input error", args)

        mock_get_next.side_effect = raise_critical
        self.pipeline._setup()
        self.pipeline._retrieve_and_process_data()
        mock_get_next.assert_called()
        mock_error.assert_called()
        assert (
            "A critical error occurred for input dummy: mock input error" in mock_error.call_args[0]
        ), "error message is logged"
        assert len(self.pipeline._output.failed_events) == 1
        assert len(self.pipeline._output.events) == 0

    @mock.patch("logprep.input.dummy_input.DummyInput.get_next")
    @mock.patch("logging.Logger.warning")
    def test_input_warning_is_logged(self, mock_warning, mock_get_next, _):
        def raise_warning(args):
            raise WarningInputError("mock input warning", args)

        mock_get_next.side_effect = raise_warning
        self.pipeline._setup()
        self.pipeline._retrieve_and_process_data()
        mock_get_next.assert_called()
        mock_warning.assert_called()
        assert (
            "An error occurred for input dummy:" in mock_warning.call_args[0][0]
        ), "error message is logged"

    @mock.patch("logprep.input.dummy_input.DummyInput.get_next", return_value={"mock": "event"})
    @mock.patch("logprep.output.dummy_output.DummyOutput.store")
    @mock.patch("logging.Logger.error")
    def test_critical_output_error_is_logged(self, mock_error, mock_store, mock_get_next, _):
        def raise_critical(args):
            raise CriticalOutputError("mock output error", args)

        mock_store.side_effect = raise_critical
        self.pipeline._setup()
        self.pipeline._retrieve_and_process_data()
        mock_store.assert_called()
        mock_error.assert_called()
        assert (
            "A critical error occurred for output dummy: mock output error"
            in mock_error.call_args[0]
        ), "error message is logged"

    @mock.patch("logprep.input.dummy_input.DummyInput.get_next", return_value={"mock": "event"})
    @mock.patch("logprep.output.dummy_output.DummyOutput.store")
    @mock.patch("logging.Logger.warning")
    def test_warning_output_error_is_logged(self, mock_warning, mock_store, mock_get_next, _):
        def raise_warning(args):
            raise WarningOutputError("mock output warning", args)

        mock_store.side_effect = raise_warning
        self.pipeline._setup()
        self.pipeline._retrieve_and_process_data()
        mock_store.assert_called()
        mock_warning.assert_called()
        assert (
            "An error occurred for output dummy:" in mock_warning.call_args[0][0]
        ), "error message is logged"

    @mock.patch("logprep.framework.pipeline.Pipeline._shut_down")
    @mock.patch("logprep.input.dummy_input.DummyInput.get_next")
    @mock.patch("logging.Logger.error")
    def test_processor_fatal_input_error_is_logged_pipeline_is_rebuilt(
        self, mock_error, mock_get_next, mock_shut_down, _
    ):
        mock_get_next.side_effect = FatalInputError
        self.pipeline.run()
        mock_get_next.assert_called()
        mock_error.assert_called()
        assert "Input dummy failed:" in mock_error.call_args[0][0], "error message is logged"
        mock_shut_down.assert_called()

    @mock.patch("logprep.input.dummy_input.DummyInput.get_next", return_value={"mock": "event"})
    @mock.patch("logprep.framework.pipeline.Pipeline._shut_down")
    @mock.patch("logprep.output.dummy_output.DummyOutput.store")
    @mock.patch("logging.Logger.error")
    def test_processor_fatal_output_error_is_logged_pipeline_is_rebuilt(
        self, mock_error, mock_store, mock_shut_down, mock_get_next, _
    ):
        mock_store.side_effect = FatalOutputError
        self.pipeline.run()
        mock_store.assert_called()
        mock_error.assert_called()
        assert "Output dummy failed:" in mock_error.call_args[0][0], "error message is logged"
        mock_shut_down.assert_called()

    @mock.patch("logprep.output.dummy_output.DummyOutput.store_custom")
    @mock.patch("logprep.input.dummy_input.DummyInput.get_next", return_value={"mock": "event"})
    def test_extra_dat_tuple_is_passed_to_store_custom(self, mock_get_next, mock_store_custom, _):
        self.pipeline._setup()
        processor_with_exta_data = mock.MagicMock()
        processor_with_exta_data.process = mock.MagicMock()
        processor_with_exta_data.process.return_value = ([{"foo": "bar"}], "target")
        self.pipeline._pipeline = [mock.MagicMock(), processor_with_exta_data, mock.MagicMock()]
        self.pipeline._retrieve_and_process_data()
        mock_get_next.call_count = 1
        mock_store_custom.call_count = 1
        mock_store_custom.assert_called_with({"foo": "bar"}, "target")

    @mock.patch("logprep.output.dummy_output.DummyOutput.store_custom")
    @mock.patch("logprep.input.dummy_input.DummyInput.get_next", return_value={"mock": "event"})
    def test_extra_dat_list_is_passed_to_store_custom(self, mock_get_next, mock_store_custom, _):
        self.pipeline._setup()
        processor_with_exta_data = mock.MagicMock()
        processor_with_exta_data.process = mock.MagicMock()
        processor_with_exta_data.process.return_value = [([{"foo": "bar"}], "target")]
        self.pipeline._pipeline = [mock.MagicMock(), processor_with_exta_data, mock.MagicMock()]
        self.pipeline._retrieve_and_process_data()
        mock_get_next.call_count = 1
        mock_store_custom.call_count = 1
        mock_store_custom.assert_called_with({"foo": "bar"}, "target")


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
