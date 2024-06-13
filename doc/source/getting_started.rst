===============
Getting Started
===============

Installation
============

Python should be present on the system. Currently, Python 3.10 - 3.12 are supported.
To install Logprep you have following options:

**1. Option:** Installation via PyPI:

This option is recommended if you just want to use the latest release of logprep.

..  code-block:: bash

    pip install logprep

To see if the installation was successful run :code:`logprep --version`.

**2. Option:** Installation via Git Repository:

This option is recommended if you are interested in the latest developments and might want to
contribute to them.

..  code-block:: bash

    git clone https://github.com/fkie-cad/Logprep.git
    cd Logprep
    pip install .

To see if the installation was successful run
:code:`logprep --version`.

**3. Option:** Installation via Github Release

This option is recommended if you just want to try out the latest developments.

..  code-block:: bash

    pip install git+https://github.com/fkie-cad/Logprep.git@latest

To see if the installation was successful run :code:`logprep --version`.

**4. Option:** Docker build

This option can be used to build a container image from a specific commit

..  code-block:: bash

    git clone https://github.com/fkie-cad/Logprep.git
    docker build -t logprep .

To see if the installation was successful run :code:`docker run logprep --version`.

Run Logprep
===========

If you have installed it via PyPI or the Github Development release just run:

..  code-block:: bash

    logprep run $CONFIG

Where :code:`$CONFIG` is the path to a configuration file.
For more information on running logprep with different configruation files or running
logprep with configruation from an api see the :ref:`configuration` section.

