================
Time Measurement
================

It is possible to add the processing time to the processed events.
This can be configured in the main configuration file via `measure_time`.
It can be set to `true` or `false`.
Time Measurement is activated per default.

The processing times of all processors/modules can be then found in the field `processing_time` of each processed event.
Additionally, the hostname of the machine on which Logprep runs is listed,
which allows to read how much time has passed between the generation of the event and the beginning of the processing.