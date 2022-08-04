"""This module implements different targets for the logprep metrics"""
import datetime
import json
import os
from logging import getLogger, Logger
from logging.handlers import TimedRotatingFileHandler
from os.path import dirname
from pathlib import Path

from logprep._version import get_versions
from logprep.metrics.metric import MetricTargets
from logprep.util.helper import add_field_to
from logprep.util.prometheus_exporter import PrometheusStatsExporter


def split_key_label_string(key_label_string):
    """Splits the key label string into separate variables"""
    if ";" not in key_label_string:
        return key_label_string, {}
    key, labels = key_label_string.split(";")
    labels = labels.split(",")
    labels = [label.split(":") for label in labels]
    return key, dict(labels)


def get_metric_targets(config: dict, logger: Logger) -> MetricTargets:
    """Checks the given configuration and creates the proper metric targets"""
    metric_configs = config.get("metrics", {})

    if not metric_configs.get("enabled", False):
        logger.info("Metric tracking is disabled via config")
        return MetricTargets(None, None)

    target_configs = metric_configs.get("targets", [])
    file_target = None
    prometheus_target = None
    for target in target_configs:
        if "file" in target.keys():
            file_target = MetricFileTarget.create(target.get("file"), config)
        if "prometheus" in target.keys():
            prometheus_target = PrometheusMetricTarget.create(config, logger)
    return MetricTargets(file_target, prometheus_target)


class MetricTarget:
    """General MetricTarget defining the expose method"""

    def expose(self, metrics):
        """Exposes the given metrics to the target"""
        raise NotImplementedError  # pragma: no cover


class MetricFileTarget(MetricTarget):
    """The MetricFileTarget writes the metrics as a json to a rolling file handler"""

    def __init__(self, file_logger, config):
        self._file_logger = file_logger
        self._logprep_config = config

    @classmethod
    def create(cls, file_config, config):
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
        return MetricFileTarget(file_exporter, config)

    def expose(self, metrics):
        metric_json = self._convert_metrics_to_pretty_json(metrics)
        metric_json = self._add_meta_information(metric_json)
        self._file_logger.info(json.dumps(metric_json))

    @staticmethod
    def _convert_metrics_to_pretty_json(metrics):
        metric_data = {}
        for key_labels, value in metrics.items():
            metric_name, labels = split_key_label_string(key_labels)
            if labels:
                dotted_path = (
                    ".".join([f"{l[0]}.{l[1]}" for l in labels.items()]) + f".{metric_name}"
                )
            else:
                dotted_path = f"{metric_name}"
            add_field_to(metric_data, dotted_path, value)
        return metric_data

    def _add_meta_information(self, metric_json):
        """Adds a timestamp to the metric data"""
        if "meta" not in metric_json:
            metric_json["meta"] = {}
        metric_json["meta"]["timestamp"] = datetime.datetime.now().isoformat()

        if "version" not in metric_json.get("meta"):
            metric_json["meta"]["version"] = {
                "logprep": get_versions().get("version"),
                "config": self._logprep_config.get("version", "unset"),
            }
        return metric_json


class PrometheusMetricTarget(MetricTarget):
    """
    The PrometheusMetricTarget writes the metrics to the prometheus exporter, exposing them via
    the webinterface.
    """

    def __init__(self, prometheus_exporter: PrometheusStatsExporter, config: dict):
        self.prometheus_exporter = prometheus_exporter
        self._logprep_config = config

    @classmethod
    def create(cls, config, logger):
        """Creates a PrometheusMetricTarget"""
        if not os.environ.get("PROMETHEUS_MULTIPROC_DIR", False):
            logger.warning(
                "Prometheus Exporter was deactivated because the "
                "mandatory environment variable "
                "'PROMETHEUS_MULTIPROC_DIR' is missing."
            )
            return None

        prometheus_exporter = PrometheusStatsExporter(config.get("metrics", {}), logger)
        prometheus_exporter.run()
        return PrometheusMetricTarget(prometheus_exporter, config)

    def expose(self, metrics):
        for key_labels, value in metrics.items():
            key, labels = split_key_label_string(key_labels)
            if key not in self.prometheus_exporter.metrics.keys():
                label_names = []
                if labels:
                    label_names = labels.keys()
                self.prometheus_exporter.create_new_metric_exporter(key, label_names)

            if labels:
                self.prometheus_exporter.metrics[key].labels(**labels).set(value)
            else:
                self.prometheus_exporter.metrics[key].set(value)

        interval = self.prometheus_exporter.configuration["period"]
        labels = {
            "component": "logprep",
            "logprep_version": get_versions().get("version"),
            "config_version": self._logprep_config.get("version", "unset"),
        }
        self.prometheus_exporter.tracking_interval.labels(**labels).set(interval)
