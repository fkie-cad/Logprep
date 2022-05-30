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

.. _intro_domain_label_extractor:

Domain Label Extractor
----------------------

The domain label extractor is a processor that splits a domain into it's corresponding labels like
:code:`registered_domain`, :code:`top_level_domain` and :code:`subdomain`. If instead an IP is given in the target field
an informational tag is added to the configured tags field. If neither a domain nor an ip address can be recognized an
invalid error tag will be be added to the tag field in the event. The added tags contain each the target field name that
was checked by the configured rule, such that it is possible to distinguish between different domain fields in one
event. For example for the target field :code:`url.domain` following tags could be added:
:code:`invalid_domain_in_url_domain` and :code:`ip_in_url_domain`

List Comparison Enricher
------------------------

The list comparison enricher is a processor that allows to compare values of a target field against lists provided
as files.

Selective Extractor
-------------------

The selective extractor is a processor that allows to write field values of a given log message to a different Kafka
topic. The output topic is configured via the pipeline yml, while the fields to be extracted are specified by means of
a list which is also specified in the pipeline configuration as a file path. This processor is applied to all messages,
because of that it does not need further rules to specify it's behavior.

Geoip Enricher
--------------

The geoip enricher is a processor that can add geoip data to an event based on an IP field.


Template Replacer
-----------------

The template replacer is a processor that can replace parts of a text field to anonymize those parts.
The replacement is based on a template file.

Generic Resolver
----------------

The generic resolver is a processor that can resolve fields by using a map of resolve patterns and resolve values.
The map can be defined within rules or within a file.

Hyperscan Resolver
------------------

The hyperscan resolver is a processor that can resolve fields by using a map of resolve patterns and resolve values.
The map can be defined within rules or within a file.
It uses hyperscan to speedup the pattern matching.

.. WARNING::
   The hyperscan resolver is only supported for x86_64 linux with python version 3.6-3.8.

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
