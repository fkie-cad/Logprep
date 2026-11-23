Kubernetes Example Deployment
=============================

This example deploys an opensiem on a local kubernetes cluster with helm:

* a kafka cluster with the topics for the example (``examples/k8s/templates/kafka.yml``)
* opensearch and opensearch dashboards (official opensearch helm charts)
* a logprep ``connector``, which accepts events via http and writes them to kafka
* a ``logprep`` instance, which reads the events from kafka and writes them to opensearch

We use minikube here, every other kubernetes environment should do the job as well.
You need :code:`minikube`, :code:`kubectl` and :code:`helm`, see the installation guides of
`minikube <https://minikube.sigs.k8s.io/docs/start/>`_,
`kubectl <https://kubernetes.io/docs/tasks/tools/>`_ and
`helm <https://helm.sh/docs/intro/install/>`_.
The cluster needs about 8 CPUs and 16 GB of memory.


Start Minikube
--------------

Minikube runs the cluster in a container, with docker or podman on Linux and MacOS:

.. tab-set::
    :sync-group: engine

    .. tab-item:: Docker
        :sync: docker

        On MacOS, give Docker Desktop at least as many CPUs and more memory than the cluster
        (Settings, Resources).

        .. code-block:: bash

            minikube config set driver docker

    .. tab-item:: Podman
        :sync: podman

        Minikube needs rootful podman. On MacOS, configure the podman machine with more
        memory than the cluster:

        .. code-block:: bash

            podman machine stop
            podman machine set --rootful --cpus 8 --memory 20480
            podman machine start

        On Linux, minikube runs :code:`sudo -n podman`, which requires passwordless sudo for
        podman, see the `podman driver <https://minikube.sigs.k8s.io/docs/drivers/podman/>`_.

        .. code-block:: bash

            minikube config set driver podman

.. code-block:: bash

    minikube config set container-runtime containerd
    minikube config set cpus 8
    minikube config set memory 16GB
    minikube start

If minikube fails with :code:`no container with name or ID "minikube" found`, a previous cluster
is gone, remove it with :code:`minikube delete` and start again.

Enable the ingress controller and wait until it is ready, otherwise installing the example fails
with :code:`failed calling webhook "validate.nginx.ingress.kubernetes.io"`:

.. code-block:: bash

    minikube addons enable ingress
    kubectl wait --namespace ingress-nginx --for=condition=ready pod \
        --selector=app.kubernetes.io/component=controller --timeout=180s


Prepare the Example
-------------------

The logprep chart deploys a prometheus :code:`PodMonitor`, which needs its custom resource
definition in the cluster:

.. code-block:: bash

    kubectl apply -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/v0.94.2/example/prometheus-operator-crd/monitoring.coreos.com_podmonitors.yaml

Fetch the subcharts, from the root of the repository:

.. code-block:: bash

    helm repo add opensearch https://opensearch-project.github.io/helm-charts/
    helm dependency update ./examples/k8s


Build a Local Image (optional)
------------------------------

Only needed to run logprep from your working copy, skip it to use the latest release.
The image has to match the cluster: linux, on the architecture of your container engine.
Building it with nix in a linux container takes care of both, on any host.
Then tag it as :code:`examples/k8s/values-dev.yaml` expects and load it into the cluster.

.. tab-set::
    :sync-group: engine

    .. tab-item:: Docker
        :sync: docker

        .. code-block:: bash

            docker run --rm -v "$PWD":/src:ro -w /src docker.io/nixos/nix sh -c \
                'cat $(nix --extra-experimental-features "nix-command flakes" build \
                "path:.#packages.$(uname -m)-linux.docker.python311" --no-link --print-out-paths)' \
                > /tmp/logprep-image.tar.gz
            docker load < /tmp/logprep-image.tar.gz
            docker tag logprep:py3.11 local/logprep:latest
            docker save -o /tmp/logprep.tar local/logprep:latest
            minikube image load /tmp/logprep.tar

    .. tab-item:: Podman
        :sync: podman

        .. code-block:: bash

            podman run --rm -v "$PWD":/src:ro -w /src docker.io/nixos/nix sh -c \
                'cat $(nix --extra-experimental-features "nix-command flakes" build \
                "path:.#packages.$(uname -m)-linux.docker.python311" --no-link --print-out-paths)' \
                > /tmp/logprep-image.tar.gz
            podman load < /tmp/logprep-image.tar.gz
            podman tag logprep:py3.11 docker.io/local/logprep:latest
            podman save -o /tmp/logprep.tar docker.io/local/logprep:latest
            minikube image load /tmp/logprep.tar

        Podman needs the full name :code:`docker.io/local/logprep:latest`, a short
        :code:`local/logprep:latest` becomes :code:`localhost/local/logprep:latest`, which
        the cluster does not find.

