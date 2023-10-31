"""This Module collects all available metrics and exposes them via configured outputs."""
from ctypes import c_double
from multiprocessing import Value
from time import time

import numpy as np


def split_key_label_string(key_label_string):
    """Splits the key label string into separate variables"""
    if ";" not in key_label_string:
        return key_label_string, {}
    key, labels = key_label_string.split(";")
    labels = labels.split(",")
    labels = [label.split(":") for label in labels]
    return key, dict(labels)


class MetricExposer:
    """The MetricExposer collects all metrics and exposes them via configured outputs"""

    def __init__(self, config, prometheus_exporter, shared_dict, lock, logger):
        self._shared_dict = shared_dict
        self._print_period = config.get("period", 180)
        self._cumulative = config.get("cumulative", True)
        self._aggregate_processes = config.get("aggregate_processes", True)
        self._lock = lock
        self._logger = logger
        self._first_metrics_exposed = False
        self._timer = Value(c_double, time() + self._print_period)
        self._prometheus_exporter = prometheus_exporter

    def expose(self, metrics):
        """
        Exposes the given metrics to the configured outputs. This is only done though once the
        tracking interval has passed. Depending on the configuration the metrics will be either
        exposed in an aggregated form, all multiprocessing pipelines will be combined to one
        pipeline, or in an independent form, where each multiprocessing pipeline will be exposed
        directly.
        """
        if not self._prometheus_exporter:
            return

        if self._time_to_expose():
            if self._aggregate_processes:
                self._store_metrics(metrics)
                self._expose_aggregated_metrics_from_shared_dict()
            else:
                self._send_to_output(metrics.expose())

            if not self._cumulative:
                metrics.reset_statistics()

            if not self._first_metrics_exposed:
                self._logger.info("Started exposing metrics")
                self._first_metrics_exposed = True

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
        with self._lock:
            if not any(value is None for value in self._shared_dict.values()):
                aggregated_metrics = self._aggregate_metrics()
                self._send_to_output(aggregated_metrics)
                self._clear_storage()

    def _aggregate_metrics(self):
        metrics_per_pipeline = [
            metric.expose() for metric in self._shared_dict.values() if metric is not None
        ]
        metrics_per_pipeline = self._strip_pipeline_metric_label(metrics_per_pipeline)
        metric_reference_keys = metrics_per_pipeline[0].keys()
        aggregated_metrics = {}
        for key in metric_reference_keys:
            key_values = [m[key] for m in metrics_per_pipeline]
            if "mean" in key:
                aggregated_metrics[key] = np.mean(key_values)
            else:
                aggregated_metrics[key] = np.sum(key_values)
        return aggregated_metrics

    def _strip_pipeline_metric_label(self, metrics_per_pipeline):
        stripped_metrics = []
        for metrics in metrics_per_pipeline:
            stripped_dict = dict((self._strip_key(key), value) for key, value in metrics.items())
            stripped_metrics.append(stripped_dict)
        return stripped_metrics

    @staticmethod
    def _strip_key(key, label_name="pipeline"):
        key, label = split_key_label_string(key)
        label.pop(label_name, None)
        if label:
            label = [":".join(item) for item in label.items()]
            label = ",".join(label)
            return f"{key};{label}"
        return key

    def _send_to_output(self, metrics):
        """
        Passes the metric object to the configured outputs such that they
        can transform and expose them
        """
        for key_labels, value in metrics.items():
            key, labels = split_key_label_string(key_labels)
            if key not in self._prometheus_exporter.metrics.keys():
                label_names = []
                if labels:
                    label_names = labels.keys()
                self._prometheus_exporter.create_new_metric_exporter(key, label_names)

            if labels:
                self._prometheus_exporter.metrics[key].labels(**labels).set(value)
            else:
                self._prometheus_exporter.metrics[key].set(value)

        interval = self._prometheus_exporter.configuration["period"]
        labels = {
            "component": "logprep",
        }
        self._prometheus_exporter.tracking_interval.labels(**labels).set(interval)
