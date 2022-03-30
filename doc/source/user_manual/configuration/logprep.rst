=======
Logprep
=======

process_count
=============

Integer, value >= 1

Count of worker processes that should be started.
The maximum performance can be probably reached by setting `process_count = Count of physical cores`.

timeout
=======

Float, value > 0.0

Logprep tries to react to signals (like sent by CTRL+C) within the given time.
The time taken for some processing steps is not always predictable, thus it is not possible to ensure that this time will be adhered to.
However, Logprep reacts quickly for small values (< 1.0), but this requires more processing power.
This can be useful for testing and debugging.
Larger values (like 5.0) slow the reaction time down, but this requires less processing power, which makes in preferable for continuous operation.

print_processed_period
======================

Integer, value > 0

Logprep does periodically write the amount of processed log messages per time period into the journal.
This value defines this time period in seconds.
It is an optional value and is set to 5 minutes by default.

.. _status_logger_configuration:

status_logger
=============

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
------

Integer, value > 0

Defines after how many seconds the metric should be written or updated.

enabled
-------

true/false

Defines if the status logger should be activated.
It is enabled by default.

cumulative
----------

true/false

Defines if the metrics should count continuously or if they should be reset after every period.
It is enabled by default.

aggregate_processes
----------

true/false

Defines if the metrics of each child process should be aggregated to single values or if the metrics
of the processes should be exported directly per process.
The aggregation is enabled by default.

targets
-------

List of targets where the statistics should be exported to. At the moment only :code:`file` and
:code:`prometheus` is allowed. Those can be further configured with the following options:

file
^^^^

| **path** *(String)*
| Path to the log file.

| **rollover_interval** *(Integer, value > 0)*
| Defines after how many seconds the log file should be rotated.

| **backup_count** *(Integer, value > 0)*
| Defines how many rotating log files should exist simultaneously.

prometheus
^^^^^^^^^^

| **port** *(Integer, value > 0)*
| Port which should be used to start the default prometheus exporter webservers

Example
-------

..  code-block:: yaml
    :linenos:

    status_logger:
      period: 10
      enabled: true
      cumulative: true
      targets:
        - prometheus:
            port: 8000
        - file:
            path: ./logs/status.json
            rollover_interval: 86400
            backup_count: 10

logger
======

The logger writes log messages into the journal.
Duplicate log messages are being aggregated if specific conditions are met.
This can be configured with the following sub parameters:

.. note::
   Logging for individual processors can be deactivated in their configuration in the pipeline by setting :code:`logging: false`.

level
-----

Configures the level of logs that should be logged.
Possible values are the Python-logging log levels:
CRITICAL, FATAL, ERROR, WARN, WARNING, INFO und DEBUG.

INFO is being used by default.
DEBUG should be only temporarily activated for debugging, since it creates a large amount of log messages.

aggregation_threshold
---------------------

Defines the amount after which duplicate log messages are being aggregated.

aggregation_period
------------------

Defines after how many seconds an aggregation of log messages will be performed.

Example
-------

..  code-block:: yaml
    :linenos:

    logger:
      level: INFO
      aggregation_threshold: 4
      aggregation_period: 10
