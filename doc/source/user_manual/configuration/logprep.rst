=======
Logprep
=======

version
=======

It is optionally possible to set a version to your configuration file which can be printed via
:code:`logprep --version config/pipeline.yml`.
This has no effect on the execution of logprep and is merely used for documentation purposes.

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


config_refresh_interval
-----------------------

Configures the interval in seconds on which logprep should try to reload the configuration.
This config key is optional. If not configured, logprep won't reload the configuration automatically.
If configured the configuration will only be reloaded if the configuration version changes.
If http errors occurs on configuration reload `config_refresh_interval` is set to a quarter
of the current `config_refresh_interval` until a minimum of 5 seconds is reached.
