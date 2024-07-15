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

    sudo apt-get install -y \
        apt-transport-https \
        ca-certificates \
        curl \
        software-properties-common

.. code-block:: bash
    :caption: Install minikube

    sudo curl -Lo /usr/local/bin/minikube \
      https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
    
    sudo chmod +x /usr/local/bin/minikube

.. code-block:: bash
    :caption: Install kubectl

    sudo curl -Lo /usr/local/bin/kubectl \
      "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"

    sudo chmod +x /usr/local/bin/kubectl

.. code-block:: bash
    :caption: Install helm

    wget https://get.helm.sh/helm-v3.15.1-linux-amd64.tar.gz
    tar xzvf helm-v3.15.1-linux-amd64.tar.gz
    sudo mv linux-amd64/helm /usr/local/bin/helm
    sudo chmod +x /usr/local/bin/helm

.. code-block:: bash
    :caption: Configure and start minikube
    
    minikube config set driver docker
    minikube config set cpus 16 
    minikube config set memory 16GB
    minikube start

Deploy the example
------------------

At first you have to install the prometheus PodMonitor CRD:

.. code-block:: bash
    :caption: Install the prometheus PodMonitor CRD

    kubectl apply -f https://raw.githubusercontent.com/prometheus-community/helm-charts/main/charts/kube-prometheus-stack/charts/crds/crds/crd-podmonitors.yaml


Then you have to update and build the helm subcharts repository:

.. code-block:: bash
    :caption: Add the bitnami helm repository

    helm dependencies update ./examples/k8s
    helm dependencies build ./examples/k8s

Then install istio (for details see: `https://istio.io/latest/docs/setup/install/helm/`_. ):

.. code-block:: bash
    :caption: Create the istio-system namespace

    kubectl create namespace istio-system

.. code-block:: bash
    :caption: Install istio

    helm repo add istio https://istio-release.storage.googleapis.com/charts
    helm repo update
    helm install istio-base istio/base -n istio-system --set defaultRevision=opensiem --wait
    helm install istiod istio/istiod -n istio-system --wait


.. code-block:: bash
    :caption: Install istio ingress gateway

    kubectl create namespace istio-ingress
    helm install istio-ingress istio/gateway -n istio-ingress

.. code-block:: bash
    :caption: Verifiy the istio installation

    ❯ helm ls -n istio-system                      
    NAME            NAMESPACE       REVISION        UPDATED                                         STATUS          CHART           APP VERSION
    istio-base      istio-system    1               2024-07-15 14:54:54.029747408 +0200 CEST        deployed        base-1.22.2     1.22.2     
    istiod          istio-system    1               2024-07-15 14:57:41.496783572 +0200 CEST        deployed        istiod-1.22.2   1.22.2   

    ❯ kubectl get deployments -n istio-system --output wide
    NAME     READY   UP-TO-DATE   AVAILABLE   AGE   CONTAINERS   IMAGES                         SELECTOR
    istiod   1/1     1            1           24m   discovery    docker.io/istio/pilot:1.22.2   istio=pilot

    ❯ kubectl get pods -n istio-ingress          
    NAME                             READY   STATUS    RESTARTS   AGE
    istio-ingress-7f5f6f58b8-sv6gk   1/1     Running   0          16m

Next you can install the opensiem example using:

.. code-block:: bash
    :caption: Install opensiem

    helm install opensiem examples/k8s
