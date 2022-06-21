"""This module contains functionality to log the status of logprep."""
import json
from collections import OrderedDict, namedtuple
from copy import deepcopy
from ctypes import c_double
from datetime import datetime
from multiprocessing import Lock, Value, current_process
from time import time

import numpy as np

from typing import List, Union, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from logprep.abc import Processor
    from logprep.processor.base.rule import Rule

np.set_printoptions(suppress=True)


class StatsClassesController:
    """Used to control if methods of classes for status tracking are enabled or not."""

    ENABLED = False

    @staticmethod
    def decorate_all_methods(decorator):
        """Decorate all methods of a class with another decorator."""

        def decorate(cls):
            for attribute in cls.__dict__:
                if callable(getattr(cls, attribute)):
                    setattr(cls, attribute, decorator(getattr(cls, attribute)))
            return cls

        return decorate

    @staticmethod
    def is_enabled(func):
        """Disable a method if status tracking is disabled."""

        def inner(*args, **kwargs):
            if StatsClassesController.ENABLED:
                return func(*args, **kwargs)
            return None

        return inner


@StatsClassesController.decorate_all_methods(StatsClassesController.is_enabled)  # nosemgrep
class ProcessorStats:
    """Used to track processor stats."""

    metrics = [
        "processed",
        "matches",
        "errors",
        "warnings",
        "avg_processing_time",
    ]

    def __init__(self):
        self.aggr_data = None
        self._max_time = None
        self.num_rules = 0
        self._processing_time_sample_counter = None
        self.reset_statistics()

    def reset_statistics(self):
        """Resets all the processor statistics to the initial zero values."""
        self.aggr_data = {metric: 0 for metric in self.metrics}
        self._max_time = -1
        self._processing_time_sample_counter = 0

    def setup_rules(self, rules: List["Rule"]):
        """Setup aggregation data for rules."""
        self.num_rules = len(rules)
        self.aggr_data["matches_per_idx"] = np.zeros(self.num_rules, dtype=int)
        self.aggr_data["times_per_idx"] = np.zeros(self.num_rules, dtype=float)

    def update_per_rule(self, idx: int, processing_time: float):
        """Update matches and times per rule in aggregation data."""
        self.aggr_data["matches"] += 1
        self.aggr_data["matches_per_idx"][idx] += 1
        self.aggr_data["times_per_idx"][idx] += processing_time

    @property
    def processed_count(self):
        """Return the current count of processed events"""
        return self.aggr_data["processed"]

    def increment_processed_count(self, number: int = 1):
        """Increments the processed count statistic."""
        self.aggr_data["processed"] += number

    def update_processed_count(self, processed_count: int):
        """Increment processed count in aggregation data."""
        self.aggr_data["processed"] = processed_count

    def update_average_processing_time(self, next_time_sample):
        """
        Calculate the new average by taking the current average, multiplying it by the number of
        currently observed samples. Then incrementing this by the new sample value and dividing it
        back to the average with the incremented sample counter.
        """
        current_average = self.aggr_data["avg_processing_time"]
        average_multiple = current_average * self._processing_time_sample_counter
        extended_average_multiple = average_multiple + next_time_sample
        self._processing_time_sample_counter += 1
        new_average = extended_average_multiple / self._processing_time_sample_counter
        self.aggr_data["avg_processing_time"] = new_average

    def increment_aggregation(self, key: str):
        """Increment value in aggregation data."""
        if key not in self.aggr_data:
            self.aggr_data[key] = 1
        else:
            self.aggr_data[key] += 1

    def increment_nested(self, key: str, nested_key: str):
        """Increment nested value in aggregation data."""
        if key not in self.aggr_data:
            self.aggr_data[key] = {}
        if nested_key not in self.aggr_data[key].keys():
            self.aggr_data[key][nested_key] = 1
        else:
            self.aggr_data[key][nested_key] += 1

    def increment_nested_existing(self, key: str, nested_key: str):
        """Increment nested value in aggregation data if containing dict already exists."""
        self.aggr_data[key][nested_key] += 1

    def get(self, key: str, value: str) -> Union[int, str]:
        """Get value in aggregation data."""
        return self.aggr_data.get(key, value)

    def get_nested(self, key: str, nested_key: str, value: Union[int, str]) -> Union[int, str]:
        """Get nested value in aggregation data."""
        if key not in self.aggr_data:
            return value
        return self.aggr_data[key].get(nested_key, value)

    def get_nested_existing(self, key: str, nested_key: str):
        """Get nested value in aggregation data if dict for parent key already exists."""
        return self.aggr_data[key][nested_key]

    def set_nested(self, key: str, nested_key: str, value):
        """Set nested value in aggregation data and create containing dict if it does not exist."""
        if key not in self.aggr_data:
            self.aggr_data[key] = {}
        self.aggr_data[key][nested_key] = value

    def set_nested_existing(self, key: str, nested_key: str, value):
        """Set nested value in aggregation data if dict for parent key already exists."""
        self.aggr_data[key][nested_key] = value

    def init_non_rule_processor(self):
        """Prepare aggregation data for processors without rules."""
        del self.aggr_data["matches"]


