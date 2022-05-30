Implementing a new Processor
============================

.. mermaid::

    graph LR
    A[register processor]-->B[add processor rule]
    B-->C[add processor class]
    C-->D[add processor tests]


A processor is used to process log messages.
Basically, a processor is called for every incoming log message (see :ref:`pipelines`), which it then can modify.
For this, some directions have to be considered.

Firstly, you have to register your processor in the :py:class:`ProcessorRegistry` by importing it and adding it to the `mapping` attribute.
This exposes your processor to the :py:class:`ProcessorFactory` and you can reference it as the processor type in your processor config.


Concurrency/IPC
---------------

Processors can run in parallel on multiple different system processes.
Therefore, it is not guaranteed that a specific processor will see all incoming log messages.
Inter-process-communication (IPC) must be used if information of log messages has the be shared between multiple processor instances.
IPC is relatively slow and can not be used if the processor instances are located on different machines.
In those cases it should be reconsidered if it is necessary that information is being shared or if an implementation of the functionality is generally sensible in the context of ths framework.

Factory
-------

Processors are being created by the factory :py:class:`~logprep.processor.processor_factory.ProcessorFactory`.

Processor
---------

Processors must implement the interface :py:class:`~logprep.abc.processor.Processor`.
If you want your processor to have processor specific configuration parameters you have to create a :py:class:`Config` class inside your processor class definition.
This :py:class:`Config` class has to inherit from :py:class:`Processor.Config` and it has to be written as a `attrs` dataclass with `kw_only` set to `true`.

..  code-block:: python
    :linenos:

    """
    NewProcessor
    ------------

    Write your processor description here. It will be rendered in the processor documentation.
    
    Example
    ^^^^^^^
    ..  code-block:: yaml
        :linenos:

        - newprocessorname:
            type: new_processor
            specific_rules:
                - tests/testdata/rules/specific/
            generic_rules:
                - tests/testdata/rules/generic/
            new_config_parameter: config_value

    """
    from logprep.abc import Processor
    from attrs import define, field

    class NewProcessor(Processor):
        """short docstring for new_processor"""
        @define(kw_only=True)
        class Config(Processor.Config):
            """NewProcessor config"""
            new_config_parameter: str = field(...)
            """the new processor specific config parameter"""

The rules must implement the interface :py:class:`~logprep.processor.base.rule.Rule`.

setup, shut_down
^^^^^^^^^^^^^^^^

The method :py:meth:`~logprep.abc.processor.Processor.setup` is called before the first log message will be processed,
the method :py:meth:`~logprep.abc.processor.Processor.shut_down` after the last log message was processed.

Those methods could be implemented to create additional data structures and to release them after processing has finished.

process
^^^^^^^

This method is implemented in the :py:class:`~logprep.abc.processor.Processor` and is called for every log message. 
To process the event it invokes the processors `apply_rules` method.
If you want to do somthing to the event after all rules have been applied, then you could overwrite this method and implement your code after calling the `super().process(event)`.
The log message is being passed as a dictionary and modified 'in place', meaning that modifications are being performed directly on the input event.

.. code-block:: python 
   :linenos:

    def process(self, event: dict):
        super().process(event)
        if self.new_config_parameter:
            self._do_more_stuff()

.. WARNING:: It is possible to cancel processing of a log message and to discard it by deleting all of its fields.
             This could be used if a large amounts of useless logs are being generated, but it does not conform to the goal of Logprep and should be avoided.


Exceptions/Error Handling
~~~~~~~~~~~~~~~~~~~~~~~~~

An exception should be thrown if an error occurs during the processing of a log message.
All exceptions are being logged and should return a helpful error message with `str(exception)`.
Exceptions derived from `ProcessorWarningError` have no impact on the operation of the processor.
Other exceptions stop the processing of a log message.
However, the log message will be separately stored as failed (see :ref:`connector_output`, `store_failed``).
