.. _configuration:

=============
Configuration
=============

.. automodule:: logprep.util.configuration
   :no-index:

.. autoclass:: logprep.util.configuration.Configuration
   :members: version, config_refresh_interval, process_count, restart_count, timeout, logger, input, output, error_output, pipeline, metrics, profile_pipelines, print_auto_test_stack_trace, error_backlog_size
   :no-index:

.. _reserved-event-fields:

Reserved event fields
=====================

``@LOGPREP_EVENT_ID`` is reserved for internal event tracking. Incoming events must
not supply this field, and processing rules must not create, overwrite, rename, or
delete it. To choose the output field for the event ID, use the output's
``target_id_field`` setting.

.. toctree::
   :maxdepth: 2

   input
   output
   processor
   rules
   getter
   metrics
   yaml_tags
   dot_notation
