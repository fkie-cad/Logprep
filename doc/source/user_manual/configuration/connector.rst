==========
Connectors
==========

Connectors are used to connect the pipeline with different log sources and log sinks on the system,
allowing Logprep to read and write log messages.
It is possible to configure different type of connectors via the `type` field.
Currently, it is assumed that Kafka is being used, which uses the `confluentkafka` connector.
Thus, `confluentkafka` will be described in greater detail below.
The `dummy`, `writer` and `writer_json_input` connectors are only utilized in testing.


Confluentkafka
==============

Logprep uses Confluent-Kafka-Python as client library to communicate with kafka-clusters.
Important information sources are `Confluent-Kafka-Python-Repo <https://github.com/confluentinc/confluent-kafka-python>`_,
`Confluent-Kafka-Python-Doku 1 <https://docs.confluent.io/current/clients/confluent-kafka-python/>`_ (comprehensive but out-dated description),
`Confluent-Kafka-Python-Doku 2 <https://docs.confluent.io/current/clients/python.html#>`_ (currently just a brief description) and the C-library `librdkafka <https://github.com/edenhill/librdkafka>`_, which is built on Confluent-Kafka-Python.

type
----

Connectors are chosen by the value `confluentkafka`.
The options for the `confluentkafka` connector will be described below.

bootstrapservers
----------------

This field contains a list of Kafka servers (also known as Kafka brokers or Kafka nodes) that can be contacted by Logprep to initiate the connection to a Kafka cluster.
The list does not have to be complete, since the Kafka server contains contact information for other Kafka nodes after the initial connection.
It is advised to list at least two Kafka servers.

consumer
--------

This object configures how log messages are being fetched from Kafka.

- **topic**: The topic from which new log messages will be fetched.
- **group**: Corresponds to the Kafka configuration parameter `group.id <https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md>`_. The individual Logprep processes have the same *group.id* and thus belong to the same consumer group. Thereby partitions of topics can be assigned to individual consumers.
- **auto_commit**: Corresponds to the Kafka configuration parameter `enable.auto.commit <https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md>`_. Enabling this parameter causes offsets being sent automatically and periodically. The values can be either *true/false* or *on/off*. Currently, this has to be set to *true*, since independent offset handling is not implemented in Logprep and it would not make sense to activate it anyways. The default setting of librdkafka is *true*.
- **session_timeout**: Corresponds to the Kafka configuration parameter `session.timeout.ms <https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md>`_. This defines the maximum duration a kafka consumer can be without contact to the Kafka broker. The kafka consumer must regularly send a heartbeat to the group coordinator, otherwise the consumer will be considered as being unavailable. In this case the group coordinator assigns the partition to be processed to another computer while re-balancing. The default of librdkafka is `10000` ms (10 s).
- **offset_reset_policy**: Corresponds to the Kafka configuration parameter `auto.offset.reset <https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md>`_. This parameter influences from which offset the Kafka consumer starts to fetch log messages from an assigned partition. The values *latest/earliest/none* are possible. With a value of *none* Logprep must manage the offset by itself. However, this is not supported by Logprep, since it is not relevant for our use-case. If the value is set to *latest/largest*, the Kafka consumer starts by reading the newest log messages of a partition if a valid offset is missing. Thus, old log messages from that partition will not be processed. This setting can therefore lead to a loss of log messages. A value of *earliest/smallest* causes the Kafka consumer to read all log messages from a partition, which can lead to a duplication of log messages. Currently, the deprecated value *smallest* is used, which should be later changed to *earliest*. The default value of librdkafka is *largest*.
- **enable_auto_offset_store**: Corresponds to the Kafka configuration parameter `enable.auto.offset.store <https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md>`_. This parameter defines if the offset is automatically updated in memory. Disabling this allows Logprep to update the offset more accurately. The default value in librdkafka it is *true*.

preprocessing
^^^^^^^^^^^^^

It is possible to activate simple preprocessors in the consumer.
The following will describe the available preprocessors and what they do.
They each have to be defined under the key :code:`preprocessor`.

**hmac**

If required it is possible to automatically attach an HMAC to incoming log messages.
To activate this preprocessor the following options should be appended to the preprocessor options
under a new field :code:`hmac`.
This field is completely optional and can also be omitted if no hmac is needed.
An example with hmac configuration is given at the end of this page.

- **target**: Defines a field inside the log message which should be used for the hmac calculation. If the target field
  is not found or does not exists an error message is written into the configured output field. If the hmac should be
  calculated on the full incoming raw message instead of a subfield the target option should be set to
  :code:`<RAW_MSG>`.
- **key**: The secret key that will be used to calculate the hmac.
- **output_field**: The parent name of the field where the hmac result should be written to in the original incoming
  log message. As subfields the result will have a field called :code:`hmac`, containing the calculated hmac, and
  :code:`compressed_base64`, containing the original message that was used to calculate the hmac in compressed and
  base64 encoded. In case the output field exists already in the original message an error is raised.

The hmac itself will be calculated with python's :code:`hashlib.sha256` algorithm and the compression is based on the
:code:`zlib` library.

**version_info_target_field**

If required it is possible to automatically add the logprep version and the used configuration
version to every incoming log message.
This helps to keep track of the processing of the events when the configuration is changing often.
To enable adding the versions to each event the keyword :code:`version_info_target_field` has to be
set under the field :code:`preprocessing`.
It defines the name of the parent field under which the version info should be given.
The example at the bottom of this page includes this configuration.
If the field :code:`preprocessing` and :code:`version_info_target_field` are not present then no
version information is added to the event.
The following json shows a snippet of an event with the added version information.
The configuration was set to :code:`version_info_target_field: version_info`

