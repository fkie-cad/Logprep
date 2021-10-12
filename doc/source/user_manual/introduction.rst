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

Generic Adder
-------------

The generic adder is a processor that adds new fields and values to documents based on a list.
The list can reside inside a rule or inside a file.

Datetime Extractor
------------------

The datetime extractor is a processor that can extract timestamps from a field and split it into its parts.

Domain Resolver
---------------

The domain resolver is a processor that can resolve domains inside a defined field.

GeoIP Enricher
--------------

The geoip enricher is a processor that can add geoip data to an event based on an IP field.


Template Replacer
------------------------

The template replacer is a processor that can replace parts of a text field to anonymize those parts.
The replacement is based on a template file.

Generic Resolver
----------------

The generic resolver is a processor that can resolve fields by using a map of resolve patterns and resolve values.
The map can be defined within rules or within a file.

Pseudonymizer
-------------

The pseudonymizer is a processor that pseudonymizes certain fields of log messages to ensure privacy regulations can be adhered to.

Clusterer
---------

The clusterer is a processor that uses heuristics to group unstructured and semi-structured log messages (especially Unix logs like Syslogs).

Dropper
-------

The Dropper is a processor that removes fields from log messages.
Which fields are deleted is determined within each rule.

Predetector
-----------

The Predetector is a processor that creates alerts for matching events.
It adds MITRE ATT&CK data to the alerts.
