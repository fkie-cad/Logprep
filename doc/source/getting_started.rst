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

Depending on how you have installed Logprep you have different choices to run Logprep as well.
If you have installed it via PyPI or the Github Development release just run:

..  code-block:: bash

    logprep run $CONFIG

Where :code:`$CONFIG` is the path to a configuration file.
For more information see the :ref:`configuration` section.

Integrate Logprep in Python
===========================

It is possible to make use of the Logprep :ref:`pipeline_config` in plain python, without any
input or output connectors or further configurations.
If on the other hand you want to make use of the input connector preprocessors you have to at least
use an input connector like the DummyInput.
The integration in python

An example with input connector and preprocessors could look like this:

.. code-block:: python

    from logprep.framework.pipeline import Pipeline

    event = {
        "some": "data",
        "test_pre_detector": "bad_information"
    }
    config = {
        "pipeline": [
            {
                "predetector": {
                    "type": "pre_detector",
                    "specific_rules": [
                        "quickstart/exampledata/rules/pre_detector/specific"
                    ],
                    "generic_rules": [
                        "quickstart/exampledata/rules/pre_detector/generic"
                    ],
                    "pre_detector_topic": "output_topic"
                }
            }
        ],
        "input": {
            "my_input":{
                "type": "dummy_input",
                "documents": [event],
                "preprocessing": {
                    "log_arrival_time_target_field": "arrival_time"
                }
            }
        }
    }
    pipeline = Pipeline(config=config)
    extra_outputs = pipeline.process_pipeline()

An example without input connector and preprocessors could look like this:

.. code-block:: python

    from logprep.framework.pipeline import Pipeline

    event = {
        "some": "data",
        "test_pre_detector": "bad_information"
    }
    config = {
        "pipeline": [
            {
                "predetector": {
                    "type": "pre_detector",
                    "specific_rules": [
                        "quickstart/exampledata/rules/pre_detector/specific"
                    ],
                    "generic_rules": [
                        "quickstart/exampledata/rules/pre_detector/generic"
                    ],
                    "pre_detector_topic": "output_topic"
                }
            }
        ],
    }
    pipeline = Pipeline(config=config)
    extra_outputs = pipeline.process_event(event)


.. hint::

    To make use of preprocessors call :code:`pipeline.process_pipeline()`.
    Calling the respective method multiple times will result in iterating through the list of input
    events.
    To call the pipeline without input connector call :code:`pipeline.process_event(event)`.


.. warning::

    When using the pipeline like this Logprep does not store any events or errors in an
    designated output.
    All relevant information are returned to the user and have to be taken care of the user
    themself.
