============
Architecture
============

Overview
========

Logprep is designed to receive, process and forward log messages.
It consists of several interconnected components that work together to make this possible.

.. raw:: html
   :file: ../../development/architecture/diagramms/overview.drawio.html


Starting Logprep
================

The following diagramm shows the starting behaviour of Logprep. 

.. raw:: html
   :file: ../../development/architecture/diagramms/logprep_start.drawio.html


Pipeline Manager
================

This diagram shows the creation of Multiprocessing Pipelines and the shutdown of failed Pipelines.

.. raw:: html
   :file: ../../development/architecture/diagramms/pipelineManager.drawio.html


Pipeline
========
This diagram shows the flow of the Pipeline. The starting-point is the creating of the 
PipelineManager and therefore the start of the MultiprocessingPipeline.

.. raw:: html
   :file: ../../development/architecture/diagramms/pipeline.drawio.html


Input
=====

In this diagram, some parts are specific for the ConfluentKafkaInput Connector.
These was deemed to be important enough to be part of the diagram.

.. raw:: html
   :file: ../../development/architecture/diagramms/input.drawio.html


Processor
=========

Below is a visualization of all available processors of Logprep. 
These diagrams also show which processors inherit from what. 
The first of these diagrams describes the process up to the 
actual application of the rule that is implemented in the respective processors.

.. raw:: html
   :file: ../../development/architecture/diagramms/process-Combined.drawio.html


Ruletree
========

The Ruletree diagramm shows how the matching rules for a given event are searched for and found.

.. raw:: html
   :file: ../../development/architecture/diagramms/ruleTree.drawio.html


Output
======

In this diagram, the last part about the backlog is specific for the Opensearch Output.
This was deemed to be important enough to be part of the diagram.

.. raw:: html
   :file: ../../development/architecture/diagramms/output.drawio.html


Event flow
==========

The following diagrams illustrate the flow of a single event to make it more comprehensible.

.. raw:: html
   :file: ../../development/architecture/diagramms/event_flow.drawio.html


.. raw:: html
   :file: ../../development/architecture/diagramms/event.drawio.html


Multiprocessing
===============

This diagram shows what ressources are shared within the multiprocessing processes and how the
processes are started and stopped.

.. raw:: html
   :file: ../../development/architecture/diagramms/multiprocessing.drawio.html

Legend
======

.. raw:: html
   :file: ../../development/architecture/diagramms/legend.drawio.html
