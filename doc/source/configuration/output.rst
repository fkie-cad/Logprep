.. _output:

======
Output
======

It is possible to define multiple outputs as a dictionary of :code:`<output name>: <output config>`.
If you define multiple outputs with the attribute :code:`default: true` then be aware, that
logprep only guaranties that one output has received data by calling the
:code:`batch_finished_callback`.

.. security-best-practice::
   :title: Output Connectors
   :location: config.output.<Output-Name>.type
   :suggested-value: <ConfluentKafkaOutput|OpensearchOutput|S3Output>

   Similar to the input connectors there is a list of available output connectors of which some
   are only meant for debugging, namely: :code:`ConsoleOutput` and :code:`JsonlOutput`.
   It is advised to not use these in production environments.

   When configuring multiple outputs it is also recommend to only use one default output and to
   define other outputs only for storing custom extra data.
   Otherwise it cannot be guaranteed that all events are safely stored.

.. automodule:: logprep.connector.confluent_kafka.output
.. autoclass:: logprep.connector.confluent_kafka.output.ConfluentKafkaOutput.Config
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

.. automodule:: logprep.connector.opensearch.output
.. autoclass:: logprep.connector.opensearch.output.OpensearchOutput.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.connector.s3.output
.. autoclass:: logprep.connector.s3.output.S3Output.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.connector.http.output
.. autoclass:: logprep.connector.http.output.HttpOutput.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:
