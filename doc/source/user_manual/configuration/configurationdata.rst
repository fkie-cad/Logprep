Configuration File
==================

Configuration is done via a YAML-File.
Logprep searches for the file `/etc/logprep/pipeline.yml`. It is possible to provide a different path.

The options under `connector` and `pipeline` are passed to factories in Logprep.
They contain settings for each separate processor and connector.
Details for configuring connectors are described in `doc/config/Connector*` and for processors in `doc/config/Processor*`.
General information about the configuration of the pipeline can be found in :doc:`pipeline`.

This section explains the possible configuration parameters.

Reading the Configuration
-------------------------

Logprep can be "issued" to reload the configuration by sending the signal `SIGUSR1` to the Logprep process.

An error message is thrown if the configuration does not pass a consistency check, and the processor proceeds to run with its old configuration.
Then the configuration should be checked and corrected according to the error message.
