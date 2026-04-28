============
Installation
============

PyPI
====

This option is recommended for using logprep as a library to build upon

.. code-block:: bash

    pip install logprep

To see if the installation was successful run :code:`logprep --version`.

Container Image
===============

This option is recommended for Users just wanting to run logprep without the hassle of compiling.
We provide a number of pre compiled Images for all officially supported python versions.
A list of every image can be found here https://github.com/fkie-cad/Logprep/pkgs/container/logprep/versions?filters%5Bversion_type%5D=tagged.

To install a specific version the general structure of our tags follows this example:

logprep:py{PYTHON_VERSION}-v{LOGPREP_VERSION}

Python 3.11 with version 19.0.0 would be called:

logprep:py3.11-v19.0.0

To download (pull) these images an OCI compliant puller (like docker) can be used like this

.. code-block:: bash

   docker pull ghcr.io/fkie-cad/logprep:py3.11-v19.0.0

To verify that the installation works you can run

.. code-block:: bash

   docker run ghcr.io/fkie-cad/logprep:py3.11-v19.0.0 --version


Helm
====

This option can be used to deploy logprep on a kubernetes cluster.

At first you have to install the prometheus PodMonitor CRD:

.. code-block:: bash
    :caption: Install the prometheus PodMonitor CRD

    kubectl apply -f https://raw.githubusercontent.com/prometheus-community/helm-charts/main/charts/kube-prometheus-stack/charts/crds/crds/crd-podmonitors.yaml


To install latest stable release:

.. code-block:: bash

   helm repo add logprep https://fkie-cad.github.io/Logprep
   helm install logprep logprep/logprep


To install from cloned github repository:

.. code-block:: bash

   git clone https://github.com/fkie-cad/Logprep.git
   cd Logprep
   helm install logprep charts/logprep

GIT
===

This option is recommended if you are interested in the latest developments and might want to
contribute to them.

UV
--
Python should be present on the system. Currently, **Python 3.11 – 3.14** are supported.

We recommend using **uv**, because uv uses a lock file during installation.
This ensures that Logprep is installed with the *exact same dependency versions*
that are used and tested during development, providing more reproducible and stable installations.

If you want to install uv, refer to the official installation guide:

https://docs.astral.sh/uv/getting-started/installation/#installing-uv

To install Logprep with uv:

.. code-block:: bash

    git clone https://github.com/fkie-cad/Logprep.git
    cd Logprep
    uv sync --frozen
    uv sync --frozen --extra dev # if you intend to contribute

To see if the installation was successful run
:code:`logprep --version`.

Nix Flake
---------
`Nix` is a package manager that creates isolated, reproducible environments.
With `flakes`, dependencies and development environments are defined in a
declarative way, ensuring that all contributors use the exact same setup
without manual dependency management.

We recommend using this method if you are already familiar with Nix or want a
fully reproducible development environment. However, it requires installing Nix
and may introduce a learning curve for new users.

Flakes are still marked as experimental, so depending on your Nix installation,
you may need to enable them by following this guide:

https://wiki.nixos.org/wiki/Flakes#Nix_standalone

To start developing with Nix:

.. code-block:: bash

   git clone https://github.com/fkie-cad/Logprep.git
   cd Logprep
   nix develop

To see if the installation was successful run
:code:`logprep --version`.
