"""This Module collects all available metrics and exposes them via configured outputs."""
from ctypes import c_double
from multiprocessing import Value
from time import time

import numpy as np

from logprep.framework.metric_targets import MetricFileTarget, PrometheusMetricTarget


class MetricExposer:
    """The MetricExposer collects all metrics and exposes them via configured outputs"""

    def __init__(self, config, status_logger_collection, shared_dict, lock):
        self._shared_dict = shared_dict
        self._print_period = config.get("period", 180)
        self._cumulative = config.get("cumulative", True)
        self._aggregate_processes = config.get("aggregate_processes", True)
        self._lock = lock
        self._timer = Value(c_double, time() + self._print_period)

        self.output_targets = []
        if status_logger_collection.file_logger:
            target = MetricFileTarget(status_logger_collection.file_logger)
            self.output_targets.append(target)
        if status_logger_collection.prometheus_exporter:
            target = PrometheusMetricTarget(status_logger_collection.prometheus_exporter)
            self.output_targets.append(target)

    def expose(self, metrics):
        self._store_metrics(metrics)
        if self._time_to_expose():
            if self._aggregate_processes:
                self._expose_aggregated_metrics_from_shared_dict()
            if not self._aggregate_processes:
                self._send_to_output(metrics.expose())

    def _store_metrics(self, metrics):
        with self._lock:
            empty_keys = [key for key, value in self._shared_dict.items() if value is None]
            if empty_keys:
                self._shared_dict[empty_keys[0]] = metrics

    def _clear_storage(self):
        for key in self._shared_dict.keys():
            self._shared_dict[key] = None

    def _time_to_expose(self) -> bool:
        """
        Check if period of metric collection has passed and if with that the metrics
        should be exposed now.
        """
        with self._lock:
            if time() < self._timer.value:
                return False
            self._timer.value = time() + self._print_period
            return True

    def _expose_aggregated_metrics_from_shared_dict(self):
        aggregated_metrics = self._aggregate_metrics()
        self._send_to_output(aggregated_metrics)
        self._clear_storage()

    def _aggregate_metrics(self):
        metrics = [metric.expose() for metric in self._shared_dict.values() if metric is not None]
        metric_keys = metrics[0].keys()
        aggregated_metrics = {}
        for key in metric_keys:
            key_values = [m[key] for m in metrics]
            if "mean" in key:
                aggregated_metrics[key] = np.mean(key_values)
            else:
                aggregated_metrics[key] = np.sum(key_values)
        return aggregated_metrics

    def _send_to_output(self, metrics):
        """
        Passes the metric object to the configured outputs such that they
        can transform and expose them
        """
        for output in self.output_targets:
            output.expose(metrics)