StatusLoggerCollection = namedtuple("StatusLogger", "file_logger prometheus_exporter")


@StatsClassesController.decorate_all_methods(StatsClassesController.is_enabled)  # nosemgrep
class StatusTracker:
    """Used to track logprep stats."""

    _instance = None
    rule_based_stats_exclusion = ["clusterer", "selective_extractor"]
    pipeline_metrics = ["processed", "errors", "warnings"]

    def __init__(
        self,
        shared_dict: dict,
        status_logger_config: dict,
        status_logger: StatusLoggerCollection,
        lock: Lock,
    ):
        """
        Initiates a status tracker object that can aggregate metrics from the different pipeline
        processes and export them to a rolling file or a prometheus.

        Parameters
        ----------
        shared_dict : dict
            A common data structure shared between the multiprocessing processes. It contains the
            metrics for each pipeline.
        status_logger_config : dict
            The status tracker configuration defining for example the aggregation period or the
            export targets.
        status_logger : List
            This list contains the configured logger. Can contain an actual python Logger or an
            PrometheusStatsExporter.
        lock : Lock
            A multiprocessing lock that prevents concurrent access to the shared dict.
        """
        self._file_logger = None
        self._prometheus_logger = None

        if status_logger is not None:
            self._file_logger = status_logger.file_logger
            self._prometheus_logger = status_logger.prometheus_exporter

        self._shared_dict = shared_dict

        self._config = status_logger_config

        self._print_period = self._config.get("period", 180)
        self._cumulative = self._config.get("cumulative", True)
        self._aggregate_processes = self._config.get("aggregate_processes", True)

        self._pipeline = []

        self.aggr_data = {
            "errors": 0,
            "warnings": 0,
            "processed": 0,
            "error_types": {},
            "warning_types": {},
        }
        self._lock = lock
        self._timer = Value(c_double, time() + self._print_period)

        self.kafka_offset = -1

    def _reset_statistics(self):
        """Resets the status tracker statistics as well as the statistics of each processor."""
        self.aggr_data = {
            "errors": 0,
            "warnings": 0,
            "processed": 0,
            "error_types": {},
            "warning_types": {},
        }
        for processor in self._pipeline:
            processor.ps.reset_statistics()
            processor.ps.setup_rules([None] * processor.ps.num_rules)

    # pylint: disable=C0111
    @property
    def time_to_print(self) -> bool:
        """Check if status should be printed."""
        with self._lock:
            # Check if the time for new periodic data stats has passed.
            if time() < self._timer.value:
                return False
            self._timer.value = time() + self._print_period
            return True

    # pylint: enable=C0111

    def set_pipeline(self, pipeline):
        """Set pipeline."""
        self._pipeline = pipeline

    def add_warnings(self, error: BaseException, processor: "Processor"):
        """Add warnings to aggregated data."""
        self.aggr_data["warnings"] += 1
        processor.ps.aggr_data["warnings"] += 1
        warning_types = self.aggr_data["warning_types"]
        if str(error) in warning_types:
            warning_types[str(error)] = warning_types[str(error)] + 1
        else:
            warning_types[str(error)] = 1

    def add_errors(self, error: BaseException, processor: "Processor"):
        """Add errors to aggregated data."""
        self.aggr_data["errors"] += 1
        processor.ps.aggr_data["errors"] += 1
        error_types = self.aggr_data["error_types"]
        if str(error) in error_types:
            error_types[str(error)] = error_types[str(error)] + 1
        else:
            error_types[str(error)] = 1

    def print_aggregate(self):
        """Print aggregated status data."""
        if self.time_to_print:
            process_data = {}
            self._add_per_process_data(process_data)
            self._add_per_processor_data(process_data)
            self._add_process_data_to_shared_process_dict(process_data)
            if self._aggregate_processes:
                self._export_logs_only_when_all_processes_published_their_metrics()
            else:
                self._export_logs(self.prepare_logging_data(process_data))

    def _add_per_process_data(self, process_data: dict):
        process_name = current_process().name
        for processor in self._pipeline:
            if not process_data.get(process_name):
                process_data[process_name] = {}
            process_data[processor.name] = deepcopy(processor.ps.aggr_data)

        # Add data to MultiprocessingPipeline that is supposed to stay
        process_data[process_name]["kafka_offset"] = self.kafka_offset

        # Add per process data
        process_data["processed"] = self.aggr_data["processed"]
        process_data["errors"] = self.aggr_data["errors"]
        process_data["warnings"] = self.aggr_data["warnings"]
        process_data["error_types"] = self.aggr_data["error_types"]
        process_data["warning_types"] = self.aggr_data["warning_types"]

    def _add_per_processor_data(self, process_data: dict):
        for processor in self._pipeline:
            aggr_data = processor.ps.aggr_data

            if not process_data.get(processor.name):
                process_data[processor.name] = {}

            if str(processor) not in self.rule_based_stats_exclusion:
                process_data[processor.name]["matches_per_idx"] = aggr_data["matches_per_idx"]
                process_data[processor.name]["times_per_idx"] = aggr_data["times_per_idx"]
                process_data[processor.name]["matches"] = aggr_data["matches"]
            process_data[processor.name]["processed"] = aggr_data["processed"]

    def _add_process_data_to_shared_process_dict(self, process_data: dict):
        with self._lock:
            for key in self._shared_dict.keys():
                if self._shared_dict[key] is None:
                    self._shared_dict[key] = process_data
                    break

    def _export_logs_only_when_all_processes_published_their_metrics(self):
        with self._lock:
            if not any(value is None for value in self._shared_dict.values()):
                ordered_data = self.prepare_logging_data()
                self._export_logs(ordered_data)

    def _export_logs(self, ordered_data):
        if self._file_logger is not None:
            self._file_logger.info(json.dumps(ordered_data))

        if self._prometheus_logger is not None:
            self._log_to_prometheus(ordered_data)

        if not self._cumulative:
            self._reset_statistics()

    def prepare_logging_data(self, metrics=None):
        """
        Initiates the collection and aggregation of all multiprocessing processes as well as
        logprep processors, and initializes the enrichment and clean up.

        If no metrics were given via the argument then the metrics are aggregated from the
        pipeline, otherwise the given metrics are enriched and cleaned.

        Parameters
        ----------
        metrics : dict
            Optional metrics that should be used as a starting point for the enrichment and clean
            up. If omitted then the metrics are aggregated from the pipeline

        Returns
        -------
        Cleaned and sorted dictionary with all relevant metrics of the logprep instance in total,
        each multiprocessing pipeline as well as each logprep processor.
        """
        if not metrics:
            metrics = self._get_aggregated_data_from_pipeline()
        self._add_derivative_data(metrics)

        filtered_data = StatusTracker._get_filtered_stats(metrics)
        filtered_data["timestamp"] = datetime.now().isoformat()

        return StatusTracker._get_sorted_output_dict(filtered_data)

    @staticmethod
    def _get_sorted_output_dict(filtered_data: dict) -> OrderedDict:
        sorted_data = OrderedDict(sorted(filtered_data.items()))
        ordered_data = OrderedDict()
        used_keys = []
        for key, value in sorted_data.items():
            if key.startswith("MultiprocessingPipeline"):
                ordered_data[key] = value
                used_keys.append(key)
        for key, value in filtered_data.items():
            if key in ("errors", "warnings", "error_types", "warning_types", "processed"):
                ordered_data[key] = value
                used_keys.append(key)
        for key, value in sorted_data.items():
            if key not in used_keys:
                ordered_data[key] = value
        return ordered_data

    def _add_derivative_data(self, aggr_data: dict):
        for name, value in aggr_data.items():
            if isinstance(value, dict):
                if not name.startswith("Multiprocessing") and name not in (
                    "error_types",
                    "warning_types",
                    *self.rule_based_stats_exclusion,
                ):
                    matches_per_idx = aggr_data[name]["matches_per_idx"]
                    mean_matches_per_idx = np.mean(matches_per_idx)
                    aggr_data[name]["mean_matches_per_rule"] = 0
                    if not np.isnan(mean_matches_per_idx):
                        aggr_data[name]["mean_matches_per_rule"] = f"{mean_matches_per_idx:.1f}"

                    times_per_idx = deepcopy(aggr_data[name]["times_per_idx"])
                    times_per_idx = np.divide(
                        times_per_idx,
                        matches_per_idx,
                        out=np.zeros_like(times_per_idx),
                        where=matches_per_idx != 0,
                    )
                    if times_per_idx.any():
                        aggr_data[name]["time_mean"] = f"{np.mean(times_per_idx):.10f}"

    def _get_aggregated_data_from_pipeline(self) -> dict:
        processes = self._get_process_data_from_shared_dict()

        aggregated_data = {}
        excluded_keys = ("error_types", "warning_types", "processed", "errors", "warnings")
        for process in processes:
            self._aggregate_processor_specific(aggregated_data, excluded_keys, process)
            StatusTracker._add_relevant_values_to_multiprocessing_pipelines(
                aggregated_data, process
            )
            # Aggregate non-processor specific
            for key in self.pipeline_metrics:
                if key not in aggregated_data:
                    aggregated_data[key] = 0
                aggregated_data[key] += process[key]

            StatusTracker._aggregate_error_types(aggregated_data, process)

        return aggregated_data

    def _aggregate_processor_specific(
        self, aggregated_data: dict, excluded_keys: tuple, process: dict
    ):
        for name, values in process.items():
            if name not in aggregated_data.keys() and name not in excluded_keys:
                aggregated_data[name] = values
            else:
                if isinstance(values, dict):
                    if not name.startswith("MultiprocessingPipeline") and name not in excluded_keys:
                        for key, value in values.items():
                            if isinstance(value, dict):
                                key_path = [name, key]
                                self._add_dict_values(value, aggregated_data, key_path)
                            if isinstance(value, (float, int)):
                                aggregated_data[name][key] += value

    @staticmethod
    def _add_relevant_values_to_multiprocessing_pipelines(aggregated_data: dict, process: dict):
        for name in process.keys():
            if name.startswith("MultiprocessingPipeline"):
                for key in ("processed",):
                    aggregated_data[name][key] = process[key]

    @staticmethod
    def _aggregate_error_types(aggregated_data: dict, process: dict):
        for error_type in ("error_types", "warning_types"):
            if error_type not in aggregated_data.keys():
                aggregated_data[error_type] = process[error_type]
            else:
                for error, error_count in process[error_type].items():
                    if error not in aggregated_data[error_type].keys():
                        aggregated_data[error_type][error] = 0
                    aggregated_data[error_type][error] += error_count

    def _get_process_data_from_shared_dict(self) -> list:
        processes = []
        for process in self._shared_dict.values():
            processes.append(deepcopy(process))
        for key in self._shared_dict.keys():
            self._shared_dict[key] = None
        return processes

    def _add_dict_values(self, _dict: dict, aggregated: dict, key_path: List[str]):
        for key, value in _dict.items():
            key_path.append(key)

            if isinstance(value, dict):
                self._add_dict_values(value, aggregated, key_path)
            elif isinstance(value, (float, int)):
                _iter = aggregated
                for idx, key_iter in enumerate(key_path):
                    if isinstance(_iter, dict):
                        if key_iter not in _iter.keys():
                            if idx < len(key_path) - 1:
                                _iter[key_iter] = {}
                            else:
                                _iter[key_iter] = value
                        if idx < len(key_path) - 1:
                            _iter = _iter[key_iter]
                        else:
                            _iter[key_iter] = float(_iter[key_iter]) + float(value)

            if key_path:
                key_path = key_path[:-1]

    @staticmethod
    def _get_filtered_stats(aggr_data: dict) -> dict:
        filtered_dict = deepcopy(aggr_data)
        StatusTracker._remove_numpy_arrays(aggr_data, filtered_dict)
        return filtered_dict

    @staticmethod
    def _remove_numpy_arrays(aggr_data: dict, filtered_dict: dict):
        _dict = filtered_dict
        for key_1, val_1 in aggr_data.items():
            if isinstance(val_1, dict):
                for key_2, val_2 in val_1.items():
                    if isinstance(val_2, np.ndarray):
                        del _dict[key_1][key_2]

    def increment_aggregation(self, key: str):
        """Increments a metric, given by key, of the full pipeline"""
        self.aggr_data[key] += 1

    def _log_to_prometheus(self, ordered_data):
        """
        Forwards the gathered metrics to the prometheus exporter, which will then provide them via
        a web interface.

        Parameters
        ----------
        ordered_data dict:
            An ordered dict containing all metrics for the full pipeline, each multiprocess process
            as well as each processor.
        """
        self._log_general_statistics_to_prometheus(ordered_data)
        self._log_processor_statistics_to_prometheus(ordered_data)

        metric_interval_tracker = self._prometheus_logger.tracking_interval
        metric_interval_tracker.labels(component="logprep").set(self._print_period)

    def _log_general_statistics_to_prometheus(self, ordered_data):
        """Forwards the general pipeline metrics to the prometheus exporter"""
        for metric_name in self.pipeline_metrics:
            prometheus_metric_id = self._prometheus_logger.get_metric_id_from_name(metric_name)
            metric_tracker = self._prometheus_logger.metrics[prometheus_metric_id]
            metric_tracker.labels(component="pipeline").set(ordered_data[metric_name])

    def _log_processor_statistics_to_prometheus(self, ordered_data):
        """Forwards the processor metrics to the prometheus exporter"""
        for processor in self._pipeline:
            for metric_name in ProcessorStats.metrics:
                metric_value = ordered_data[processor.name][metric_name]
                prometheus_metric_id = self._prometheus_logger.get_metric_id_from_name(metric_name)
                metric_tracker = self._prometheus_logger.metrics[prometheus_metric_id]
                metric_tracker.labels(component=processor.name).set(metric_value)
