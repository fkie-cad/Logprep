# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
from copy import deepcopy
from logging import Logger
from unittest import mock

from logprep.framework.pipeline_manager import PipelineManager
from logprep.metrics.exporter import PrometheusExporter
from logprep.util.configuration import Configuration
from tests.testdata.metadata import path_to_config


@mock.patch("multiprocessing.Process", new=mock.MagicMock())
class TestPipelineManager:
    def setup_class(self):
        self.config = Configuration.from_sources([path_to_config])
        self.logger = Logger("test")

        self.manager = PipelineManager(self.config)

    def teardown_method(self):
        self.manager._pipelines = []

    def test_get_count_returns_count_of_pipelines(self):
        for count in range(5):
            self.manager.set_count(count)

            assert self.manager.get_count() == count

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
        logger_mock.assert_called_with("Restarted 1 failed pipeline(s), with exit code(s): [-1]")

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
            self.config.metrics = {"enabled": True, "port": 1234}
            self.config.process_count = 2
            manager = PipelineManager(self.config)
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
            self.config.process_count = 2
            manager = PipelineManager(config)
            prometheus_exporter_mock = mock.MagicMock()
            manager.prometheus_exporter = prometheus_exporter_mock
            manager.stop()
            prometheus_exporter_mock.cleanup_prometheus_multiprocess_dir.assert_called()

    def test_prometheus_exporter_is_instanciated_if_metrics_enabled(self):
        self.config.metrics["enabled"] = True
        manager = PipelineManager(self.config)
        assert isinstance(manager.prometheus_exporter, PrometheusExporter)
