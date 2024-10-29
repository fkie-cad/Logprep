Implementing a new Connector
============================


Connectors are used to fetch or store log messages.
Input and ouput connectors work each independently, with the exception that an output connector
might call a callback function inside the input, to notify that the current batch was sucessfully
processed. Only then the input would start collecting new inputs.
Because of this independence, it is possible to receive messages from one system and to store them
in another, i.e. reading from Kafka and writing to OpenSearch.

The internal structure of the connector implementation is left to the developer.
However, the information below and in the corresponding base classes must be considered.

Input
-----

An input connector must implement the interface :py:class:`~logprep.input.input.Input`.
Please consider the doc strings within the interface!

:py:meth:`~logprep.input.input.Input.describe`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This method gives a description of the connector.
It can be used to refer to the connector in an error messsage.
The return value should be a brief string like `ConfluentKafkaInput (name) - Kafka: 127.0.0.1:1234`.
A base description is already given in the generic interface :py:class:`~logprep.input.input.Input`
and should be extended by calling the :code:`super().describe()`.

:py:meth:`~logprep.input.input.Input.get_next`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This method fetches a new log message, which must be returned as dictionaries.

The implementation can run in the background and it can fetch multiple log messages at once, but it
can return only one log message per call of the method. The other messages must be cached and
returned with subsequent calls of `get_next`.

An exception should be thrown if an error occurs on calling this function.
These exceptions must inherit from the exception classes in :py:class:`~logprep.input.input.Input`.
They should return a helpful message when calling `str(exception)`.
Exceptions requiring Logprep to restart should inherit from `FatalInputError`.
Exceptions that inherit from `WarningInputError` will be logged, but they do not require any error
handling.

.. _connector_output:

Output
------

An output connector must implement the interface :py:class:`~logprep.output.output.Output`.
Please consider the doc strings within the interface!

:py:meth:`~logprep.output.output.Output.store`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This method is called to send log messages to a storage location.

An exception should be thrown if an error occurs on calling this function.
These exceptions must inherit from the exception classes in :py:class:`~logprep.output.output.Output`.
They should return a helpful message when calling `str(exception)`.
Analogous to the input, exceptions that require a restart of Logprep should inherit from `FatalOutputError`.
Exceptions that inherit from `OutputWarning` will be logged, but they do not require any error handling.


.. _error_output:

Error Output
------------

Error output is setup in :py:class:`~logprep.framework.pipeline_manager.PipelineManager`. The error
output connector is instantiated and setup only once during the initialization of the pipeline manager
together with :py:class:`~logprep.framework.pipeline_manager.OutputQueueListener`.
The listener is used to listen on the populated error queue and to send the log messages to the
:code:`store` method of the error output connector.
The error queue is given to the listener and to all pipelines instantiated by the pipeline manager.


Factory
-------

The :py:class:`~logprep.factory.Factory` reads the `type` field from components configurations,
retrieves the corresponding component class from the :py:class:`~logprep.registry.Registry` and
creates a proper object.


The functionality of a factory should be checked with appropriate tests (`connector.test_ConnectorFactory`).
The configuration in the test serves simultaneously as reference for the configuration of connectors.
