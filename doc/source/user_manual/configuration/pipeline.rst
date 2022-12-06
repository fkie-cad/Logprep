=========
Pipelines
=========

The pipeline is configured as a list of objects under the option `pipeline`.
The processors are being processed in the order given in `pipeline`.
The field `type` decides which processor will be created.
The descriptor of the object will be used in the log messages of the corresponding processor.
Due to this it is possible to attribute log messages to their corresponding processor even if multiple processors of the same type exist in the pipeline.

Example
-------

.. literalinclude:: /../../quickstart/exampledata/config/pipeline.yml
   :language: yaml
   :start-after:   level: INFO
   :end-before: input:
