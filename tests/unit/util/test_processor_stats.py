# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=no-self-use
# pylint: disable=attribute-defined-outside-init
import logging
from multiprocessing import Lock
from unittest import mock

import numpy as np
from prometheus_client import REGISTRY

from logprep.processor.dropper.processor import Dropper
from logprep.util.processor_stats import ProcessorStats, StatsClassesController, StatusTracker
from logprep.util.prometheus_exporter import PrometheusStatsExporter


def validify_mean_proc_time_calculation(processor_stats, time_samples):
    for i, time_sample in enumerate(time_samples):
        processor_stats.update_average_processing_time(time_sample)

        real_mean = np.mean(time_samples[: i + 1])
        if real_mean != processor_stats.aggr_data.get("avg_processing_time"):
            return False
    return True


class TestProcessorStats:
    def setup_method(self):
        StatsClassesController.ENABLED = True

    def test_correct_calculation_of_avg_processing_time(self):
        processor_stats = ProcessorStats()

        time_samples = [4, 21, 5, 48, 12, 1, 3, 54, 3, 3]
        assert validify_mean_proc_time_calculation(processor_stats, time_samples)

    def test_correct_calculation_of_avg_processing_time_with_reset_in_between(self):
        processor_stats = ProcessorStats()

        first_time_samples = [4, 21, 5, 48, 12, 1, 3, 54, 3, 3]
        assert validify_mean_proc_time_calculation(processor_stats, first_time_samples)

        processor_stats.reset_statistics()

        second_time_samples = [5, 7, 15, 3, 18]
        assert validify_mean_proc_time_calculation(processor_stats, second_time_samples)

    def test_reset_statistics_sets_everything_to_zero(self):
        processor_stats = ProcessorStats()

        processor_stats.aggr_data = {
            "processed": 142,
            "matches": 13,
            "errors": 37,
            "warnings": 2,
            "avg_processing_time": 18.9,
        }
        processor_stats._max_time = 200
        processor_stats._processing_time_sample_counter = 20

        processor_stats.reset_statistics()

        assert all(processor_stats.aggr_data[key] == 0 for key in processor_stats.aggr_data)

        assert processor_stats._max_time == -1
        assert processor_stats._processing_time_sample_counter == 0

    def test_increment_processed_count_by_one(self):
        processor_stats = ProcessorStats()
        assert processor_stats.processed_count == 0
        processor_stats.increment_processed_count()
        assert processor_stats.processed_count == 1

    def test_increment_processed_count_by_n(self):
        processor_stats = ProcessorStats()
        assert processor_stats.processed_count == 0
        number = 20
        processor_stats.increment_processed_count(number)
        processor_stats.increment_processed_count(number)
        assert processor_stats.processed_count == 2 * number

    def test_update_processed_count_sets_number_in_processed_count(self):
        processor_stats = ProcessorStats()
        assert processor_stats.processed_count == 0
        number = 42
        processor_stats.update_processed_count(number)
        assert processor_stats.processed_count == number
        number = 13
        processor_stats.update_processed_count(number)
        assert processor_stats.processed_count == number


class TestStatusTracker:
    def setup_method(self):
        REGISTRY.__init__()
        StatsClassesController.ENABLED = True
        logger = logging.getLogger("test-logger")
        stats_logger_config = {
            "period": 10,
            "enabled": True,
            "cumulative": True,
            "targets": [
                {"prometheus": {"port": 8000}},
                {
                    "file": {
                        "path": "./logs/status.json",
                        "rollover_interval": 86400,
                        "backup_count": 10,
                    }
                },
            ],
        }
        self.status_tracker = StatusTracker(
            shared_dict={},
            status_logger_config=stats_logger_config,
            status_logger=[
                logging.getLogger("test-file-metric-logger"),
                PrometheusStatsExporter(stats_logger_config, logger),
            ],
            lock=Lock(),
        )
        first_dropper = Dropper("Dropper1", "tests/testdata/unit/tree_config.json", logger)
        second_dropper = Dropper("Dropper2", "tests/testdata/unit/tree_config.json", logger)
        first_dropper.ps.num_rules = 12
        second_dropper.ps.num_rules = 9

        self.status_tracker.set_pipeline([first_dropper, second_dropper])

    def test_unpack_status_logger_sets_correct_attributes(self):
        assert isinstance(self.status_tracker._file_logger, logging.Logger)
        assert isinstance(self.status_tracker._prometheus_logger, PrometheusStatsExporter)

    def test_reset_statistics_sets_everything_to_zero(self):
        self.status_tracker.aggr_data = {
            "errors": 12,
            "warnings": 13,
            "processed": 37,
            "error_types": {"A": 2, "B": 2},
            "warning_types": {"A": 2, "B": 2},
        }
        self.status_tracker._pipeline[0].ps.aggr_data = {
            "processed": 142,
            "matches": 13,
            "errors": 37,
            "warnings": 2,
            "avg_processing_time": 18.9,
        }
        self.status_tracker._pipeline[1].ps.aggr_data = {
            "processed": 142,
            "matches": 13,
            "errors": 37,
            "warnings": 2,
            "avg_processing_time": 18.9,
        }
        self.status_tracker._reset_statistics()

        assert all(
            self.status_tracker.aggr_data[key] == 0 for key in ["errors", "warnings", "processed"]
        )
        assert all(
            not self.status_tracker.aggr_data[key] for key in ["error_types", "warning_types"]
        )

        for processor in self.status_tracker._pipeline:
            assert all(
                processor.ps.aggr_data[key] == 0
                for key in processor.ps.aggr_data
                if not key.endswith("idx")
            )
            assert len(processor.ps.aggr_data["matches_per_idx"]) == processor.ps.num_rules
            assert np.sum(processor.ps.aggr_data["matches_per_idx"]) == 0
            assert len(processor.ps.aggr_data["times_per_idx"]) == processor.ps.num_rules
            assert np.sum(processor.ps.aggr_data["times_per_idx"]) == 0

    @mock.patch("prometheus_client.Gauge.labels")
    def test_log_to_prometheus_exports_calls_gauge_labels(self, mock_labels):
        metrics = {
            "MultiprocessingPipeline-1": {"kafka_offset": 1, "processed": 123},
            "MultiprocessingPipeline-2": {"kafka_offset": 3, "processed": 50},
            "errors": 12,
            "warnings": 13,
            "processed": 37,
            "error_types": {"A": 2, "B": 2},
            "warning_types": {"A": 2, "B": 2},
            "Dropper1": {
                "processed": 10,
                "matches": 11,
                "errors": 12,
                "warnings": 13,
                "mean_matches_per_rule": 1,
                "avg_processing_time": 1,
            },
            "Dropper2": {
                "processed": 20,
                "matches": 21,
                "errors": 22,
                "warnings": 23,
                "mean_matches_per_rule": 2,
                "avg_processing_time": 2,
            },
            "timestamp": "2022-01-01T01:01:01.000001",
        }

        self.status_tracker._log_to_prometheus(ordered_data=metrics)
        mock_labels.assert_has_calls([mock.call(of="pipeline"), mock.call().set(12)])
        mock_labels.assert_has_calls([mock.call(of="pipeline"), mock.call().set(13)])
        mock_labels.assert_has_calls([mock.call(of="pipeline"), mock.call().set(37)])
        mock_labels.assert_has_calls([mock.call(of="Dropper1"), mock.call().set(10)])
        mock_labels.assert_has_calls([mock.call(of="Dropper1"), mock.call().set(11)])
        mock_labels.assert_has_calls([mock.call(of="Dropper1"), mock.call().set(12)])
        mock_labels.assert_has_calls([mock.call(of="Dropper1"), mock.call().set(13)])
        mock_labels.assert_has_calls([mock.call(of="Dropper2"), mock.call().set(20)])
        mock_labels.assert_has_calls([mock.call(of="Dropper2"), mock.call().set(21)])
        mock_labels.assert_has_calls([mock.call(of="Dropper2"), mock.call().set(22)])
        mock_labels.assert_has_calls([mock.call(of="Dropper2"), mock.call().set(23)])
