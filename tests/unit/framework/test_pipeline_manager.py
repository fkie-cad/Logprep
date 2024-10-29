# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
# pylint: disable=unnecessary-lambda-assignment
import multiprocessing
import time
from copy import deepcopy
from logging import Logger
from logging.config import dictConfig
from unittest import mock

import pytest

from logprep.connector.http.input import HttpInput
from logprep.factory import Factory
from logprep.framework.pipeline_manager import (
    OutputQueueListener,
    PipelineManager,
    ThrottlingQueue,
)
from logprep.metrics.exporter import PrometheusExporter
from logprep.util.configuration import Configuration, MetricsConfig
from logprep.util.defaults import DEFAULT_LOG_CONFIG, EXITCODES
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

    def test_prometheus_exporter_is_instantiated_if_metrics_enabled(self):
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

    def test_restart_failed_pipeline_adds_error_output_health_check_to_metrics_exporter(
        self, tmp_path
    ):
        with mock.patch("logprep.framework.pipeline_manager.OutputQueueListener"):
            with mock.patch("logprep.framework.pipeline_manager.ThrottlingQueue"):
                config = deepcopy(self.config)
                config.error_output = {"dummy": {"type": "dummy_output"}}
                pipeline_manager = PipelineManager(config)
                mock_export = mock.MagicMock()
                pipeline_manager.prometheus_exporter = mock_export
                pipeline_manager.restart()
                mock_export.update_healthchecks.assert_called()

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

    def test_setup_error_queue_sets_error_queue_and_starts_listener(self):
        self.config.error_output = {"dummy": {"type": "dummy_output"}}
        with mock.patch("logprep.framework.pipeline_manager.OutputQueueListener"):
            with mock.patch("logprep.framework.pipeline_manager.ThrottlingQueue") as mock_queue:
                mock_queue.get.return_value = "not null"
                manager = PipelineManager(self.config)
        assert manager.error_queue is not None
        assert manager._error_listener is not None
        manager._error_listener.start.assert_called()  # pylint: disable=no-member

    def test_setup_does_not_sets_error_queue_if_no_error_output(self):
        self.config.error_output = {}
        manager = PipelineManager(self.config)
        assert manager.error_queue is None
        assert manager._error_listener is None

    def test_setup_error_queue_raises_system_exit_if_error_listener_fails(self):
        self.config.error_output = {"dummy": {"type": "dummy_output"}}
        with mock.patch("logprep.framework.pipeline_manager.OutputQueueListener") as mock_listener:
            mock_queue_listener = mock.MagicMock()
            mock_queue_listener.sentinel = None
            mock_listener.return_value = mock_queue_listener
            with mock.patch("logprep.framework.pipeline_manager.ThrottlingQueue.get") as mock_get:
                mock_get.return_value = None
                with pytest.raises(
                    SystemExit, match=str(EXITCODES.ERROR_OUTPUT_NOT_REACHABLE.value)
                ):
                    PipelineManager(self.config)

    def test_stop_calls_stop_on_error_listener(self):
        self.config.error_output = {"dummy": {"type": "dummy_output"}}
        with mock.patch("logprep.framework.pipeline_manager.OutputQueueListener"):
            with mock.patch("logprep.framework.pipeline_manager.ThrottlingQueue.get") as mock_get:
                mock_get.return_value = "not None"
                manager = PipelineManager(self.config)
                manager.stop()
        manager._error_listener.stop.assert_called()  # pylint: disable=no-member

    def test_restart_with_error_output_calls_pipeline_with_error_queue(self):
        self.config.error_output = {"dummy": {"type": "dummy_output"}}
        with mock.patch("multiprocessing.Process"):
            with mock.patch("logprep.framework.pipeline_manager.Pipeline") as mock_pipeline:
                with mock.patch("logprep.framework.pipeline_manager.OutputQueueListener"):
                    with mock.patch(
                        "logprep.framework.pipeline_manager.ThrottlingQueue.get"
                    ) as mock_get:
                        mock_get.return_value = "not None"
                        manager = PipelineManager(self.config)
                        manager.restart()
        mock_pipeline.assert_called()
        mock_pipeline.assert_called_with(
            pipeline_index=3,  # last call index
            config=manager._configuration,
            error_queue=manager.error_queue,
        )

    def test_restart_without_error_output_calls_pipeline_with_error_queue(self):
        self.config.error_output = {}
        with mock.patch("multiprocessing.Process"):
            with mock.patch("logprep.framework.pipeline_manager.Pipeline") as mock_pipeline:
                with mock.patch("logprep.framework.pipeline_manager.OutputQueueListener"):
                    with mock.patch(
                        "logprep.framework.pipeline_manager.ThrottlingQueue.get"
                    ) as mock_get:
                        mock_get.return_value = "not None"
                        manager = PipelineManager(self.config)
                        manager.restart()
        mock_pipeline.assert_called()
        mock_pipeline.assert_called_with(
            pipeline_index=3,  # last call index
            config=manager._configuration,
            error_queue=None,
        )


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


