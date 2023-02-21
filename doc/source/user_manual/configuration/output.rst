.. _output:

======
Output
======

It is possible to define multiple outputs as a dictionary of :code:`<output name>: <output config>`.
If you define multiple outputs with the attribute :code:`default: true` then be aware, that
logprep only guaranties that one output has received data by calling the :code:`batch_finished_callback`.

We recommed to only use one default output and define other outputs only for storing custom extra data.

.. automodule:: logprep.connector.confluent_kafka.output
.. autoclass:: logprep.connector.confluent_kafka.input.ConfluentKafkaInput.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.connector.console.output
.. autoclass:: logprep.connector.console.output.ConsoleOutput.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.connector.jsonl.output
.. autoclass:: logprep.connector.jsonl.output.JsonlOutput.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.connector.elasticsearch.output
.. autoclass:: logprep.connector.elasticsearch.output.ElasticsearchOutput.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.connector.opensearch.output
.. autoclass:: logprep.connector.opensearch.output.OpensearchOutput.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:
