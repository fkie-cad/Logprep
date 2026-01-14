========================
Profiling & Benchmarking
========================

How-to: Profiling Memory Usage in Pipelie Mode
==============================================

The Python ecosystem offers a variety of tools for profiling memory usage.
For the **logprep** project, additional requirements include support for
**multiprocessing**, **multithreading**, and **compiled extension modules**.
`Memray <https://bloomberg.github.io/memray/>`_ is a modern, open-source memory profiling tool
that meets these requirements.
It is easy to use, performant, and supports all the necessary features.

This guide describes how to profile **logprep** running in pipeline mode
between **Kafka** and **OpenSearch**.
While Kafka, OpenSearch, and other components are deployed using Docker containers
with ports exposed on the host,
**logprep** runs directly on the host using ``memray run`` as the entry point.

The following diagram illustrates the high-level setup:

.. raw:: html
   :file: diagrams/memory-profiling-setup.drawio.html

---

Install Dependencies
--------------------

Ensure all required dependencies are installed on the host:

- **Memray**: Install using ``pip install memray`` in the virtual environment where **logprep** runs.
- **Logprep**: Install using ``pip install . && pip install ".[dev]"`` in the same virtual environment.
- **Docker** / **Podman**: Refer to :ref:`the respective docs <compose_setup_with_logprep_on_host>` for detailed instructions.

Prepare the Execution Environment
---------------------------------

Start the Docker containers and wait for them to be fully operational:

.. code-block:: bash

    docker compose -f examples/compose/docker-compose.yml up -d

Prepare a Test Scenario
-----------------------

Set up a **logprep** configuration and test inputs to trigger the desired functionality.
Simplify the setup to minimize noise in the system.

Logprep Configuration
^^^^^^^^^^^^^^^^^^^^^

- Use ``examples/exampledata/config/pipeline.yml`` as a starting point for profiling Kafka input,
  basic processing, and OpenSearch output.
- Set ``process_count`` to **1** and reduce backlog sizes to further simplify the setup.

Log Data
^^^^^^^^

- Use ``examples/exampledata/input_logdata/logclass/test_input.jsonl`` as a starting point for
  generating log events.
- Make adequate modifications to focus on the desired functionality.

Configure Memray
----------------

Select the appropriate **Memray** configuration options based on the code being profiled
(main process, subprocesses, or native code).
For this guide, we use the following options to track potential memory issues in the pipeline process,
including native code:

- ``--follow-fork``
- ``--trace-python-allocators``
- ``--native``

Additional CLI Options
^^^^^^^^^^^^^^^^^^^^^^

``--follow-fork``
   To follow forked subprocesses.
   `<https://bloomberg.github.io/memray/run.html#tracking-across-forks>`__

``--trace-python-allocators``
   To track individual object allocations (more data, slower, helpful for tracking memory leaks).
   `<https://bloomberg.github.io/memray/run.html#python-allocator-tracking>`__

``--native``
   To track allocations in extension modules as well (more data, slower).
   `<https://bloomberg.github.io/memray/run.html#native-tracking>`__

``--aggregate``
   To only store aggregated data, speeding up analysis (but only after program termination).
   `<https://bloomberg.github.io/memray/run.html#aggregated-capture-files>`__

``--live``
   To display a live allocation screen.
   `<https://bloomberg.github.io/memray/run.html#live-tracking>`__

Run the Experiment
------------------

The experiment requires multiple terminals to manage parallel processes.

Terminal 1: Run the Profiler
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   # Prepare a simple configuration to profile relevant code sections.
   PIPELINE_CONFIG=examples/exampledata/config/pipeline.yml

   # Run the profiler
   memray run --follow-fork --trace-python-allocators --native logprep/run_logprep.py run $PIPELINE_CONFIG

   # Identify the runner PID ($RUNNER) and, if applicable, the PID of the subprocess ($SUBPROCESS) from the logs.
   # Alternatively, pipe the output to a file and search for "Pipeline" to find the subprocess PID.

Terminal 2: Generate Continuous Reports
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   # For the main process
   DUMP_FILE=logprep/memray-run_logprep.py.$RUNNER.bin

   # For a subprocess
   DUMP_FILE=logprep/memray-run_logprep.py.$RUNNER.bin.$SUBPROCESS

   while true; do
      TIMESTAMP=$(date +%s)
      REPORT_FILE="${DUMP_FILE}-${TIMESTAMP}.html"
      memray flamegraph $DUMP_FILE --leaks -o $REPORT_FILE --force && open $REPORT_FILE
      # ^ generated reports are opened automatically in the browser
   done

Terminal 3: Continuously Produce Test Input
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   # Prepare log messages to trigger the desired functionality.
   KAFKA_TEST_INPUT=examples/exampledata/input_logdata/logclass/test_input.jsonl

   while true; do
      docker exec -i kafka kafka-console-producer.sh --bootstrap-server 127.0.0.1:9092 --topic consumer < $KAFKA_TEST_INPUT
   done

.. note::
   **Memray** supports multiple report formats.
   For more details, see the
   `Memray Flamegraph Documentation <https://bloomberg.github.io/memray/flamegraph.html>`_.
