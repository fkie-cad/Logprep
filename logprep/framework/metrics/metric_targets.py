"""This module implements different targets for the logprep metrics"""
import datetime
import json
import os
from logging import getLogger
from logging.handlers import TimedRotatingFileHandler
from os.path import dirname
from pathlib import Path

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

    @classmethod
    def create(cls, file_config):
        """Creates a MetricFileTarget"""
        file_exporter = getLogger("Logprep-JSON-File-Logger")
        file_exporter.handlers = []

        log_path = file_config.get("path", "./logprep-metrics.jsonl")
        Path(dirname(log_path)).mkdir(parents=True, exist_ok=True)
        interval = file_config.get("rollover_interval", 60 * 60 * 24)
        backup_count = file_config.get("backup_count", 10)
        file_exporter.addHandler(
            TimedRotatingFileHandler(
                log_path, when="S", interval=interval, backupCount=backup_count
            )
        )
        return MetricFileTarget(file_exporter)

    def expose(self, metrics):
        metric_json = self._convert_metrics_to_pretty_json(metrics)
        metric_json = self._add_timestamp(metric_json)
        self._file_logger.info(json.dumps(metric_json))

    @staticmethod
    def _convert_metrics_to_pretty_json(metrics):
        metric_data = {}
        for key_labels, value in metrics.items():
            metric_name, labels = split_key_label_string(key_labels)
            dotted_path = ".".join([f"{l[0]}.{l[1]}" for l in labels.items()]) + f".{metric_name}"
            add_field_to(metric_data, dotted_path, value)
        return metric_data

    @staticmethod
    def _add_timestamp(metric_json):
        """Adds a timestamp to the metric data"""
        if "meta" not in metric_json.keys():
            metric_json["meta"] = {}
        metric_json["meta"]["timestamp"] = datetime.datetime.now().isoformat()
        return metric_json


class PrometheusMetricTarget(MetricTarget):
    """
    The PrometheusMetricTarget writes the metrics to the prometheus exporter, exposing them via
    the webinterface.
    """

    def __init__(self, prometheus_exporter: PrometheusStatsExporter):
        self._prometheus_exporter = prometheus_exporter

    @classmethod
    def create(cls, metric_configs, logger):
        """Creates a PrometheusMetricTarget"""
        if not os.environ.get("PROMETHEUS_MULTIPROC_DIR", False):
            logger.warning(
                "Prometheus Exporter was is deactivated because the"
                "mandatory environment variable "
                "'PROMETHEUS_MULTIPROC_DIR' is missing."
            )
            return None

        prometheus_exporter = PrometheusStatsExporter(metric_configs, logger)
        prometheus_exporter.run()
        return PrometheusMetricTarget(prometheus_exporter)

    def expose(self, metrics):
        for key_labels, value in metrics.items():
            key, labels = split_key_label_string(key_labels)
            if key not in self._prometheus_exporter.metrics.keys():
                self._prometheus_exporter.create_new_metric_exporter(key, labels.keys())
            self._prometheus_exporter.metrics[key].labels(**labels).set(value)

        interval = self._prometheus_exporter.configuration["period"]
        self._prometheus_exporter.tracking_interval.labels(component="logprep").set(interval)
