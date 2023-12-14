============
Architecture
============

Overview
========

Logprep is designed to receive, process and forward log messages.
It consists of several interconnected components that work together to make this possible.
The following diagramm shows how Logprep behaves at the start. 

.. raw:: html
   :file: ../../development/architecture/diagramms/logprep_start.drawio.html


Pipeline
========
This diagram shows the flow of the Pipeline. The starting-point is the creating of the PipelineManager and therefore thr start oft the MultiprocessingPipeline.

.. raw:: html
   :file: ../../development/architecture/diagramms/pipeline.drawio.html

Input
=====

.. raw:: html
   :file: /home/vagrant/external_work/Logprep/doc/source/development/architecture/diagramms/input.drawio.html



Processor
=========

Below is a visualization of all available processors of Logprep. These diagrams also show which processors inherit from what. 
The first of these diagrams describes the process up to the actual application of the rule that is implemented in the respective processors.

.. raw:: html
   :file: /home/vagrant/external_work/Logprep/doc/source/development/architecture/diagramms/process-Combined.drawio.html


Ruletree
========

.. raw:: html
   :file: /home/vagrant/external_work/Logprep/doc/source/development/architecture/diagramms/ruleTree.drawio.html


Output
======

.. raw:: html
   :file: /home/vagrant/external_work/Logprep/doc/source/development/architecture/diagramms/output.drawio.html



Event flow
==========

To make the flow and processing of a single event more comprehensible, this has been simplified in this diagram.

.. raw:: html
   :file: /home/vagrant/external_work/Logprep/doc/source/development/architecture/diagramms/event_flow.drawio.html


Multiprocessing
===============


Expandability
=============

Logprep is designed to be extended with new Connectors and Processors.
