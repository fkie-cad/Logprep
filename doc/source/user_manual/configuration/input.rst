.. _input:

=====
Input
=====

.. security-best-practice::
   :title: Input Connectors
   :location: config.input.<INPUT-Name>.type and config.input.<INPUT-Name>.preprocessing.hmac
   :suggested-value: <ConfluentKafkaInput|HttpConnector|FileInput> and <hmac>

   It is advised to only use the :code:`ConfluentKafkaInput`, :code:`HttpConnector` or
   :code:`FileInput` as input connectors in production environments.
   The connectors :code:`DummyInput`, :code:`JsonInput` and :code:`JsonlInput` are mainly designed
   for debugging purposes.

   Furthermore, it is suggested to enable the :code:`HMAC` preprocessor to ensure no tempering of
   processed events.

   .. code:: yaml

      hmac:
         target: <RAW_MSG>
         key: <SECRET>
         output_field: HMAC

.. automodule:: logprep.connector.confluent_kafka.input
.. autoclass:: logprep.connector.confluent_kafka.input.ConfluentKafkaInput.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.connector.dummy.input
.. autoclass:: logprep.connector.dummy.input.DummyInput.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.connector.http.input
.. autoclass:: logprep.connector.http.input.HttpInput.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.connector.json.input
.. autoclass:: logprep.connector.json.input.JsonInput.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.connector.jsonl.input
.. autoclass:: logprep.connector.jsonl.input.JsonlInput.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.connector.file.input
.. autoclass:: logprep.connector.file.input.FileInput.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:
