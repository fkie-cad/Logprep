=======
Metrics
=======

Configuration
=============

.. _status_logger_configuration:

status_logger
-------------

The status logger exports metrics like counts of processed events, errors or warnings, for all
processors and multiprocessing pipelines. The metrics can be exported as a rotating log file with
JSON lines and/or via a Prometheus Exporter. The log file format has additional information like
warning and error types. Those are not available for the Prometheus Exporter. Both can be activated
at the same time. By default only the file target is activated. To activate the prometheus exporter
the required target has to be configured. Furthermore the utilized `prometheus python
client <https://github.com/prometheus/client_python>`_ requires the configuration of the environment
variable :code:`PROMETHEUS_MULTIPROC_DIR`, a directory to save temporary files needed for in-between
process communication.

.. WARNING::
   The configured directory :code:`PROMETHEUS_MULTIPROC_DIR` will be cleared on every startup. Make
   sure it does not contain any other files as they will be lost afterwards.

The status_logger can export it's metrics as an aggregation of all child processes or independently,
without any aggregation.

.. hint::
   To achieve the best results for the prometheus exporter it is suggested to deactivate
   `cumulative` metrics as well as the process aggregation `aggregate_processes`. This ensures that
   each process is exported as it's own metrics giving full transparency.
   And deactivating `cumulative` will result in exporting only the statistics of the past period
   instead of counting endlessly.

This status_logger is configured with the following sub parameters:

period
^^^^^^

Integer, value > 0

Defines after how many seconds the metric should be written or updated.

enabled
^^^^^^^

true/false

Defines if the status logger should be activated.
It is enabled by default.

cumulative
^^^^^^^^^^

true/false

Defines if the metrics should count continuously (true) or if they should be reset after every period (false).
It is enabled by default.

aggregate_processes
^^^^^^^^^^^^^^^^^^^

true/false

Defines if the metrics of each child process should be aggregated to single values or if the metrics
of the processes should be exported directly per process.

Time Measurement
^^^^^^^^^^^^^^^^

It is possible to export metrics that indicate the processing times of one or more events.
This can be configured in the main configuration file via :code:`metrics.measure_time`.
If this config field is available and the subfield :code:`enabled` is set to :code:`true` then the
processing times are measured and exported.
Through the metric tracking it is possible to export those metrics as file or through the prometheus
exporter.
There the processing times represent the average of all events during the configured
period.
It is also possible to export the processing time for each event independently by appending the
information to the event.
The processing times of all processors/modules can be then found in the field
:code:`processing_time` of each processed event.
Additionally, the hostname of the machine on which Logprep runs is listed,
which allows to read how much time has passed between the generation of the event and the
beginning of the processing.

Time Measurement is deactivated by default.

If only the general metrics are activated then the metric for the time measurement will be 0.

targets
^^^^^^^

List of targets where the statistics should be exported to. At the moment only :code:`file` and
:code:`prometheus` are allowed. Those can be further configured with the following options:

**file**

| **path** *(String)*
| Path to the log file.

| **rollover_interval** *(Integer, value > 0)*
| Defines after how many seconds the log file should be rotated.

| **backup_count** *(Integer, value > 0)*
| Defines how many rotating log files should exist simultaneously.

**prometheus**

| **port** *(Integer, value > 0)*
| Port which should be used to start the default prometheus exporter webservers

Example
-------

..  code-block:: yaml
    :linenos:

    metrics:
      enabled: true
      period: 10
      cumulative: true
      aggregate_processes: false
      measure_time:
        enabled: true
        append_to_event: false
      targets:
        - prometheus:
            port: 8000
        - file:
            path: ./logs/status.json
            rollover_interval: 86400
            backup_count: 10


Metrics Overview
================

.. autoclass:: logprep.framework.rule_tree.rule_tree.RuleTree.RuleTreeMetrics
   :members:
   :undoc-members:
   :private-members:
   :inherited-members:

.. autoclass:: logprep.abc.processor.Processor.ProcessorMetrics
   :members:
   :undoc-members:
   :private-members:
   :inherited-members:

.. autoclass:: logprep.processor.domain_resolver.processor.DomainResolver.DomainResolverMetrics
   :members:
   :undoc-members:
   :private-members:
   :inherited-members:

.. autoclass:: logprep.processor.pseudonymizer.processor.Pseudonymizer.PseudonymizerMetrics
   :members:
   :undoc-members:
   :private-members:
   :inherited-members:

.. autoclass:: logprep.framework.pipeline.Pipeline.PipelineMetrics
   :members:
   :undoc-members:
   :private-members:
   :inherited-members:
