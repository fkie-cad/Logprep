"""This module contains functionality to start a prometheus exporter and expose metrics with it"""
from prometheus_client import REGISTRY, Gauge, multiprocess, start_http_server


class PrometheusStatsExporter:
    """Used to control the prometheus exporter and to manage the metrics"""

    metric_prefix: str = "logprep_"
    multi_processing_dir: str = None

    def __init__(self, status_logger_config, application_logger):
        self._logger = application_logger
        self.configuration = status_logger_config
        self._port = status_logger_config.get("port", 8000)

        self._prepare_multiprocessing()
        self._set_up_metrics()

    def _prepare_multiprocessing(self):
        """
        Sets up the proper metric registry for multiprocessing and handles the necessary
        temporary multiprocessing directory that the prometheus client expects.
        """
        multiprocess.MultiProcessCollector(REGISTRY, self.multi_processing_dir)

    def remove_metrics_from_process(self, pid):
        """
        Remove the prometheus multiprocessing database file from the multiprocessing directory.
        This ensures that prometheus won't export stale metrics in case a process has died.

        Parameters
        ----------
        pid : int
            The Id of the process whose metrics should be removed
        """
        multiprocess.mark_process_dead(pid)

    def _set_up_metrics(self):
        """Sets up the metrics that the prometheus exporter should expose"""
        self.metrics = {}
        self.tracking_interval = Gauge(
            f"{self.metric_prefix}tracking_interval_in_seconds",
            "Tracking interval",
            labelnames=["component"],
            registry=None,
        )

    def create_new_metric_exporter(self, metric_id, labelnames):
        """Creates a new gauge metric exporter and appends it to the already existing ones"""
        exporter = Gauge(
            metric_id,
            "Tracks the overall processing status",
            labelnames=labelnames,
            registry=None,
        )
        self.metrics[metric_id] = exporter

    def run(self):
        """Starts the default prometheus http endpoint"""
        start_http_server(self._port)
        self._logger.info(f"Prometheus Exporter started on port {self._port}")
