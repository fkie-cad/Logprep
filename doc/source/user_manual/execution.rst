Executing Logprep
=================

To execute Logprep the following command can be executed in the root directory of the project:

..  code-block:: bash

    logprep run $CONFIG

Where :code:`$CONFIG` is the path or a url to a configuration file (see :ref:`configuration`).

To get help on the different parameters use:

..  code-block:: bash

    logprep --help


Event Generation
----------------

Logprep has the additional functionality of generating events and sending them to two
different targets.
It can send events to kafka, while also loading events from kafka or reading them from file,
and it can send events to a http endpoint as POST requests.

Following sections describe the usage of these event generators.

Kafka
^^^^^

The kafka load-tester can send a configurable amount of documents to Kafka.
The documents that are being send can be obtained either from Kafka or from a file with JSON lines.

It can be configured how many documents should be retrieved from Kafka (if Kafka is used as source)
and how many documents will be sent.
Documents obtained from Kafka won't be written down to disk.

The documents will be sent repeatedly until the desired amount has been sent.
The `tags` field and the `_index` field of each document will be set to `load-tester`.
Furthermore, a field `load-tester-unique` with a unique value will be added to each document every
time a document is sent.
This is done to prevent that repeatedly sent documents are identical.

To find out more about the usage of the kafka load-tester execute:

.. code-block:: bash

    logprep generate kafka --help

Configuration
"""""""""""""

The kafka load-tester is configured via a YAML file.
It must have the following format:

.. code-block:: yaml
    :caption: Example configuration file for the kafka load-tester

    logging_level: LOG_LEVEL  # Default: "INFO"
    source_count: INTEGER  # Number of documents to obtain form Kafka
    count: INTEGER  # Number of documents to send
    process_count: INTEGER  # Number of processes (default: 1)
    profile: BOOL  # Shows profiling data (default: false)
    target_send_per_sec: INTEGER  # Desired number of documents to send per second with each process. Setting it to 0 sends as much as possible (default: 0).

    kafka:
    bootstrap_servers:  # List of bootstrap servers
        - URL:PORT  # i.e. "127.0.0.1:9092"
    consumer:  # Kafka consumer
        topic: STRING  # Topic to obtain documents from
        group_id: STRING  # Should be different from the group_id of the Logprep Consumer, otherwise the offset in Logprep will be changed!
        timeout: FLOAT  # Timeout for retrieving documents (default: 1.0)
    producer:  # Kafka producer
        acks: STRING/INTEGER # Determines if sending should be acknowledged (default: 0)
        compression_type: STRING  # Compression type (default: "none")
        topic: STRING  # Topic to send documents to
        queue_buffering_max_messages: INTEGER # Batch for sending documents (default: 10000)
        linger_ms: INTEGER # Time to wait before a batch is sent if the max wasn't reached before (default: 5000)
        flush_timeout: FLOAT # Timeout to flush the producer (default 30.0)
    ssl:  # SSL authentication (Optional)
        ca_location: STRING
        certificate_location: STRING
        key:
        location: STRING
        password: STRING # Optional

Unused parameters must be removed or commented.


Kafka2
^^^^^^

Kafka2 is a load tester for generating events based on templated sample files
stored in a dataset directory. These events are then sent to specified Kafka topics.
The event generation process is identical to the :ref:`http_generator` generator.

The dataset directory containing the sample files must follow this structure:

.. code-block:: bash

    | - Test-Logs-Directory
    | | - Test-Logs-Class-1-Directory
    | | | - config.yaml
    | | | - Test-Logs-1.jsonl
    | | | - Test-Logs-2.jsonl
    | | - Test-Logs-Class-2-Directory
    | | | - config.yaml
    | | | - Test-Logs-A.jsonl
    | | | - Test-Logs-B.jsonl

While the jsonl event files can have arbitrary names, the `config.yaml` needs to be called exactly
that. It also needs to follow the following schema:

.. code-block:: yaml
    :caption: Example configuration file for the http event generator

    target: example_topic
    timestamps:
    - key: TIMESTAMP_FIELD_1
        format: "%Y%m%d"
    - key: TIMESTAMP_FIELD_1
        format: "%H%M%S"
        time_shift: "+0200"  # Optional, sets time shift in hours and minutes, if needed ([+-]HHMM)

To learn more about the Kafka event generator, run:

.. code-block:: bash

    logprep generate kafka2 --help



.. _http_generator:

Http
^^^^

The http endpoint allows for generating events based on templated sample files which are stored
inside a dataset directory.

The dataset directory with the sample files has to have the following format:

.. code-block:: bash

    | - Test-Logs-Directory
    | | - Test-Logs-Class-1-Directory
    | | | - config.yaml
    | | | - Test-Logs-1.jsonl
    | | | - Test-Logs-2.jsonl
    | | - Test-Logs-Class-2-Directory
    | | | - config.yaml
    | | | - Test-Logs-A.jsonl
    | | | - Test-Logs-B.jsonl

While the jsonl event files can have arbitrary names, the `config.yaml` needs to be called exactly
that. It also needs to follow the following schema:

.. code-block:: yaml
    :caption: Example configuration file for the http event generator

    target: /endpoint/logsource/path
    timestamps:
    - key: TIMESTAMP_FIELD_1
        format: "%Y%m%d"
    - key: TIMESTAMP_FIELD_1
        format: "%H%M%S"
        time_shift: "+0200"  # Optional, sets time shift in hours and minutes, if needed ([+-]HHMM)

To find out more about the usage of the http event generator execute:

.. code-block:: bash

    logprep generate http --help


Pseudonymization Tools
----------------------

Logprep provides tools to pseudonymize and depseudonymize values. This can be useful for testing
and debugging purposes. But this can also be used to depseudonymize values pseudonymized by
Logprep :code:`Pseudonymizer` Processor.

These tools can be used to pseudonymize given strings using the same method as used in Logprep
and provides functionality to depseudonymize values using a pair of keys.

generate keys
^^^^^^^^^^^^^

.. code-block:: bash

    logprep pseudo generate -f analyst 1024
    logprep pseudo generate -f depseudo 2048

this will generate four files to pseudonymize in the next step.
the depseudo key has to be longer than the analyst key due to the hash padding involved in the procedure.

* get help with :code:`logprep pseudo generate --help`

pseudonymize
^^^^^^^^^^^^

.. code-block:: bash

    logprep pseudo pseudonymize analyst.crt depseudo.crt mystring

This will pseudonymize the provided string using the analyst and depseudo keys.
 get help with :code:`logprep pseudo pseudonymize --help`

depseudonymize
^^^^^^^^^^^^^^

.. code-block:: bash

    logprep pseudo depseudonymize analyst depseudo <output from above>

This will depseudonymize the provided string using the analyst and depseudo keys.

* get help with :code:`logprep pseudo depseudonymize --help`

Restart Behavior
----------------

Logprep reacts on failures during pipeline execution by restarting 5 (default) times.
This restart count can be configured in the configuration file with the parameter
:code:`restart_count`. If the restart count is set to a negative number, the restart count
is infinite and logprep will restart the pipelines immediately after a failure.
On logprep start a random timeout seed is calculated between 100 and 1000 milliseconds.
This seed is then doubled after each restart and is used as sleep period
between pipeline restart tryouts.

If the pipeline restart succeeds, the restart count is reset to 0.


Exit Codes
----------

.. autoclass:: logprep.util.defaults.EXITCODES
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:


Healthchecks
------------

Logprep provides a health endpoint which can be used to check the health of all components.
The asgi app for the healthcheck endpoint is implemented in :code:`logprep.metrics.exporter.make_patched_asgi_app` and
will be recreated on every restart of logprep (e.g. after a configuration change) or on creation of the first pipeline process.
The healthcheck endpoint is available at :code:`/health` if metrics are enabled and can be accessed via HTTP GET.

* On success, the healthcheck endpoint will return a :code:`200` status code and a payload :code:`OK`.
* On failure, the healthcheck endpoint will return a :code:`503` status code and a payload :code:`FAIL`.

Healthchecks are implemented in components via the :code:`health()` method. You have to ensure to call
the :code:`super.health()` method in new implemented health checks.
The health is checked for the first time after the first pipeline process is started and then every 5 seconds.
You can configure the healthcheck timeout on component level with the parameter :code:`health_timeout`.
The default value is 1 second.

Healthchecks are used in the provided helm charts as default for readiness probes.

Event Generation Guide
----------------------

Prerequisites
^^^^^^^^^^^^^

Before running either the HTTP or Kafka event generation process, ensure that
the required environment is set up as described in :doc:`../examples/compose`.

Start the necessary environment using the following command:

.. code-block:: bash

    source PROMETHEUS_MULTIPROC_DIR="/tmp/logprep"
    docker compose -f examples/compose/docker-compose.yml up -d

HTTP Event Generation
^^^^^^^^^^^^^^^^^^^^^

To start an example pipeline for HTTP event generation, execute the following steps:

1. Create the required directory:

.. code-block:: bash

    mkdir -p /tmp/logprep/

2. Run the pipeline

.. code-block:: bash

    logprep run ./examples/exampledata/config/http_pipeline.yml

Generate and send events to the HTTP endpoint:

.. code-block:: bash

    logprep generate http --target-url http://localhost:9000/ --input-dir ./examples/exampledata/input_logdata_http --events 10000

After execution, the console should display an output similar to:

.. code-block:: bash

    "Number of failed events": 0,
    "Number of successful events": 10000,
    "Requests Connection Errors": 0,
    "Requests Timeouts": 0,
    "Requests http status 200": 20,
    "Requests total": 20

The HTTP 200 status indicates that the generated data was successfully transferred.
Since no batch size was specified, the default batch size was used, resulting in 20 batches being sent.

Kafka Event Generation
^^^^^^^^^^^^^^^^^^^^^^

To generate events and send them to Kafka, follow these steps:

1. Run the pipeline:

.. code-block:: bash

    logprep run ./examples/exampledata/config/http_pipeline.yml

2. Generate and send events to Kafka:

.. code-block:: bash

    logprep generate kafka2 --input-dir ./examples/exampledata/input_logdata_kafka/  --batch-size 1000 --events 10000 --output-config '{"bootstrap.servers": "127.0.0.1:9092"}'

After execution, the console should display an output similar to:

.. code-block:: bash

    "Is the producer healthy": true,
    "Number of processed batches": 10,
    "Number of successful events": 10000

This confirms that the Kafka producer is healthy, and all events have been successfully processed.
