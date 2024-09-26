Kubernetes Example Deployment
=============================

For this example, we need a working kubernetes cluster. Here we will use minikube,
but every other kubernetes environment should do the job.

Setup Minikube
--------------

To install :code:`minikube`, :code:`helm` and :code:`kubectl` follow the instructions below.

If you have docker already installed, you can install the needed components and start minikube
with the following commands:

.. code-block:: bash
    :caption: Install package prerequisites

    sudo apt-get install -y apt-transport-https ca-certificates  curl software-properties-common

.. code-block:: bash
    :caption: Install minikube

    sudo curl -Lo /usr/local/bin/minikube https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
    
    sudo chmod +x /usr/local/bin/minikube

.. code-block:: bash
    :caption: Install kubectl

    sudo curl -Lo /usr/local/bin/kubectl "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"

    sudo chmod +x /usr/local/bin/kubectl

.. code-block:: bash
    :caption: Install helm

    wget https://get.helm.sh/helm-v3.15.1-linux-amd64.tar.gz
    tar xzvf helm-v3.15.1-linux-amd64.tar.gz
    sudo mv linux-amd64/helm /usr/local/bin/helm
    sudo chmod +x /usr/local/bin/helm

.. code-block:: bash
    :caption: add helm repositories

    helm repo add bitnami https://charts.bitnami.com/bitnami

.. code-block:: bash
    :caption: Configure and start minikube
    
    minikube config set driver docker
    minikube config set cpus 16 
    minikube config set memory 16GB
    minikube start
    minikube addons enable ingress

Deploy the example
------------------

The following steps install the actual opensiem example on the minikube cluster.
It will install 

At first you have to install the prometheus PodMonitor CRD:

.. code-block:: bash
    :caption: Install the prometheus PodMonitor CRD

    kubectl apply -f https://raw.githubusercontent.com/prometheus-community/helm-charts/main/charts/kube-prometheus-stack/charts/crds/crds/crd-podmonitors.yaml


Then you have to update and build the helm subcharts repository:

.. code-block:: bash
    :caption: Add the bitnami helm repository

    helm dependencies update ./examples/k8s
    helm dependencies build ./examples/k8s

Next you are ready to install the opensiem example using:

.. code-block:: bash
    :caption: Install opensiem

    helm install opensiem examples/k8s

Make the cluster locally resolvable:

.. code-block:: bash
    :caption: add hosts entry to resolve the cluster

    echo "$( minikube ip ) connector.opensiem dashboards.opensiem grafana.opensiem" | sudo tee -a /etc/hosts

Test the defined ingresses:

.. code-block:: bash
    :caption: Test the opensiem example ingress

    curl -v http://connector.opensiem/health
    curl -v http://dashboards.opensiem

Test the opensiem connector:

.. code-block:: bash
    :caption: Test the opensiem example connector

    ❯ logprep generate http --input-dir ./examples/exampledata/input_logdata/ --target-url http://connector.opensiem --events 100 --batch-size 10
    
    2024-07-17 11:15:35 301643 Generator  INFO    : Log level set to 'NOTSET'
    2024-07-17 11:15:35 301643 Generator  INFO    : Started Data Processing
    2024-07-17 11:15:35 301643 Input      INFO    : Reading input dataset and creating temporary event collections in: '/tmp/logprep_a51e1vh6'
    2024-07-17 11:15:35 301643 Input      INFO    : Preparing data took: 0.0042 seconds
    2024-07-17 11:15:35 301643 Input      INFO    : Cleaned up temp dir: '/tmp/logprep_a51e1vh6'
    2024-07-17 11:15:35 301643 Generator  INFO    : Completed with following statistics: {
        "Number of failed events": 0,
        "Number of successfull events": 100,
        "Requests Connection Errors": 0,
        "Requests Timeouts": 0,
        "Requests http status 200": 10,
        "Requests total": 10
    }
    2024-07-17 11:15:35 301643 Generator  INFO    : Execution time: 0.067013 seconds

open your browser and go to `opensearch dashboard <http://dashboards.opensiem>`_ to see the generated data in the opensearch dashboards.


Use local container images
--------------------------

If you want to use local logprep container images, you can build the images with the following commands:

.. code-block:: bash
    :caption: switch docker context to minikube in bash

    eval $(minikube docker-env)

for powershell:

.. code-block:: powershell
    :caption: switch docker context to minikube in powershell

    (minikube docker-env).replace("export ", '$env:') | out-string | Invoke-Expression

Then build the logprep image with the following command:

.. code-block:: bash
    :caption: build this image using the Dockerfile in the root of the repository

    docker buildx build -t local/logprep:latest --build-arg PYTHON_VERSION=3.11 --build-arg LOGPREP_VERSION=dev .

Then install the opensiem example using the local logprep image:

.. code-block:: bash
    :caption: use the local values file to deploy the opensiem example

    helm install opensiem examples/k8s --values examples/k8s/values-dev.yaml
