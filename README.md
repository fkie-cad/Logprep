# Logprep

## Introduction

Logprep allows to collect, process and forward log messages from various data sources.
Log messages are being read and written by so called connectors.
Currently, connectors for Kafka and JSON files exist.

The log messages are processed step-by-step by a pipeline of processors,
where each processor modifies an event that is being `passed` through.
The main idea is that each processor performs a simple task that is easy to carry out.

Logprep is designed to be extensible with new connectors and processors.

## Documentation

The documentation for Logprep is online at https://logprep.readthedocs.io/en/latest/ or it can be built locally via tox (install via `pip3 install tox`). 
Building the documentation is done by executing the following command from within the project root directory:

`tox -e docs`

A HTML documentation can be then found in `doc/_build/html/index.html`.

## Installation

Python 3.6 should be present on the system.
All packages required for Logprep must be installed.
For this, the following command can be executed from within the project root directory: 
  
`pip3 install -r requirements.txt`

### Testing

Tox can be used to perform unit and acceptance tests (install tox via `pip3 install tox`).
Tests are started by executing `tox` in the project root directory.
This creates a virtual test environment and executes tests within it.

Multiple different test environments were defined for tox.
Those can be executed via:

`tox -e [name of the test environment]`
 
An overview of the test environments can be obtained by executing:

`tox -av`

Example:

`tox -e all`

This runs all tests, calculates the test coverage and evaluates the code quality.

In case the requirements change, the test environments must be rebuilt with the parameter '-r':

`tox -e all -r`
 

## Running Logprep

Execute the following from within the project root directory: 

`PYTHONPATH="." python3 logprep/run_logprep.py $CONFIG`

Where `$CONFIG` is the path to a configuration file (see Configuration.md).

## Validating Labeling-Schema and Rules

The following command can be executed to validate the schema and the rules:

`PYTHONPATH="." python3 logprep/run_logprep.py --validate-rules $CONFIG`

Where `$CONFIG` is the path to a configuration file (see Configuration.md).

Alternatively, the validation can be performed directly:

`PYTHONPATH="." python3 logprep/util/schema_and_rule_checker.py --labeling-schema $LABELING_SCHEMA --labeling-rules $LABELING_RULES`

Where `$LABELING_SCHEMA` is the path to a labeling-schema (JSON file) and `$LABELING_RULES` is the path to a directory with rule files (JSON/YML files, see Rules.md, subdirectories are permitted)

Analogously, `--normalization-rules` and `--pseudonymizer-rules` can be used.



## Reload the Configuration

Logprep can be issued to reload the configuration. 
For this, the signal `SIGUSR1` must be send to the Logprep process.

If the configuration does not pass a consistency check, then an error message is logged and Logprep keeps running with the previous configuration.
The configuration should be then checked and corrected on the basis of the error message.


## Quickstart Test Environment

Logprep was designed to work with the Elastic Stack and Kafka.
This repository comes with a docker-compose file that builds a pre-configured Elastic Stack with Kafka and Logprep.
To get it running docker and docker-compose (version >= 1.28) must be first installed.
The docker-compose file is located in the directory quickstart.

### Running the Test Environment

Before running docker-compose `sysctl -w vm.max_map_count=262144` must be executed.
Otherwise, Elasticsearch is not properly started.
The environment can be either started with a Logprep container or without one.
To start it without Logprep, the command `docker-compose up -d` can be executed from within the quickstart directory.
It starts and connects Kafka, ZooKeeper, Logstash, Elasticsearch and Kibana.
Logprep can be then started from the host once the quickstart environment is running and fully loaded.
The Logprep configuration file `quickstart/exampledata/config/pipeline.yml` can be used to connect to the quickstart environment.
To start the whole environment including a Logprep container, the command `docker-compose --profile logprep up -d` can be executed.

### Interacting with the Quickstart Environment

It is now possible to write JSON events into Kafka and read the processed events in Kibana.

Once everything has started, Kibana can be accessed by a web-browser with the address `127.0.0.1:5601`.
Kafka can be accessed with the console producer and consumer from Kafka with the address `127.0.0.1:9092` or from within the docker container `Kafka`.
The table below shows which ports have been exposed on localhost for the services.

#### Table of Ports for Services

|          | Kafka | ZooKeeper | Elasticsearch | Kibana |
| ---      | ---   | ---       | ---           | ---    |
| **Port** | 9092  | 2181      | 9200          | 5601   |

The example rules that are used in the docker instance of Logprep can be found in `quickstart/exampledata/rules`.
Example events that trigger for the example rules can be found in `quickstart/exampledata/input_logdata/test_input.jsonl`.
These events can be added to Kafka with the Kafka console producer within the Kafka container by executing the following command:

`(docker exec -i kafka /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server 127.0.0.1:9092 --topic consumer) < exampledata/input_logdata/test_input.jsonl`

Once the events have been processed for the first time, the new indices *processed*, *sre* and *pseudonyms* should be available in Kibana.

The environment can be stopped via `docker-compose down`.
