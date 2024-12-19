Start Logprep programaticly
===========================

It is possible to make use of the Logprep pipeline in plain python, without any
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
                    "rules": [
                        "examples/exampledata/rules/pre_detector/rules"
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
                    "rules": [
                        "examples/exampledata/rules/pre_detector/rules"
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
