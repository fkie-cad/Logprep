Configuration File
==================

Configuration is done via a YAML-File.
Logprep searches for the file :code:`/etc/logprep/pipeline.yml` if not configuration file is passed.
You can pass a different configuration file via a valid file path or url.

..  code-block:: bash

    logprep /different/path/file.yml

or

..  code-block:: bash
    
    logprep http://url-to-our-yaml-file-or-api


The options under :code:`input`, :code:`output` and :code:`pipeline` are passed to factories in Logprep.
They contain settings for each separate processor and connector.
Details for configuring connectors are described in :ref:`output` and :ref:`input` and for processors in :ref:`processors` .
General information about the configuration of the pipeline can be found in :ref:`pipeline_config` .

This section explains the possible configuration parameters.

Reading the Configuration
-------------------------

Logprep can be "issued" to reload the configuration by sending the signal `SIGUSR1` to the Logprep process.

An error message is thrown if the configuration does not pass a consistency check, and the processor proceeds to run with its old configuration.
Then the configuration should be checked and corrected according to the error message.
