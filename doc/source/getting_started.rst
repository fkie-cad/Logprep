===============
Getting Started
===============

Installation
============

Python should be present on the system. Currently, Python 3.10 - 3.12 are supported.
To install Logprep you have following options:

**1. Option:** Installation via PyPI:

This option is recommended if you just want to use the latest release of logprep.

..  code-block:: bash

    pip install logprep

To see if the installation was successful run :code:`logprep --version`.

**2. Option:** Installation via Git Repository:

This option is recommended if you are interested in the latest developments and might want to
contribute to them.

..  code-block:: bash

    git clone https://github.com/fkie-cad/Logprep.git
    cd Logprep
    pip install .

To see if the installation was successful run
:code:`logprep --version`.

**3. Option:** Installation via Github Release

This option is recommended if you just want to try out the latest developments.

..  code-block:: bash

    pip install git+https://github.com/fkie-cad/Logprep.git@latest

To see if the installation was successful run :code:`logprep --version`.

**4. Option:** Docker build

This option can be used to build a container image from a specific commit

..  code-block:: bash

    git clone https://github.com/fkie-cad/Logprep.git
    docker build -t logprep .

To see if the installation was successful run :code:`docker run logprep --version`.

Run Logprep
===========

If you have installed it via PyPI or the Github Development release just run:

..  code-block:: bash

    logprep run $CONFIG

Where :code:`$CONFIG` is the path to a configuration file.
For more information on running logprep with different configruation files or running
logprep with configruation from an api see the :ref:`configuration` section.



Logprep Quickstart Environment
==============================

To demonstrate the functionality of logprep this repo comes with a complete `kafka`, `logprep` and
`opensearch` stack.
To get it running `docker` and `docker-compose` (version >= 1.28) must be first installed.
The docker-compose file is located in the directory `quickstart`.
A prerequisite is to run `sysctl -w vm.max_map_count=262144`, otherwise Opensearch might not
properly start.

The environment can either be started with a Logprep container or without one:

Run without Logprep Container (default)
---------------------------------------

  1. Run from within the `quickstart` directory:
     ```bash
     docker-compose up -d
     ```
     It starts and connects `Kafka`, `logprep`, `Opensearch` and `Opensearch Dashboards`.
  2. Run Logprep against loaded environment from main `Logprep` directory:
     ```bash
     logprep run quickstart/exampledata/config/pipeline.yml
     ```

Run with Logprep Container
--------------------------

  * Run from within the `quickstart` directory:
    ```bash
    docker-compose --profile logprep up -d
    ```

Run with getting config from http server with basic authentication
------------------------------------------------------------------

  * Run from within the `quickstart` directory:
    ```bash
    docker-compose --profile basic_auth up -d
    ```
  * Run within the project root directory:
    ```bash
    export LOGPREP_CREDENTIALS_FILE="quickstart/exampledata/config/credentials.yml"
    logprep http://localhost:8081/config/pipeline.yml
    ```

Run with getting config from FDA with oauth2 authentication
-----------------------------------------------------------

Start logprep by using the oauth2 profile with docker-compose:

    ```bash
    export LOGPREP_CREDENTIALS_FILE="quickstart/exampledata/config/credentials.yml"
    docker-compose --profile oauth2 up -d
    ```


In order to run logprep with the FDA configuration it is necessary to set the following environment
variables:

- `LOGPREP_INPUT=<INPUT_CONNECTOR_CONFIG>`
- `LOGPREP_OUTPUT=<OUTPUT_CONNECTOR_CONFIG>`
- `LOGPREP_OPTIONS=<GENERAL_LOGPREP_CONFIG>`


Once they are set logprep can be started with:

```bash
logprep run "http://localhost:8000/api/v1/pipelines?stage=prod&logclass=ExampleClass"
```

### Interacting with the Quickstart Environment

The start up takes a few seconds to complete, but once everything is up
and running it is possible to write JSON events into Kafka and read the processed events in
Opensearch Dashboards. Following services are available after start up:

====================== ================= ======== ========
Service                Location          User     Password
====================== ================= ======== ========
Kafka:                 `localhost:9092`  /        /       
Kafka Exporter:        `localhost:9308`  /        /       
Logprep metrics:       `localhost:8001`  /        /       
Opensearch:            `localhost:9200`  /        /       
Opensearch Dashboards: `localhost:5601`  /        /       
Grafana Dashboards:    `localhost:3000`  admin    admin   
Prometheus:            `localhost:9090`  /        /       
Nginx:                 `localhost:8081`  user     password
Keycloak:              `localhost:8080`  admin    admin   
Keycloak Postgres:     `localhost:5432`  keycloak bitnami 
FDA:                   `localhost:8002`  logprep  logprep 
FDA Postgres:          `localhost:25432` fda      fda     
====================== ================= ======== ========

The example rules that are used in the docker instance of Logprep can be found
in `quickstart/exampledata/rules`.
Example events that trigger for the example rules can be found in
`quickstart/exampledata/input_logdata/logclass/test_input.jsonl`.
These events can be added to Kafka with the following command:

```bash
(docker exec -i kafka kafka-console-producer.sh --bootstrap-server 127.0.0.1:9092 --topic consumer) < exampledata/input_logdata/logclass/test_input.jsonl
```

Once the events have been processed for the first time, the new indices *processed*, *sre*
and *pseudonyms* should be available in Opensearch Dashboards.

The environment can be stopped via `docker-compose down`.