
Docker Compose Example Deployment
=================================

To demonstrate the functionality of logprep this repo comes with a complete `kafka`, `logprep` and
`opensearch` stack.
To get it running `docker` with compose support must be first installed.
The docker compose file is located in the directory `examples/compose`.
A prerequisite is to run `sysctl -w vm.max_map_count=262144`, otherwise Opensearch might not
properly start.

The environment can either be started with a Logprep container or without one:

Run without Logprep Container (default)
---------------------------------------

  1. Run from within the `examples/compose` directory:

     .. code-block:: bash

      docker compose up -d

     It starts and connects `Kafka`, `logprep`, `Opensearch` and `Opensearch Dashboards`.
  2. Run Logprep against loaded environment from main `Logprep` directory:

     .. code-block:: bash

      logprep run examples/exampledata/config/pipeline.yml

    If logprep is run with the metrics enabled, the necessary environment variable has to be set first:

    .. code-block:: bash

      export PROMETHEUS_MULTIPROC_DIR="tmp/logprep"
      logprep run examples/exampledata/config/pipeline.yml




Run with Logprep Container
--------------------------

  * Run from within the `examples/compose` directory:

    .. code-block:: bash

      docker compose --profile logprep up -d


Run with getting config from http server with basic authentication
------------------------------------------------------------------

  * Run from within the `examples/compose` directory:

    .. code-block:: bash

      docker compose --profile basic_auth up -d

  * Run within the project root directory:

    .. code-block:: bash

      export LOGPREP_CREDENTIALS_FILE="examples/exampledata/config/credentials.yml"
      logprep run http://localhost:8081/config/pipeline.yml


Run with getting config from http server with mTLS authentication
-----------------------------------------------------------------

  * Run from within the `examples/compose` directory:

    .. code-block:: bash

      docker compose --profile mtls up -d

  * Run within the project root directory:

    .. code-block:: bash

      export LOGPREP_CREDENTIALS_FILE="examples/exampledata/config/credentials.yml"
      logprep run https://localhost:8082/config/pipeline.yml


Interacting with the Compose Environment
----------------------------------------

The start up takes a few seconds to complete, but once everything is up
and running it is possible to write JSON events into Kafka and read the processed events in
Opensearch Dashboards.
Considering, you have started logprep.
Following services are available after start up:

====================== ================= ========================  =======================
Service                Location          User                      Password
====================== ================= ========================  =======================
Kafka:                 `localhost:9092`  /                         /
Kafka Exporter:        `localhost:9308`  /                         /
Logprep metrics:       `localhost:8001`  /                         /
Opensearch:            `localhost:9200`  /                         /
Opensearch Dashboards: `localhost:5601`  /                         /
Grafana Dashboards:    `localhost:3000`  admin                     admin
Prometheus:            `localhost:9090`  /                         /
Nginx Basic Auth:      `localhost:8081`  user                      password
Nginx mTLS:            `localhost:8082`
Keycloak:              `localhost:8080`  admin                     admin
Keycloak Postgres:     `localhost:5432`  keycloak                  bitnami
FDA:                   `localhost:3002`  (configure via keycloak)  (configure via keycloak)
FDA Postgres:          `localhost:5432`  fda                       fda
UCL:                   `localhost:3001`  (configure via keycloak)  (configure via keycloak)
UCL Postgres:          `localhost:5432`  ucl                       ucl
====================== ================= ========================  =======================

The example rules that are used in the docker instance of Logprep can be found
in `examples/exampledata/rules`.
Example events that trigger for the example rules can be found in
`examples/exampledata/input_logdata/logclass/test_input.jsonl`.
These events can be added to Kafka with the following command:

.. code-block:: bash

  (docker exec -i kafka kafka-console-producer.sh --bootstrap-server 127.0.0.1:9092 --topic consumer) < exampledata/input_logdata/logclass/test_input.jsonl


Once the events have been processed for the first time, the new indices *processed*, *sre*
and *pseudonyms* should be available in Opensearch Dashboards.

The environment can be stopped via :code:`docker compose down`.


Utilizing FDA and UCL
---------------------

If you want to try out the FDA and UCL you first have to do some preparations.


0. Run the example compose setup with the :code:`oauth2` profile:

.. code-block:: bash

  docker compose --profile oauth2 up -d.


1. Sign into the keycloak admin panel and create a logprep user in the :code:`logprep` realm.
   Make sure that the user is part of the :code:`logprep-admin` group and has a password. If you
   choose a password other than :code:`logprep` you have to update the credentials file
   :code:`examples/exampledata/config/credentials.yml`, such that the password of
   :code:`http://localhost:3001` and :code:`http://localhost:3002` reflects your choice.
2. You have to login to the FDA with the previously created user and create a release, as well
   as your first logclass. It is also necessary to add an example event to this logclass in order
   to initialize the first mapping flow. The logclass and its mapping flow has to be available in
   order for logprep to load it's configuration.
3. If desired you can also create Use-Cases in the UCL. Similar to step two you have to sign in with
   your created logprep user and then configure required Use-Cases.
   At the current moment these configuration are not yet processed by logprep though, as the ucl
   only provides a mock endpoint which doesn't contain your Use-Case configurations.
4. Set the env and run logprep

  .. code-block:: bash

    export LOGPREP_CREDENTIALS_FILE="examples/exampledata/config/credentials.yml"
    logprep run examples/exampledata/config/pipeline.yml "http://localhost:3002/api/v1/pipelines?stage=prod&logclass=ExampleClass" "http://localhost:3001/api/v1/general-predetection"

Just consider that the first :code:`pipeline.yml` argument is used to define a proper :code:`input`
and :code:`output` as those are not part of the FDA/UCL output. Also, in the second argument
you should ensure that the :code:`stage` and :code:`loglcass` are set properly.

.. note::

     If you did use the example compose setup before and run into problems it is advised to first pull
     all images again to update them to the latest version:
     :code:`docker compose -f ./examples/compose/docker-compose.yml pull`.
