============
Installation
============

UV
==

Python should be present on the system. Currently, Python 3.11 – 3.14 are supported.

Logprep can be installed with **uv**, a fast drop-in replacement for pip.
Using uv is optional – Logprep can still be installed with regular pip as well.

We recommend using **uv**, because uv uses a lock file during installation.
This ensures that Logprep is installed with the *exact same dependency versions*
that are used and tested during development, providing more reproducible and stable installations.

If you want to install uv, refer to the official installation guide:

https://docs.astral.sh/uv/getting-started/installation/#installing-uv

To install Logprep you have the following options:

**1. Option:** latest stable release

This option is recommended if you just want to use the latest stable release of Logprep.

.. code-block:: bash

    uv sync

To see if the installation was successful run :code:`logprep --version`.

**2. Option:** latest development release

This option is recommended if you want to try out the latest developments.

.. code-block:: bash

    uv pip install git+https://github.com/fkie-cad/Logprep.git@latest

To see if the installation was successful run :code:`logprep --version`.

GIT
===

This option is recommended if you are interested in the latest developments and might want to
contribute to them.

..  code-block:: bash

    git clone https://github.com/fkie-cad/Logprep.git
    cd Logprep
    uv sync
    uv sync --extra dev # if you intend to contribute

To see if the installation was successful run
:code:`logprep --version`.

Docker
======

This option can be used to build a container image from a specific commit

..  code-block:: bash

    git clone https://github.com/fkie-cad/Logprep.git
    docker build -t logprep .

To see if the installation was successful run :code:`docker run logprep --version`.

**Note:**
The provided Dockerfile uses **Python 3.11** by default via the :code:`PYTHON_VERSION` build argument.
If you want to build Logprep with another supported Python version, override the value during build:

..  code-block:: bash

    docker build --build-arg PYTHON_VERSION=3.13 -t logprep .

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
