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

How are Pipelines Implemented?
------------------------------

This program generates a list of processors according to the configuration.
Each incoming event is being processed by these processors in the configured order.
The processors modify the event that is being `passed` through.
Thus, the order of the processors is relevant.

Multiple instances of pipelines are created and run in parallel by different processes.
Only one event at a time is processed by each processor.
Therefore, results of a processor should not depend on other events.

.. mermaid::

   flowchart LR
   A[Input\nConnector] --> B
   A[Input\nConnector] --> C
   A[Input\nConnector] --> D
   subgraph Pipeline 1
   B[Dissector] --> E[Geo-IP Enricher]
   E --> F[Dropper] 
   end
   subgraph Pipeline 2
   C[Dissector] --> G[Geo-IP Enricher]
   G --> H[Dropper] 
   end
   subgraph Pipeline n
   D[Dissector] --> I[Geo-IP Enricher]
   I --> J[Dropper] 
   end
   F --> K[Output\nConnector]
   H --> K[Output\nConnector]
   J --> K[Output\nConnector]

Processors
==========

.. autosummary::
   
   logprep.processor.clusterer.processor
   logprep.processor.datetime_extractor.processor
   logprep.processor.deleter.processor
   logprep.processor.domain_label_extractor.processor
   logprep.processor.domain_resolver.processor
   logprep.processor.dropper.processor
   logprep.processor.generic_adder.processor
   logprep.processor.generic_resolver.processor
   logprep.processor.geoip_enricher.processor
   logprep.processor.labeler.processor
   logprep.processor.list_comparison.processor
   logprep.processor.pre_detector.processor
   logprep.processor.pseudonymizer.processor
   logprep.processor.selective_extractor.processor
   logprep.processor.template_replacer.processor
   logprep.processor.hyperscan_resolver.processor
