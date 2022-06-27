"""This module implements different targets for the logprep metrics"""
import json

from logprep.util.helper import add_field_to
from logprep.util.prometheus_exporter import PrometheusStatsExporter


def split_key_label_string(key_label_string):
    """Splits the key label string into separate variables"""
    key, labels = key_label_string.split(";")
    labels = labels.split(",")
    labels = [label.split(":") for label in labels]
    return key, dict(labels)


class MetricTarget:
    """General MetricTarget defining the expose method"""

    def expose(self, metrics):
        """Exposes the given metrics to the target"""
        raise NotImplementedError  # pragma: no cover


class MetricFileTarget(MetricTarget):
    """The MetricFileTarget writes the metrics as a json to a rolling file handler"""

    def __init__(self, file_logger):
        self._file_logger = file_logger

    def expose(self, metrics):
        # TODO: add timestamp to file target
        metrics = self._convert_metrics_to_pretty_json(metrics)
        self._file_logger.info(json.dumps(metrics))

    def _convert_metrics_to_pretty_json(self, metrics):
        metric_data = {}
        for key_labels, value in metrics.items():
            metric_name, labels = split_key_label_string(key_labels)
            dotted_path = ".".join(labels.values()) + f".{metric_name}"
            add_field_to(metric_data, dotted_path, value)
        return metric_data


class PrometheusMetricTarget(MetricTarget):
    """
    The PrometheusMetricTarget writes the metrics to the prometheus exporter, exposing them via
    the webinterface.
    """

    def __init__(self, prometheus_exporter: PrometheusStatsExporter):
        self._prometheus_exporter = prometheus_exporter

    def expose(self, metrics):
        for key_labels, value in metrics.items():
            key, labels = split_key_label_string(key_labels)
            if key not in self._prometheus_exporter.metrics.keys():
                self._prometheus_exporter.create_new_metric_exporter(key, labels.keys())
            self._prometheus_exporter.metrics[key].labels(**labels).set(value)
