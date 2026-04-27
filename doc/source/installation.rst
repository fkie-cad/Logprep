============
Installation
============

PyPI
====
.. code-block:: bash

    pip install logprep

To see if the installation was successful run :code:`logprep --version`.

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
Flakes are theoretically experimental so depending on which nix installer you used,
you might have to follow this short guide:

https://wiki.nixos.org/wiki/Flakes#Nix_standalone

After that, you should be able to run the following code and just start developing.

.. code-block:: bash

   git clone https://github.com/fkie-cad/Logprep.git
   cd Logprep
   nix develop

To see if the installation was successful run
:code:`logprep --version`.

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
