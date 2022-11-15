# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
from logging import WARNING, Logger, INFO, ERROR
from time import time, sleep
from unittest import mock

from pytest import raises

from logprep.framework.pipeline import MultiprocessingPipeline
from logprep.framework.pipeline_manager import PipelineManager, MustSetConfigurationFirstError
from logprep.metrics.metric import MetricTargets
from logprep.util.configuration import Configuration
from tests.testdata.metadata import path_to_config
from tests.util.testhelpers import AssertEmitsLogMessage, HandlerStub, AssertEmitsLogMessages


class MultiprocessingPipelineMock(MultiprocessingPipeline):
    process_count = 0

    def __init__(self):
        self.was_started = False
        self.was_stopped = False

        self.process_is_alive = False
        self._id = MultiprocessingPipelineMock.process_count

        MultiprocessingPipelineMock.process_count += 1

    def __repr__(self):
        return f"MultiprocessingLogprepWrapperMock-{self._id}"

    def start(self):
        self.was_started = True
        self.process_is_alive = True

    def stop(self):
        self.was_stopped = True
        self.process_is_alive = False

    def is_alive(self):
        return self.process_is_alive

    def join(self, timeout=None):
        pass


class PipelineManagerForTesting(PipelineManager):
    def _create_pipeline(self, index):
        return MultiprocessingPipelineMock()


class TestPipelineManager:
    def setup_class(self):
        self.config = Configuration.create_from_yaml(path_to_config)
        self.handler = HandlerStub()
        self.logger = Logger("test")
        self.metric_targets = MetricTargets(file_target=self.logger, prometheus_target=None)
        self.logger.addHandler(self.handler)

        self.manager = PipelineManagerForTesting(self.logger, self.metric_targets)
        self.manager.set_configuration(self.config)

    def test_create_pipeline_fails_if_config_is_unset(self):
        manager = PipelineManager(self.logger, self.metric_targets)

        with raises(
            MustSetConfigurationFirstError,
            match="Failed to create new pipeline: Configuration is unset",
        ):
            pipeline_index = 1
            manager._create_pipeline(pipeline_index)

    def test_get_count_returns_count_of_pipelines(self):
        for count in range(5):
            self.manager.set_count(count)

            assert self.manager.get_count() == count

    def test_increase_to_count_adds_required_number_of_pipelines(self):
        process_count = MultiprocessingPipelineMock.process_count
        self.manager.set_count(0)
        self.manager._increase_to_count(4)

        assert MultiprocessingPipelineMock.process_count == (4 + process_count)

    def test_increase_to_count_does_nothing_if_count_is_equal_or_less_to_current_count(self):
        current_pipelines = list(self.manager._pipelines)

        for count in range(len(current_pipelines) + 1):
            self.manager._increase_to_count(count)

            assert self.manager._pipelines == current_pipelines

    def test_processes_created_by_run_are_started(self):
        self.manager.set_count(3)

        for processor in self.manager._pipelines:
            assert processor.was_started

    def test_replace_pipelines_replaces_all_pipelines(self):
        self.manager.set_count(3)
        old_pipelines = list(self.manager._pipelines)

        self.manager.replace_pipelines()

        assert len(self.manager._pipelines) == len(old_pipelines)
        for logprep_instance in self.manager._pipelines:
            assert logprep_instance not in old_pipelines

    def test_decrease_to_count_removes_required_number_of_pipelines(self):
        self.manager._increase_to_count(3)

        self.manager._decrease_to_count(2)
        assert len(self.manager._pipelines) == 2

        self.manager._decrease_to_count(1)
        assert len(self.manager._pipelines) == 1

    def test_decrease_to_count_does_nothing_if_count_is_equal_or_more_than_current_count(self):
        current_pipelines = list(self.manager._pipelines)

        for count in range(len(current_pipelines) + 1):
            self.manager._decrease_to_count(len(current_pipelines) + count)

            assert self.manager._pipelines == current_pipelines

    def test_set_count_increases_or_decreases_count_of_pipelines_as_needed(self):
        self.manager._increase_to_count(3)

        self.manager.set_count(2)
        assert len(self.manager._pipelines) == 2

        self.manager.set_count(5)
        assert len(self.manager._pipelines) == 5

    def test_set_count_does_nothing_if_count_is_equal_to_current_count_of_pipelines(self):
        current_pipelines = list(self.manager._pipelines)
        self.manager.set_count(len(current_pipelines))

        assert self.manager._pipelines == current_pipelines

    def test_remove_failed_pipelines_removes_terminated_pipelines(self):
        self.manager.set_count(2)
        failed_pipeline = self.manager._pipelines[-1]
        failed_pipeline.process_is_alive = False

        self.manager.remove_failed_pipeline()

        assert not failed_pipeline in self.manager._pipelines

    def test_remove_failed_pipelines_logs_warning_for_removed_failed_pipelines(self):
        self.manager.set_count(2)
        failed_pipeline = self.manager._pipelines[-1]
        failed_pipeline.process_is_alive = False

        with AssertEmitsLogMessage(self.handler, WARNING, message="Removed 1 failed pipeline(s)"):
            self.manager.remove_failed_pipeline()

    def test_handle_logs_into_logger_returns_after_timeout(self):
        self.manager.set_count(1)
        timeout = 0.1

        start = time()
        self.manager.handle_logs_into_logger(self.logger, timeout=timeout)
        duration = time() - start

        assert duration >= timeout
        assert duration <= (1.5 * timeout)

    def test_handle_logs_into_logger_forwards_log_record_to_logger(self):
        self.manager.set_count(1)
        timeout = 0.1

        handler = HandlerStub()

        logger_in = Logger("test_handle_logs_into_logger_forwards_log_record_to_logger")
        logger_in.addHandler(self.manager._log_handler)
        logger_in.error("this is a test")

        logger_out = Logger("test_handle_logs_into_logger_forwards_log_record_to_logger")
        logger_out.addHandler(handler)

        with AssertEmitsLogMessage(handler, ERROR, "this is a test"):
            self.manager.handle_logs_into_logger(logger_out, timeout=timeout)

    def test_handle_logs_into_logger_retrieves_all_logs_with_a_single_call(self):
        self.manager.set_count(1)
        timeout = 0.1

        handler = HandlerStub()

        logger_in = Logger("test_handle_logs_into_logger_forwards_log_record_to_logger")
        logger_in.addHandler(self.manager._log_handler)
        logger_in.error("msg1")
        logger_in.warning("msg2")
        logger_in.info("msg3")

        logger_out = Logger("test_handle_logs_into_logger_forwards_log_record_to_logger")
        logger_out.addHandler(handler)
        # NOTE: This test failed once in a while (fewer messages received than expected),
        # this sleep seems to have fixed it, try adjusting, if the test fails randomly.
        sleep(0.01)  # nosemgrep

        with AssertEmitsLogMessages(handler, [ERROR, WARNING, INFO], ["msg1", "msg2", "msg3"]):
            self.manager.handle_logs_into_logger(logger_out, timeout=timeout)

    def test_stop_terminates_processes_created(self):
        self.manager.set_count(3)
        logprep_instances = list(self.manager._pipelines)

        self.manager.stop()

        assert len(logprep_instances) == 3

        for logprep_instance in logprep_instances:
            assert logprep_instance.was_started and logprep_instance.was_stopped

    @mock.patch("logprep.util.prometheus_exporter.PrometheusStatsExporter")
    def test_remove_failed_pipelines_removes_metrics_database_if_prometheus_target_is_configured(
        self, prometheus_exporter_mock
    ):
        failed_pipeline = mock.MagicMock()
        failed_pipeline.is_alive = mock.MagicMock()  # nosemgrep
        failed_pipeline.is_alive.return_value = False  # nosemgrep
        failed_pipeline.pid = 42
        metric_targets = MetricTargets(None, prometheus_exporter_mock)
        manager = PipelineManager(self.logger, metric_targets)
        manager._pipelines = [failed_pipeline]

        manager.remove_failed_pipeline()
        prometheus_exporter_mock.prometheus_exporter.remove_metrics_from_process.assert_called()
        prometheus_exporter_mock.prometheus_exporter.remove_metrics_from_process.assert_called_with(
            42
        )

    def test_remove_failed_pipelines_skips_removal_of_metrics_database_if_no_metric_target_is_configured(
        self,
    ):
        failed_pipeline = mock.MagicMock()
        failed_pipeline.metric_targets = None
        failed_pipeline.is_alive = mock.MagicMock()  # nosemgrep
        failed_pipeline.is_alive.return_value = False  # nosemgrep
        manager = PipelineManager(self.logger, None)
        manager._pipelines = [failed_pipeline]

        manager.remove_failed_pipeline()
        assert failed_pipeline.metric_targets is None
