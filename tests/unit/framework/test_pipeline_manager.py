# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
import multiprocessing
from copy import deepcopy
from logging import Logger
from logging.config import dictConfig
from unittest import mock

from logprep.connector.http.input import HttpInput
from logprep.factory import Factory
from logprep.framework.pipeline_manager import PipelineManager, ThrottlingQueue
from logprep.metrics.exporter import PrometheusExporter
from logprep.util.configuration import Configuration, MetricsConfig
from logprep.util.defaults import DEFAULT_LOG_CONFIG
from logprep.util.logging import logqueue
from tests.testdata.metadata import path_to_config


@mock.patch("multiprocessing.Process", new=mock.MagicMock())
class TestPipelineManager:
    def setup_class(self):
        self.config = Configuration.from_sources([path_to_config])
        self.logger = Logger("test")

        self.manager = PipelineManager(self.config)

    def teardown_method(self):
        self.manager._pipelines = []

    def test_decrease_to_count_removes_required_number_of_pipelines(self):
        self.manager._increase_to_count(3)

        self.manager._decrease_to_count(2)
        assert len(self.manager._pipelines) == 2

        self.manager._decrease_to_count(1)
        assert len(self.manager._pipelines) == 1

    def test_set_count_calls_multiprocessing_process(self):
        self.manager._pipelines = []
        with mock.patch("multiprocessing.Process") as process_mock:
            self.manager.set_count(2)
            process_mock.assert_called()
        assert len(self.manager._pipelines) == 2

    def test_decrease_to_count_does_nothing_if_count_is_equal_or_more_than_current_count(self):
        current_pipelines = list(self.manager._pipelines)

        for count in range(len(current_pipelines) + 1):
            self.manager._decrease_to_count(len(current_pipelines) + count)

            assert self.manager._pipelines == current_pipelines

    def test_decrease_to_count_increases_number_of_pipeline_stops_metric(self):
        self.manager._increase_to_count(2)
        self.manager.metrics.number_of_pipeline_stops = 0
        self.manager._decrease_to_count(0)
        assert self.manager.metrics.number_of_pipeline_stops == 2

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
        failed_pipeline = mock.MagicMock()
        failed_pipeline.is_alive = mock.MagicMock(return_value=False)
        ok_pipeline = mock.MagicMock()
        ok_pipeline.is_alive = mock.MagicMock(return_value=True)
        self.manager._pipelines = [failed_pipeline, ok_pipeline]
        self.manager.restart_failed_pipeline()

        assert not failed_pipeline in self.manager._pipelines

    @mock.patch("logging.Logger.warning")
    def test_remove_failed_pipelines_logs_warning_for_removed_failed_pipelines(self, logger_mock):
        failed_pipeline = mock.MagicMock()
        failed_pipeline.is_alive = mock.MagicMock(return_value=False)
        failed_pipeline.exitcode = -1
        ok_pipeline = mock.MagicMock()
        ok_pipeline.is_alive = mock.MagicMock(return_value=True)
        self.manager._pipelines = [failed_pipeline, ok_pipeline]
        self.manager.restart_failed_pipeline()
        logger_mock.assert_called_with(
            "Restarting failed pipeline on index %s with exit code: %s", 1, -1
        )

    def test_stop_terminates_processes_created(self):
        self.manager.set_count(3)
        logprep_instances = list(self.manager._pipelines)

        self.manager.stop()

        assert len(logprep_instances) == 3

        for logprep_instance in logprep_instances:
            assert logprep_instance.was_started and logprep_instance.was_stopped

    def test_restart_failed_pipelines_calls_prometheus_cleanup_method(self, tmpdir):
        with mock.patch("os.environ", new={"PROMETHEUS_MULTIPROC_DIR": str(tmpdir)}):
            failed_pipeline = mock.MagicMock()
            failed_pipeline.is_alive = mock.MagicMock()
            failed_pipeline.is_alive.return_value = False
            failed_pipeline.pid = 42
            config = deepcopy(self.config)
            config.metrics = {"enabled": True, "port": 1234}
            config.process_count = 2
            manager = PipelineManager(config)
            prometheus_exporter_mock = mock.MagicMock()
            manager.prometheus_exporter = prometheus_exporter_mock
            manager._pipelines = [failed_pipeline]
            manager.restart_failed_pipeline()
            prometheus_exporter_mock.mark_process_dead.assert_called()
            prometheus_exporter_mock.mark_process_dead.assert_called_with(42)

    def test_restart_failed_pipelines_increases_number_of_failed_pipelines_metrics(self):
        failed_pipeline = mock.MagicMock()
        failed_pipeline.is_alive = mock.MagicMock()
        failed_pipeline.is_alive.return_value = False
        self.manager._pipelines = [failed_pipeline]
        self.manager.metrics.number_of_failed_pipelines = 0
        self.manager.restart_failed_pipeline()
        assert self.manager.metrics.number_of_failed_pipelines == 1

    def test_stop_calls_prometheus_cleanup_method(self, tmpdir):
        with mock.patch("os.environ", new={"PROMETHEUS_MULTIPROC_DIR": str(tmpdir)}):
            config = deepcopy(self.config)
            config.metrics = {"enabled": True, "port": 1234}
            config.process_count = 2
            manager = PipelineManager(config)
            prometheus_exporter_mock = mock.MagicMock()
            manager.prometheus_exporter = prometheus_exporter_mock
            manager.stop()
            prometheus_exporter_mock.cleanup_prometheus_multiprocess_dir.assert_called()

    def test_prometheus_exporter_is_instanciated_if_metrics_enabled(self):
        config = deepcopy(self.config)
        config.metrics = MetricsConfig(enabled=True, port=8000)
        with mock.patch("logprep.metrics.exporter.PrometheusExporter.prepare_multiprocessing"):
            manager = PipelineManager(config)
        assert isinstance(manager.prometheus_exporter, PrometheusExporter)

    def test_set_count_increases_number_of_pipeline_starts_metric(self):
        self.manager.metrics.number_of_pipeline_starts = 0
        self.manager.set_count(2)
        assert self.manager.metrics.number_of_pipeline_starts == 2

    def test_set_count_increases_number_of_pipeline_stops_metric(self):
        self.manager.metrics.number_of_pipeline_stops = 0
        self.manager.set_count(2)
        self.manager.set_count(0)
        assert self.manager.metrics.number_of_pipeline_stops == 2

    def test_restart_calls_set_count(self):
        with mock.patch.object(self.manager, "set_count") as mock_set_count:
            self.manager.restart()
            mock_set_count.assert_called()
            assert mock_set_count.call_count == 2

    def test_restart_sets_deterministic_pipeline_index(self):
        config = deepcopy(self.config)
        config.metrics = MetricsConfig(enabled=False, port=666)
        pipeline_manager = PipelineManager(config)
        pipeline_manager.set_count(3)
        expected_calls = [mock.call(1), mock.call(2), mock.call(3)]
        with mock.patch.object(pipeline_manager, "_create_pipeline") as mock_create_pipeline:
            pipeline_manager.restart()
            mock_create_pipeline.assert_has_calls(expected_calls)

    def test_restart_failed_pipelines_sets_old_pipeline_index(self):
        pipeline_manager = PipelineManager(self.config)
        pipeline_manager.set_count(3)
        pipeline_manager._pipelines[0] = mock.MagicMock()
        pipeline_manager._pipelines[0].is_alive.return_value = False
        with mock.patch.object(pipeline_manager, "_create_pipeline") as mock_create_pipeline:
            pipeline_manager.restart_failed_pipeline()
            mock_create_pipeline.assert_called_once_with(1)

    def test_pipeline_manager_sets_queue_size_for_http_input(self):
        config = deepcopy(self.config)
        config.input = {
            "http": {
                "type": "http_input",
                "message_backlog_size": 100,
                "collect_meta": False,
                "uvicorn_config": {"port": 9000, "host": "127.0.0.1"},
                "endpoints": {
                    "/json": "json",
                },
            }
        }
        PipelineManager(config).start()
        assert HttpInput.messages._maxsize == 100
        http_input = Factory.create(config.input)
        assert http_input.messages._maxsize == 100

    def test_pipeline_manager_setups_logging(self):
        dictConfig(DEFAULT_LOG_CONFIG)
        manager = PipelineManager(self.config)
        manager.start()
        assert manager.loghandler is not None
        assert manager.loghandler.queue == logqueue
        assert manager.loghandler._thread is None
        assert manager.loghandler._process.is_alive()
        assert manager.loghandler._process.daemon

    def test_restart_failed_pipeline_increases_restart_count_if_pipeline_fails(self):
        pipeline_manager = PipelineManager(self.config)
        pipeline_manager._pipelines = [mock.MagicMock()]
        pipeline_manager._pipelines[0].is_alive.return_value = False
        assert pipeline_manager.restart_count == 0
        pipeline_manager.restart_failed_pipeline()
        assert pipeline_manager.restart_count == 1

    def test_restart_failed_pipeline_resets_restart_count_if_pipeline_recovers(self):
        pipeline_manager = PipelineManager(self.config)
        pipeline_manager._pipelines = [mock.MagicMock()]
        assert pipeline_manager.restart_count == 0
        pipeline_manager._pipelines[0].is_alive.return_value = False
        pipeline_manager.restart_failed_pipeline()
        assert pipeline_manager.restart_count == 1
        pipeline_manager._pipelines[0].is_alive.return_value = False
        pipeline_manager.restart_failed_pipeline()
        assert pipeline_manager.restart_count == 2
        pipeline_manager._pipelines[0].is_alive.return_value = True
        pipeline_manager.restart_failed_pipeline()
        assert pipeline_manager.restart_count == 0

    @mock.patch("time.sleep")
    def test_restart_failed_pipeline_restarts_immediately_on_negative_restart_count_parameter(
        self, mock_time_sleep
    ):
        config = deepcopy(self.config)
        config.restart_count = -1
        pipeline_manager = PipelineManager(config)
        pipeline_manager._pipelines = [mock.MagicMock()]
        pipeline_manager._pipelines[0].is_alive.return_value = False
        pipeline_manager.restart_failed_pipeline()
        mock_time_sleep.assert_not_called()

    def test_restart_injects_healthcheck_functions(self):
        pipeline_manager = PipelineManager(self.config)
        pipeline_manager.prometheus_exporter = mock.MagicMock()
        pipeline_manager._pipelines = [mock.MagicMock()]
        pipeline_manager.restart()
        pipeline_manager.prometheus_exporter.update_healthchecks.assert_called()

    def test_reload_calls_set_count_twice(self):
        with mock.patch.object(self.manager, "set_count") as mock_set_count:
            self.manager.reload()
            # drains pipelines down to 0 and scales up to 3 afterwards
            mock_set_count.assert_has_calls([mock.call(0), mock.call(3)])

    def test_should_exit_returns_bool_based_on_restart_count(self):
        self.config.restart_count = 2
        manager = PipelineManager(self.config)
        assert not manager.should_exit()
        manager.restart_count = 1
        assert not manager.should_exit()
        manager.restart_count = 2
        assert manager.should_exit()

    def test_stop_calls_stop_on_loghandler(self):
        manager = PipelineManager(self.config)
        manager.loghandler = mock.MagicMock()
        manager.stop()
        manager.loghandler.stop.assert_called()