class TestOutputQueueListener:

    @pytest.mark.parametrize(
        "parameters, error",
        [
            (
                {
                    "config": {"random_name": {"type": "dummy_output"}},
                    "queue": ThrottlingQueue(multiprocessing.get_context(), 100),
                    "target": "random",
                },
                None,
            ),
            (
                {
                    "config": {"random_name": {"type": "dummy_output"}},
                    "queue": ThrottlingQueue(multiprocessing.get_context(), 100),
                    "target": lambda x: x,
                },
                TypeError,
            ),
            (
                {
                    "config": {"random_name": {"type": "dummy_output"}},
                    "queue": "I am not a queue",
                    "target": "random",
                },
                TypeError,
            ),
            (
                {
                    "config": "I am not a config",
                    "queue": ThrottlingQueue(multiprocessing.get_context(), 100),
                    "target": "random",
                },
                TypeError,
            ),
        ],
    )
    def test_sets_parameters(self, parameters, error):
        if error:
            with pytest.raises(error):
                OutputQueueListener(**parameters)
        else:
            OutputQueueListener(**parameters)

    def test_init_sets_process_but_does_not_start_it(self):
        target = "store"
        queue = ThrottlingQueue(multiprocessing.get_context(), 100)
        output_config = {"random_name": {"type": "dummy_output"}}
        listener = OutputQueueListener(queue, target, output_config)
        assert listener._process is not None
        assert isinstance(listener._process, multiprocessing.Process)
        assert not listener._process.is_alive()

    def test_init_sets_process_target(self):
        target = "store"
        output_config = {"random_name": {"type": "dummy_output"}}
        queue = ThrottlingQueue(multiprocessing.get_context(), 100)
        with mock.patch("multiprocessing.Process") as mock_process:
            listener = OutputQueueListener(queue, target, output_config)
        mock_process.assert_called_with(target=listener._listen, daemon=True)

    def test_start_starts_process(self):
        target = "store"
        output_config = {"random_name": {"type": "dummy_output"}}
        queue = ThrottlingQueue(multiprocessing.get_context(), 100)
        listener = OutputQueueListener(queue, target, output_config)
        with mock.patch.object(listener._process, "start") as mock_start:
            listener.start()
        mock_start.assert_called()

    @mock.patch(
        "logprep.framework.pipeline_manager.OutputQueueListener.get_output_instance",
        new=mock.MagicMock(),
    )
    def test_sentinel_breaks_while_loop(self):
        target = "store"
        output_config = {"random_name": {"type": "dummy_output"}}
        queue = ThrottlingQueue(multiprocessing.get_context(), 100)
        listener = OutputQueueListener(queue, target, output_config)
        listener.queue.put(listener.sentinel)
        with mock.patch("logging.Logger.debug") as mock_debug:
            listener._listen()
        mock_debug.assert_called_with("Got sentinel. Stopping listener.")

    def test_stop_injects_sentinel(self):
        target = "store"
        output_config = {"random_name": {"type": "dummy_output"}}
        with mock.patch("multiprocessing.Process"):
            queue = ThrottlingQueue(multiprocessing.get_context(), 100)
            listener = OutputQueueListener(queue, target, output_config)
            with mock.patch.object(queue, "put") as mock_put:
                listener.stop()
            mock_put.assert_called_with(listener.sentinel)

    def test_stop_joins_process(self):
        target = "store"
        output_config = {"random_name": {"type": "dummy_output"}}
        with mock.patch("multiprocessing.Process"):
            queue = ThrottlingQueue(multiprocessing.get_context(), 100)
            listener = OutputQueueListener(queue, target, output_config)
            listener.stop()
            listener._process.join.assert_called()

    def test_listen_calls_target(self):
        target = "store"
        output_config = {"random_name": {"type": "dummy_output"}}
        queue = ThrottlingQueue(multiprocessing.get_context(), 100)
        queue.empty = mock.MagicMock(return_value=True)
        with mock.patch("logprep.connector.dummy.output.DummyOutput.store") as mock_store:
            listener = OutputQueueListener(queue, target, output_config)
            listener.queue.put("test")
            listener.queue.put(listener.sentinel)
            listener._listen()
        mock_store.assert_called_with("test")

    def test_listen_creates_component(self):
        target = "store"
        output_config = {"random_name": {"type": "dummy_output"}}
        queue = ThrottlingQueue(multiprocessing.get_context(), 100)
        queue.empty = mock.MagicMock(return_value=True)
        listener = OutputQueueListener(queue, target, output_config)
        with mock.patch("logprep.factory.Factory.create") as mock_create:
            listener.queue.put("test")
            listener.queue.put(listener.sentinel)
            listener._listen()
        mock_create.assert_called_with(output_config)

    def test_listen_setups_component(self):
        target = "store"
        output_config = {"random_name": {"type": "dummy_output"}}
        queue = ThrottlingQueue(multiprocessing.get_context(), 100)
        queue.empty = mock.MagicMock(return_value=True)
        listener = OutputQueueListener(queue, target, output_config)
        with mock.patch("logprep.connector.dummy.output.DummyOutput.setup") as mock_setup:
            listener.queue.put("test")
            listener.queue.put(listener.sentinel)
            listener._listen()
        mock_setup.assert_called()

    def test_get_component_instance_raises_if_setup_not_successful(self):
        target = "store"
        output_config = {"random_name": {"type": "dummy_output"}}
        queue = ThrottlingQueue(multiprocessing.get_context(), 100)
        listener = OutputQueueListener(queue, target, output_config)
        with mock.patch("logprep.connector.dummy.output.DummyOutput.setup") as mock_setup:
            mock_setup.side_effect = SystemExit(4)
            with pytest.raises(SystemExit, match="4"):
                listener._listen()

    def test_listen_calls_component_shutdown_by_injecting_sentinel(self):
        target = "store"
        output_config = {"random_name": {"type": "dummy_output"}}
        queue = ThrottlingQueue(multiprocessing.get_context(), 100)
        queue.empty = mock.MagicMock(return_value=True)
        listener = OutputQueueListener(queue, target, output_config)
        with mock.patch("logprep.connector.dummy.output.DummyOutput.shut_down") as mock_shutdown:
            listener.queue.put("test")
            listener.queue.put(listener.sentinel)
            listener._listen()
        mock_shutdown.assert_called()

    @mock.patch(
        "logprep.framework.pipeline_manager.OutputQueueListener.get_output_instance",
        new=mock.MagicMock(),
    )
    def test_listen_drains_queue_on_shutdown(self):
        target = "store"
        output_config = {"random_name": {"type": "dummy_output"}}
        queue = multiprocessing.Queue()
        listener = OutputQueueListener(queue, target, output_config)
        listener.queue.put(listener.sentinel)
        listener.queue.put("test")
        listener._listen()
        assert listener.queue.qsize() == 0

    @mock.patch(
        "logprep.framework.pipeline_manager.OutputQueueListener.get_output_instance",
        new=mock.MagicMock(),
    )
    def test_listen_ensures_error_queue_is_closed_after_drained(self):
        target = "store"
        output_config = {"random_name": {"type": "dummy_output"}}
        queue = ThrottlingQueue(multiprocessing.get_context(), 100)
        listener = OutputQueueListener(queue, target, output_config)
        listener.queue.put(listener.sentinel)
        listener._listen()
        with pytest.raises(ValueError, match="is closed"):
            listener.queue.put("test")

    @mock.patch(
        "logprep.framework.pipeline_manager.OutputQueueListener.get_output_instance",
    )
    def test_listen_ignores_sync_item_1_and_sentinel(self, mock_get_output_instance):
        mock_component = mock.MagicMock()
        mock_target = mock.MagicMock()
        mock_component.store = mock_target
        mock_get_output_instance.return_value = mock_component
        target = "store"
        output_config = {"random_name": {"type": "dummy_output"}}
        queue = ThrottlingQueue(multiprocessing.get_context(), 100)
        listener = OutputQueueListener(queue, target, output_config)
        listener.queue.put(1)
        listener.queue.put(listener.sentinel)
        listener._listen()
        mock_target.assert_not_called()

    @mock.patch(
        "logprep.framework.pipeline_manager.OutputQueueListener.get_output_instance",
    )
    @mock.patch("logging.Logger.error")
    def test_listen_logs_event_on_unexpected_exception(self, mock_error, mock_get_output_instance):
        mock_component = mock.MagicMock()
        mock_target = mock.MagicMock()
        mock_target.side_effect = Exception("TestException")
        mock_component.store = mock_target
        mock_get_output_instance.return_value = mock_component
        target = "store"
        output_config = {"random_name": {"type": "dummy_output"}}
        queue = ThrottlingQueue(multiprocessing.get_context(), 100)
        listener = OutputQueueListener(queue, target, output_config)
        event = {"event": "test"}
        listener.queue.put(event)
        listener.queue.put(listener.sentinel)
        time.sleep(0.1)  # test will sometimes fail without it, probably due to ThrottlingQueue
        listener._listen()
        expected_error_log = (
            f"[Error Event] Couldn't enqueue error item due to: TestException | Item: '{event}'"
        )
        mock_error.assert_called_with(expected_error_log)

    @mock.patch(
        "logprep.framework.pipeline_manager.OutputQueueListener.get_output_instance",
        new=mock.MagicMock(),
    )
    def test_drain_queue_ignores_sync_item_1_and_sentinel(self):
        target = "store"
        output_config = {"random_name": {"type": "dummy_output"}}
        queue = ThrottlingQueue(multiprocessing.get_context(), 100)
        listener = OutputQueueListener(queue, target, output_config)
        listener.queue.put(1)
        listener.queue.put(listener.sentinel)
        mock_target = mock.MagicMock()
        listener._drain_queue(mock_target)
        mock_target.assert_not_called()

    @mock.patch(
        "logprep.framework.pipeline_manager.OutputQueueListener.get_output_instance",
        new=mock.MagicMock(),
    )
    @mock.patch("logging.Logger.error")
    def test_drain_queue_logs_event_on_unexpected_exception(self, mock_error):
        target = "store"
        output_config = {"random_name": {"type": "dummy_output"}}
        queue = ThrottlingQueue(multiprocessing.get_context(), 100)
        listener = OutputQueueListener(queue, target, output_config)
        event = {"event": "test"}
        listener.queue.put(event)
        mock_target = mock.MagicMock()
        mock_target.side_effect = Exception("TestException")
        time.sleep(0.1)  # test will sometimes fail without it, probably due to ThrottlingQueue
        listener._drain_queue(mock_target)
        expected_error_log = (
            f"[Error Event] Couldn't enqueue error item due to: TestException | Item: '{event}'"
        )
        mock_error.assert_called_with(expected_error_log)
