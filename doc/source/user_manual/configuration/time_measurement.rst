================
Time Measurement
================

It is possible to export metrics that indicate the processing times of one or more events.
This can be configured in the main configuration file via :code:`measure_time`.
If this config field is available and the subfield :code:`enabled` is set to :code:`true` then the
processing times are measured and exported via the :ref:`status_logger_configuration`.
Through the status logger it is possible to export those metrics as file or through the prometheus
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

If only the status_logger is activated then the metric for the time measurement will be 0.

Configuration Example
---------------------

..  code-block:: yaml
    :linenos:

    measure_time:
      enabled: true
      append_to_event: false