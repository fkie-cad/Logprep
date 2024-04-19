============
Introduction
============

Logprep allows to collect, process and forward log messages from different data sources.
Data sources are connected via so called `Connectors`.
A sequence of `Processors` in a `Pipeline` processes the log messages step-by-step.
Logprep is designed so that new `Connectors` and `Processors` can be integrated (see :doc:`../development/index`).

Connectors
==========

Connectors allow reading and writing log messages.
They are connecting pipelines to the rest of the system.
Basically, different types of connections can be chosen via the parameter `type`.
Currently, only `confluentkafka`, which connects Logprep with Kafka, should be used in production.


.. _pipelines:

Pipelines
=========

A pipeline consists of a sequence of multiple processing steps (processors).
The main idea is that each processor performs a simple task that is easy to carry out.

Each incoming event is being processed by these processors in the configured order.
The processors modify the event that is being `passed` through.
Thus, the order of the processors is relevant.

Multiple instances of pipelines are created and run in parallel by different processes.
Only one event at a time is processed by each processor.
Therefore, results of a processor should not depend on other events.


Processors
==========

A list of all available processors can be found under the configuration section :ref:`processors`.