class TestThrottlingQueue:

    def test_throttling_queue_is_multiprocessing_queue(self):
        queue = ThrottlingQueue(multiprocessing.get_context(), 100)
        assert isinstance(queue, ThrottlingQueue)
        assert isinstance(queue, multiprocessing.queues.Queue)

    def test_throttling_put_calls_parent(self):
        queue = ThrottlingQueue(multiprocessing.get_context(), 100)
        with mock.patch.object(multiprocessing.queues.Queue, "put") as mock_put:
            queue.put("test")
            mock_put.assert_called_with("test", block=True, timeout=None)

    def test_throttling_put_throttles(self):
        queue = ThrottlingQueue(multiprocessing.get_context(), 100)
        with mock.patch.object(queue, "throttle") as mock_throttle:
            queue.put("test")
            mock_throttle.assert_called()

    def test_throttle_sleeps(self):
        with mock.patch("time.sleep") as mock_sleep:
            queue = ThrottlingQueue(multiprocessing.get_context(), 100)
            with mock.patch.object(queue, "qsize", return_value=95):
                queue.throttle()
            mock_sleep.assert_called()

    def test_throttle_sleep_time_increases_with_qsize(self):
        with mock.patch("time.sleep") as mock_sleep:
            queue = ThrottlingQueue(multiprocessing.get_context(), 100)
            with mock.patch.object(queue, "qsize", return_value=91):
                queue.throttle()
            first_sleep_time = mock_sleep.call_args[0][0]
            mock_sleep.reset_mock()
            with mock.patch.object(queue, "qsize", return_value=95):
                queue.throttle()
            assert mock_sleep.call_args[0][0] > first_sleep_time
