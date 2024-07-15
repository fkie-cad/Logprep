============
Installation
============

PIP
===

Python should be present on the system. Currently, Python 3.10 - 3.12 are supported.
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

..  code-block:: bash

   helm repo add logprep https://fkie-cad.github.io/Logprep
   helm install logprep logprep/logprep   
