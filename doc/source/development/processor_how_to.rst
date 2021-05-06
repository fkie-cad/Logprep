Implementing a new Processor
============================

A processor is used to process log messages.
Basically, a processor is called for every incoming log message (see `pipelines for details`), which it then can modify.
For this, some directions have to be considered.

Firstly, a new factory must be implemented for every new processor.
It is then used to create processor instances based on the configuration.
Furthermore, the configuration should be documented in `doc/config/ProcessorNAME` (replace NAME with the name of the processor).

Concurrency/IPC
-------------------

Processors can run in parallel on multiple different system processes.
Therefore, it is not guaranteed that a specific processor will see all incoming log messages.
Inter-process-communication (IPC) must be used if information of log messages has the be shared between multiple processor instances.
IPC is relatively slow and can not be used if the processor instances are located on different machines.
In those cases it should be reconsidered if it is necessary that information is being shared or if an implementation of the functionality is generally sensible in the context of ths framework.

Factory
-------

Processors are being created by the factory :py:class:`~logprep.processor.processor_factory.ProcessorFactory`.
They will be automatically discovered.

For a processor to be created by the factory, it has to be located in its own directory that is named after the processor name.
Within this directory there must exist a module `factor.py` that implements :py:class:`~logprep.processor.base.factory.BaseFactory`.
Those directories can be created in :py:class:`~logprep.processor` or alternatively an additional custom path can be configured with `plugin_directories` in the configuration file.

For example, the processor `dropper` resides in :py:class:`~logprep.processor.dropper`.
The directory contains a module `factory.py`, `processor.py` and `rule.py`.
Here only `factory.py` must exist.
The specific files `processor.py` and `rule.py` do not have to exist, but the classes implementing the processor and the rule there must exist somewhere.

The following has be be considered when creating a new processor factory:

* Configuration errors should be derived from `InvalidConfigurationError` and should show helpful error messages with `str(exception)`.
* On creation of a processor the parameters `name` and `section` will be passed over. The `name` is mainly used for error handling or debugging and is helpful to distinguish multiple processors of the same type.

Processor
---------

Processors must implement the interface :py:class:`~logprep.processor.base.processor.RuleBasedProcessor` if the processor uses rules.
Otherwise, the interface :py:class:`~logprep.processor.base.processor.BaseProcessor` must be implemented.
Here information in the docstrings should be noted.
If the processor implements :py:class:`~logprep.processor.base.processor.RuleBasedProcessor`,
then its rules must implement the interface :py:class:`~logprep.processor.base.rule.Rule`.

setup, shut_down
^^^^^^^^^^^^^^^^

The method :py:meth:`~logprep.processor.base.processor.Processor.setup` is called before the first log message will be processed,
the method :py:meth:`~logprep.processor.base.processor.Processor.shut_down` after the last log message was processed.

Those methods could be implemented to create additional data structures and to release them after processing has finished.
 
events_processed_count
^^^^^^^^^^^^^^^^^^^^^^

This method can be used for diagnostics and should simply return the amount of log messages a processor has processed.

process
^^^^^^^

This method is called to process log messages.
The log message is being passed as a dictionary and modified 'in place', meaning that modifications are being performed directly on the input event.

**Important**: It is possible to cancel processing of a log message and to discard it by deleting all of its fields.
This could be used if a large amounts of useless logs are being generated, but it does not conform to the goal of Logprep and should be avoided.
The processor :py:class:`~logprep.processor.do_nothing.processor.Delete` demonstrates this.
It deletes all log messages and should be only used for testing purposes.

Exceptions/Error Handling
~~~~~~~~~~~~~~~~~~~~~~~~~

An exception should be thrown if an error occurs during the processing of a log message.
All exceptions are being logged and should return a helpful error message with `str(exception)`.
Exceptions derived from `ProcessorWarningError` have no impact on the operation of the processor.
Other exceptions stop the processing of a log message.
However, the log message will be separately stored as failed (see `ConnectorHowTo`, store_failed).
