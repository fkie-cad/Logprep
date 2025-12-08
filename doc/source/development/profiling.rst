========================
Profiling & Benchmarking
========================

Profiling memory usage
======================

The python ecosystem contains various tools for profiling memory usage.
In the context of the logprep project additional requirements are
the support for multiprocessing, multithreading and compiled extension modules.
[`memray`](https://bloomberg.github.io/memray/) is a modern open source memory profiling solution
which supports all of the above, while being easy to use and reasonably performant.

How-to
------

This how-to describes the process how to run logprep in pipeline mode between kafka and openearch.
Whereas kafka, opensearch (and other misc components) are deployed using docker containers with ports mounted on the host,
logprep is being run on the host using `memray run` as the entrypoint.

Make sure you have all requirements installed:
- `memray`: run `pip install memray` in the virtual environment used to run logprep on the host
- `logprep`: run `pip install . && pip install ".[dev]"` in the same virtual environment
- `docker compose` / `podman compose`: see :ref:`compose_setup_with_logprep_on_host` for a more detailed how-to

First, spin up the docker containers and wait until all of them are up & running.

.. code-block:: bash

    docker compose -f examples/compose/docker-compose.yml up -d

Then, set up a pipeline configuration which enables (and preferably simplifies) profiling of the functionality in question.
For profiling kafka input, basic processing and opensearch outputs, the example pipeline configuration
(`examples/exampledata/config/pipeline.yml`) might be a good starting point.
Setting the `process_count` to 1 and reducing the backlog sizes might be helpful to produce less noise.

Then, run `memray` with `logprep` while supplying all relevant options.

Typical options entail:
- [`--follow-fork`](https://bloomberg.github.io/memray/run.html#tracking-across-forks) to follow forked subprocesses
- [`--trace-python-allocators`](https://bloomberg.github.io/memray/run.html#python-allocator-tracking) to track individual object allocations (more data, slower, helpful for tracking memory leaks)
- [`--native`](https://bloomberg.github.io/memray/run.html#native-tracking) to track allocations in extension modules as well (more data, slower)
- [`--agreggate`](https://bloomberg.github.io/memray/run.html#aggregated-capture-files) to only store aggregated data, speeding up analysis (but only after program termination)
- [`--live`](https://bloomberg.github.io/memray/run.html#live-tracking) to display a live allocation screen

.. code-block:: bash

    # Preparation:

    # Prepare a simple configuration which allows you to profile the relevant code sections
    # For instance, use examples/exampledata/config/pipeline.yml, set the process_count to 1 and reduce backlog sizes
    PIPELINE_CONFIG=examples/exampledata/config/pipeline.yml

    # Prepare log messages which trigger the relevant functionality
    # You could use examples/exampledata/input_logdata/logclass/test_input.jsonl as a starting point
    KAFKA_TEST_INPUT=examples/exampledata/input_logdata/logclass/test_input.jsonl

    ## Terminal 1: run the profiler
    memray run --follow-fork --trace-python-allocators --native logprep/run_logprep.py run $PIPELINE_CONFIG
    # identify the runner PID $RUNNER and, if relevant, the PID of the subprocess $SUBPROCESS you want to profile from the logs
    # you can also pipe output to a file and grep for Pipeline to get the pipeline subprocess PID

    ## Terminal 2: run a continuous report and open in browser
    # note that flamegraph+leaks is just one of many options
    DUMP_FILE=logprep/memray-run_logprep.py.$RUNNER.bin # for the main process
    DUMP_FILE=logprep/memray-run_logprep.py.$RUNNER.bin.$SUBPROCESS # for a subprocess
    while true; do
        TIMESTAMP=$(date +%s)
        REPORT_FILE="${DUMP_FILE}-${TIMESTAMP}.html"
        memray flamegraph $DUMP_FILE --leaks -o $REPORT_FILE --force && open $REPORT_FILE;
    done

    ## Terminal 3: continuously produce test input
    while true; do
        # sleep 1;
        (docker exec -i kafka kafka-console-producer.sh --bootstrap-server 127.0.0.1:9092 --topic consumer) < $KAFKA_TEST_INPUT;
    done


.. note::

     `memray` supports multiple different report formats.
     See more on https://bloomberg.github.io/memray/flamegraph.html