**logprep_arrival_timestamp_target_field**

It is possible to automatically add the arrival time in Logprep to every incoming log message.
To enable adding arrival times to each event the keyword
:code:`logprep_arrival_timestamp_target_field` has to be set under the field :code:`preprocessing`.
It defines the name of the dotted field under which the arrival times should be given.
The example at the bottom of this page includes this configuration.
If the field :code:`preprocessing` and :code:`logprep_arrival_timestamp_target_field` are not
present then no arrival timestamp is added to the event.

**logprep_arrival_delta_target_field**

It is possible to automatically calculate the difference between the arrival time of logs in
Logprep and their generation timestamp, which is then added to every incoming log message.
To enable adding delta times to each event the keyword :code:`logprep_arrival_delta_target_field`
has to be set under the field :code:`preprocessing`.
Furthermore, :code:`logprep_arrival_delta_target_field` has to be set (see above).
It defines the name of the dotted field under which the delta times should be given.
The example at the bottom of this page includes this configuration.
If the field :code:`preprocessing`, :code:`logprep_arrival_timestamp_target_field` and
:code:`logprep_arrival_delta_target_field` are not present then no arrival timestamp is added to the
event.

..  code-block:: json
    :linenos:
    :caption: Example event with version information

    {
        "Any": "regular event information",
        "version_info": {
            "logprep": "3.0.0",
            "configuration": "1"
        },
        ...
    }


producer
--------

In this object the configuration for storing and processing log messages in kafka is set.

- **topic**: The topic where log messages should be stored.
- **error_topic**: The topic where log messages are stored that failed to be processed.
- **ack_policy**: Corresponds to the Kafka producer configuration parameter `acks <https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md>`_. The parameter describes how many partition replicas the processed log messages obtained. Valid values are *0/1/-1(all)*. For the value *0* no replicas are expected and data loss is possible on failure of the Kafka cluster. For the value *1* replicas are expected, but data loss on failure can still occur in rare cases. By setting the value to *-1* or *all* the safest mode is activated and data loss is almost ruled out, even on failure. However, this modes causes the most overhead. A value of *-1/all* is recommended. It should be changed to *1* if it causes performance issues. The default value for librdkafka is *-1* (all).
- **compression**: Corresponds to the Kafka producer configuration parameter `compression.type <https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md>`_. Log messages can be compressed with the modes *snappy/gzip/lz4/zstd*. Compression can be disabled with *none*. Our tests have shown that compression reduces the performance (throughput per seconds). However, compression can be useful if network bandwidth is limited. The default value for librdkafka is *none*.
- **maximum_backlog**: Corresponds to the Kafka producer configuration parameter `queue.buffering.max.messages <https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md>`_. Log messages that have not been written are being cached. An error message is created if this value is exceeded and the log messages are lost. This can happen if the Kafka server is unreachable or overloaded. Therefore this value should be increased during continuous operation so that clients do not throw away log messages prematurely. It must be set to a whole number *> 0*. The default value for librdkafka is *100000* (the amount of log messages).
- **linger_duration**: Corresponds to the Kafka producer configuration parameter `linger.ms <https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md>`_. The Kafka producer sends log messages if the batch size or the *linger_duration* in milliseconds has been reached. If the value is set to *0*, the Kafka producer can send log messages directly. The default for librdkafka is *0.5*.
- **flush_timeout**: Does not correspond to any Kafka producer configuration parameter. This setting defines after how many seconds an overflown buffer (Exception BufferError) must be flushed at the latest. After the time is over processing will be resumed even if the buffer was not flushed completely. This could be eventually optimized. *flush_timeout* is a parameter for the confluent Kafka method `flush() <https://docs.confluent.io/current/clients/confluent-kafka-python/index.html#confluent_kafka.Producer.flush>`_. See `additional documentation <https://docs.confluent.io/current/clients/python.html#synchronous-writes>`_.
- **send_timeout**: Does not correspond to any Kafka producer configuration parameter. The maximum waiting time in seconds Logprep should wait blocking. *send_timeout* is a parameter for the method `poll() <https://docs.confluent.io/current/clients/confluent-kafka-python/index.html#confluent_kafka.Producer.poll>`_.

ssl
---

In this subsection the settings of TLS/SSL are defined.

- **cafile** Path to a certificate authority (see `ssl.ca.location <https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md>`_).
- **certfile** Path to a file with the certificate of the client (see `ssl.certificate.location <https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md>`_).
- **keyfile** Path to the key file corresponding to the given certificate file (see `ssl.key.location <https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md>`_).
- **password** Password for the given key file (see `ssl.key.password <https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md>`_).

Example
-------

..  code-block:: yaml
    :linenos:
    :caption: Logprep configuration (with optional settings)

    connector:
      type: confluentkafka
      bootstrapservers:
        - 127.0.0.1:9092
      consumer:
        topic: consumer
        group: cgroup
        auto_commit: on
        session_timeout: 6000
        offset_reset_policy: smallest
        preprocessing:
          version_info_target_field: Version_info
          hmac:
            target: <RAW_MSG>
            key: secret-key
            output_field: Hmac
          logprep_arrival_timestamp_target_field: logprep_arrival.timestamp
          logprep_arrival_delta_target_field: logprep_arrival.delta
      producer:
        topic: producer
        error_topic: producer_error
        ack_policy: all
        compression: none
        maximum_backlog: 10000
        linger_duration: 0
        flush_timeout: 30
        send_timeout: 2
      ssl:
        cafile:
        certfile:
        keyfile:
        password:
