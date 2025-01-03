============
Installation
============

PIP
===

Python should be present on the system. Currently, Python 3.11 - 3.13 are supported.
To install Logprep you have following options:

**1. Option:** latest stable release

This option is recommended if you just want to use the latest release of logprep.

..  code-block:: bash

    pip install logprep

To see if the installation was successful run :code:`logprep --version`.

**2. Option:** latest development release

This option is recommended if you just want to try out the latest developments.

..  code-block:: bash

    pip install git+https://github.com/fkie-cad/Logprep.git@latest

To see if the installation was successful run :code:`logprep --version`.


GIT
===

This option is recommended if you are interested in the latest developments and might want to
contribute to them.

..  code-block:: bash

    git clone https://github.com/fkie-cad/Logprep.git
    cd Logprep
    pip install .

To see if the installation was successful run
:code:`logprep --version`.

Docker
======

This option can be used to build a container image from a specific commit

..  code-block:: bash

    git clone https://github.com/fkie-cad/Logprep.git
    docker build -t logprep .

To see if the installation was successful run :code:`docker run logprep --version`.

Helm
====

This option can be used to deploy logprep on a kubernetes cluster.

At first you have to install the prometheus PodMonitor CRD:

.. code-block:: bash
    :caption: Install the prometheus PodMonitor CRD

    kubectl apply -f https://raw.githubusercontent.com/prometheus-community/helm-charts/main/charts/kube-prometheus-stack/charts/crds/crds/crd-podmonitors.yaml


To install latest stable release:

..  code-block:: bash

   helm repo add logprep https://fkie-cad.github.io/Logprep
   helm install logprep logprep/logprep


To install from cloned github repository:

..  code-block:: bash

   git clone https://github.com/fkie-cad/Logprep.git
   cd Logprep
   helm install logprep charts/logprep
