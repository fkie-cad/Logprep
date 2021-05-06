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

Pipelines
=========

A pipeline consists of a sequence of multiple processing steps (processors).
The main idea is that each processor performs a simple task that is easy to carry out.

How are Pipelines Implemented?
------------------------------

This program generates a list of processors according to the configuration.
Each incoming event is being processed by these processors in the configured order.
The processors modify the event that is being `passed` through.
Thus, the order of the processors is relevant.

Multiple instances of pipelines are created and run in parallel by different processes.
Only one event at a time is processed by each processor.
Therefore, results of a processor should not depend on other events.


Processors
==========

A processor processes incoming log messages.
Its results can be used by following processors or they can be put out by a connector.

Labeler
-------

The labeler is a processor that analyzes log messages according to certain rules and then adds appropriate labels.

Normalizer
----------

The normalizer is a processor that normalizes log messages by copying certain fields to standardized fields.

Pseudonymizer
-------------

The pseudonymizer is a processor that pseudonymizes certain fields of log messages to ensure privacy regulations can be adhered to.
