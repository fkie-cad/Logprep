Configuration File
==================

Configuration is done via a YAML-File.
Logprep searches for the file :code:`/etc/logprep/pipeline.yml` if no configuration file is passed.
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

It is possible to use environment variables in all configuration and rules files in all places.
Environment variables have to be setted in uppercase. Lowercase variables are ignored.

The following config file will be valid by setting the given environment variables:

..  code-block:: yaml
    :caption: pipeline.yml config file

    version: $LOGPREP_VERSION
    process_count: $LOGPREP_PROCESS_COUNT
    timeout: 0.1
    logger:
        level: $LOGPREP_LOG_LEVEL
    $LOGPREP_PIPELINE
    $LOGPREP_INPUT
    $LOGPREP_OUTPUT


.. code-block:: bash
    :caption: setting the bash environment variables

    export LOGPREP_VERSION="1"
    export LOGPREP_PROCESS_COUNT="1"
    export LOGPREP_LOG_LEVEL="DEBUG"
    export LOGPREP_PIPELINE="
    pipeline:
        - labelername:
            type: labeler
            schema: quickstart/exampledata/rules/labeler/schema.json
            include_parent_labels: true
            specific_rules:
                - quickstart/exampledata/rules/labeler/specific
            generic_rules:
                - quickstart/exampledata/rules/labeler/generic"
    export LOGPREP_OUTPUT="
    output:
        kafka:
            type: confluentkafka_output
            bootstrapservers:
            - 172.21.0.5:9092
            topic: producer
            error_topic: producer_error
            ack_policy: all
            compression: none
            maximum_backlog: 10000
            linger_duration: 0
            flush_timeout: 30
            send_timeout: 2
            ssl:
                cafile:
                certfile:
                keyfile:
                password:"
    export LOGPREP_INPUT="
    input:
        kafka:
            type: confluentkafka_input
            bootstrapservers:
            - 172.21.0.5:9092
            topic: consumer
            group: cgroup3
            auto_commit: true
            session_timeout: 6000
            offset_reset_policy: smallest
            ssl:
                cafile:
                certfile:
                keyfile:
                password:"


This section explains the possible configuration parameters.

Reading the Configuration
-------------------------

Logprep can be "issued" to reload the configuration by sending the signal `SIGUSR1` to the Logprep process or by defining the
configuration option :code:`config_refresh_interval`.

An error message is thrown if the configuration does not pass a consistency check, and the processor proceeds to run with its old configuration.
Then the configuration should be checked and corrected according to the error message.
