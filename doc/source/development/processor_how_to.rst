Implementing a new Processor
============================

A processor is used to process log messages.
Basically, a processor is called for every incoming log message (see :ref:`pipelines`), which it
then can modify. For this, some directions have to be considered.


Concurrency/IPC
---------------

Processors can run in parallel on multiple different system processes.
Therefore, it is not guaranteed that a specific processor will see all incoming log messages.
Inter-process-communication (IPC) must be used if information of log messages has to be shared between multiple processor instances.
IPC is relatively slow and can not be used if the processor instances are located on different machines.
In those cases it should be reconsidered if it is necessary that information is being shared or if an implementation of the functionality is generally sensible in the context of ths framework.

.. _implementing_a_new_processor:

Getting started
---------------

.. autoclass:: logprep.util.processor_generator.ProcessorCodeGenerator
   :no-members:
   :no-undoc-members:
   :no-inherited-members:
   :noindex:

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
            rules:
                - tests/testdata/rules_1/
                - tests/testdata/rules_2/
            new_config_parameter: config_value

    """
    from logprep.abc.processor import Processor
    from attrs import define, field

    class NewProcessor(Processor):
        """short docstring for new_processor"""
        @define(kw_only=True)
        class Config(Processor.Config):
            """NewProcessor config"""
            new_config_parameter: str = field(...)
            """the new processor specific config parameter"""

        __slots__ = ["processor_attribute"]

        processor_attribute: list

        def __init__(self, name, configuration, logger):
            super().__init__(name, configuration, logger)
            self.processor_attribute = []

        def _apply_rules(self, event, rule):
            """your implemented workload"""
            ...

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
If you want to do something to the event after all rules have been applied, then you could overwrite this method and implement your code after calling the `super().process(event)`.
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

An exception should not been thrown on processor level. Instead it should be added to
the :py:class:`~logprep.abc.processor.ProcessorResult` if an error occurs during the processing of a log message.
All exceptions are being logged in :py:class:`~logprep.framework.pipeline.Pipeline` and should provide a helpful
error message with `str(exception)`. You do not have to log the exception in the processor itself.
Exceptions derived from :py:class:`~logprep.processor.base.exceptions.ProcessingWarning` have no impact on the
operation of the processor.
Other exceptions stop the processing of a log message.
However, the log message will be separately stored as failed (see :ref:`error_output`).


Metrics
^^^^^^^

To achieve implementing new processor specific metrics you have to implement a embedded class
:code:`Metrics` inside the processor class which inherits from :code:`Component.Metrics`.
For further information about metrics see the reference implementation in the :code:`Amides` Processor.

The following code example highlights an implementation of processor specific metrics, aligned with
the general implementation of a new processor seen in :ref:`implementing_a_new_processor`.

..  code-block:: python
    :linenos:

    """Processor Documentation"""
    from logprep.abc.processor import Processor
    from logprep.metrics.metrics import CounterMetric
    from attrs import define

    class NewProcessor(Processor):
        """short docstring for new_processor"""

        @define(kw_only=True)
        class Config(Processor.Config):
            """NewProcessor config"""
            ...

        @define(kw_only=True)
        class Metrics(Component.Metrics):
            """Tracks statistics about the NewProcessor"""

            new_metric: CounterMetric = field(
                factory=lambda: CounterMetric(
                    description="Short description of this metric",
                    name="new_metric",
                )
            )
            """Short description of this metric"""
    

        __slots__ = ["processor_attribute"]

        processor_attribute: list

        def __init__(self, name, configuration, logger):
            super().__init__(name, configuration, logger)
            self.processor_attribute = []
            self.metrics = self.NewProcessorMetrics(
                labels=self.metric_labels,
                rule_tree=self._rule_tree.metrics,
            )

        def _apply_rules(self, event, rule):
            """your implemented workload"""
            ...

After initialization of these new metrics it is necessary  to increase or change them accordingly.
This can be simply done by accessing the attribute and changing it's value.
For example, the following code will increase the metrics inside the apply_rules method:

..  code-block:: python
    :linenos:

    def _apply_rules(self, event, rule):
        """your implemented workload"""
        ...
        if something_happens:
            self.metrics.new_metric += 1

If the processor already has processor specific metrics and only one new metric value is needed,
it can simply be created by adding a new attribute to the ProcessorMetrics class.
Once the new attribute exists, it can be accessed and updated when needed.
The exporter will automatically recognize it as a new metric and will expose it as such.

Tests
-----

While developing the new processor you have to create a test class under 
`tests.unit.processor.yourprocessor_package.processor`. Your test class has to inherit from
`BaseProcessorTestCase`. It will help you to implement the necessary methods the right way. All
tests should pass successfully. Appropriate tests for the processor specific functions have to 
be implemented independently.
