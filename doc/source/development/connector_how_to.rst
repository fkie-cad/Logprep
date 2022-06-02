Implementing a new Connector
============================

Connectors are used to fetch and store log messages.

Basically, it consists of three components:

    * Input (:py:class:`~logprep.input.input.Input`)
    * Output (:py:class:`~logprep.output.output.Output`)
    * Factory to create connector instances

Basics
------

Inputs and outputs are viewed as independent by the pipeline.
Therefore, it is possible to receive messages from one system and to store them in another, i.e. reading from Kafka and writing to MongoDB.

A connector implementation can cover both inputs and outputs.
Here it must be noted that the methods `setup` and `shut_down` are being called multiple times (once for the input and once for the output).

The internal structure of the implementation is left to the developer.
However, the information below and in the corresponding base classes must be considered.

Input
-----

An input connector must implement the interface :py:class:`~logprep.input.input.Input`.
Please consider the doc strings within the interface!

:py:meth:`~logprep.input.input.Input.describe_endpoint`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This method gives a description of the connector.
It can be used to refer to the connector in an error messsage.
The return value should be a brief string like `Kafka: 127.0.0.1:1234`.

:py:meth:`~logprep.input.input.Input.get_next`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This method fetches new log messages, which must be returned as dictionaries.

The implementation can run in the background and it can fetch multiple log messages at once, but it can return only one log message per call of the method.
The other messages must be cached and returned with subsequent calls of `get_next`.

An exception should be thrown if an error occurs on calling this function.
These exceptions must inherit from the exception classes in :py:class:`~logprep.input.input.Input`.
They should return a helpful message when calling `str(exception)`.
Exceptions that require a restart of Logprep should inherit from `FatalInputError`.
Exceptions that inherit from `WarningInputError` will be logged, but they do not require any error handling.

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
Exceptions that inherit from `WarningOutputError` will be logged, but they do not require any error handling.

:py:meth:`~logprep.output.output.Output.store_failed`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This method is being called if an error occurred during the processing of a log message.
The original log message, the partially processed log message and the error message are being passed to this method.
These will be stored separately from regular log messages for debugging and error handling.


Factory
-------

The factory :py:class:`~logprep.connector.connector_factory.ConnectorFactory` reads the `type` field from connector configurations and calls the appropriate factory for the corresponding connector type.
New connector types have to be manually added to this factory.

For simple cases it might be enough to create a factory method directly in :py:class:`~logprep.connector.connector_factory.ConnectorFactory` (i.e. `dummy` with `DummyInput` and `DummyOutput`).
Generally, it is however better to create a separate factory for a connector so that `ConnectorFactory` just contains a call to that specific connector factory (i.e. `confluentkafka` with :py:class:`~logprep.connector.confluent_kafka.ConfluentKafkaFactory`).
Errors in the configuration must throw exceptions that are derived from `connector.ConnectorFactoryError.InvalidConfigurationError`.

The functionality of a factory should be checked with appropriate tests (`connector.test_ConnectorFactory`).
The configuration in the test serves simultaneously as reference for the configuration of connectors.
