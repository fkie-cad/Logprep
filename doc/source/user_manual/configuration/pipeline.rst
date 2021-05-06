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

..  code-block:: yaml
    :linenos:

    pipeline:
      - normalizer:
          type: normalizer
          schema: default
      - labeler:
          type: labeler
          schema: /etc/labeler/schema.json
          rules:
            - /etc/labeler/rules/
            - /opt/labeler/rules
      - other_labeler:
          type: labeler
          schema: /opt/other_labeler/schema.json
          rules:
            - /etc/other_labeler/rules/