With nix on a linux host, building directly is faster, e.g.
:code:`nix build .#packages.x86_64-linux.docker.python311 -o image`.
A plain :code:`nix build .#docker.python311` on MacOS builds for MacOS, which fails in the
cluster with :code:`exec format error`.
To try the dev values without building, pull a released image, e.g.
:code:`ghcr.io/fkie-cad/logprep:py3.11-latest`, and tag, save and load it the same way
instead of :code:`logprep:py3.11`.


Install the Example
-------------------

.. tab-set::
    :sync-group: image

    .. tab-item:: Released image
        :sync: release

        Pulls the latest release of logprep from :code:`ghcr.io/fkie-cad/logprep`:

        .. code-block:: bash

            helm install opensiem examples/k8s

    .. tab-item:: Local image
        :sync: local

        Uses the image built above and smaller settings for a local cluster:

        .. code-block:: bash

            helm install opensiem examples/k8s --values examples/k8s/values-dev.yaml

Wait until everything is running, this takes a few minutes:

.. code-block:: bash

    kubectl wait --for=condition=ready pod --all --timeout=15m
    kubectl get pods

Logprep restarts a few times until kafka and opensearch are ready, that is expected.
To change the configuration later, use :code:`helm upgrade` with the same arguments as
:code:`helm install`, or start over with :code:`helm uninstall opensiem`.


Send Events
-----------

Forward the ports of the connector and opensearch in the background:

.. code-block:: bash

    kubectl port-forward svc/opensiem-connector-http-input 9000:9000 > /dev/null &
    kubectl port-forward svc/opensiem-opensearch 9200:9200 > /dev/null &

Send the example events to the connector:

.. code-block:: bash

    curl --data-binary @examples/exampledata/input_logdata/logclass/test_input.jsonl \
        http://localhost:9000/lab/123/ABC/auditlog

Logprep writes them to opensearch within about a minute:

.. code-block:: bash

    curl -s http://localhost:9200/processed/_count

With logprep installed locally, :code:`logprep generate http` sends larger amounts of events:

.. code-block:: bash

    logprep generate http --input-dir ./examples/exampledata/input_logdata/ \
        --target-url http://localhost:9000 --events 100 --batch-size 10

Stop the port forwarding when you are done:

.. code-block:: bash

    kill %1 %2


Use the Ingress
---------------

The example also exposes the connector and opensearch dashboards via ingress.
Make the host names resolvable:

.. tab-set::
    :sync-group: os

    .. tab-item:: Linux
        :sync: linux

        .. code-block:: bash

            echo "$(minikube ip) connector.opensiem dashboards.opensiem" | sudo tee -a /etc/hosts

    .. tab-item:: MacOS
        :sync: macos

        The cluster's network is not reachable from MacOS, :code:`minikube tunnel` forwards
        the ingress to localhost:

        .. code-block:: bash

            echo "127.0.0.1 connector.opensiem dashboards.opensiem" | sudo tee -a /etc/hosts

        Then run :code:`minikube tunnel` in a separate terminal, it asks for your sudo password
        and has to keep running.

Then the connector is available at :code:`http://connector.opensiem` and opensearch dashboards
at `http://dashboards.opensiem <http://dashboards.opensiem>`_:

.. code-block:: bash

    curl -v http://connector.opensiem/health
