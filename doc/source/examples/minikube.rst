Kubernetes Example Deployment
=============================

For this example, we need a working kubernetes cluster. In this example we will use minikube
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

    curl -Lo /usr/local/bin/kubectl \
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
    minikube start

Deploy the example
------------------


