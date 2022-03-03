==========
Processors
==========

Labeler
-------

Parameter
^^^^^^^^^

type
~~~~

The value `labeler` chooses the processor type Labeler, which will be described here in greater detail.

schema
~~~~~~

Path to a labeling schema file (like `/var/git/logprep-rules/labeling/schema.json`).

include_parent_labels
~~~~~~~~~~~~~~~~~~~~~

If the option is deactivated (`off`) only labels defined in a rule will be activated.
Otherwise, also allowed labels in the path to the *root* of the corresponding category of a label will be added.
This allows to search for higher level labels if this option was activated in the rule.

rules
~~~~~

List of directory paths with rule files, i.e.:

  * /var/git/logprep-rules/rules/
  * /var/git/other-rules/rules/
  * /var/git/additional-rules/rules/

Here directories can be defined from which rule files will be loaded.
An arbitrary amount of rule directories can be given.
However, the processing time increases with the addition of more rules.

Labeling-Schema and validating Rules
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The validation of schemata and rules can be started separately by executing:

..  code-block:: bash

    PYTHONPATH="." python3 logprep/util/schema_and_rule_checker.py $LABELING_SCHEMA $RULES

Where :code:`$LABELING_SCHEMA` is the path to a labeling schema file and :code:`$RULES` is the path to a directory with rule files.

Example
^^^^^^^

..  code-block:: yaml
    :linenos:

    - labelername:
        type: labeler
        schema: tests/testdata/labeler_rules/labeling/schema.json
        include_parent_labels: on
        rules:
            - tests/testdata/labeler_rules/rules/

Normalizer
----------

Parameter
^^^^^^^^^

type
~~~~

The value `normalizer` chooses the processor type Normalizer, which will be described here in greater detail.

specific_rules
~~~~~~~~~~~~~~

List of directory paths with rule files that are specific for some event IDs.
These rules are being executed before generic rules, i.e.:

  * /var/git/logprep-rules/normalizer_rules/specific/
  * /var/git/other-rules/normalizer_rules/specific/

generic_rules
~~~~~~~~~~~~~

List of directory paths with generic rule files that can match multiple event types.
These rules are being executed after specific rules, i.e.:

  * /var/git/logprep-rules/normalizer_rules/generic/
  * /var/git/other-rules/normalizer_rules/generic/


regex_mapping
~~~~~~~~~~~~~

Path to regex mapping file with regex keywords that are replaced with regex expressions by the normalizer.

grok_patterns
~~~~~~~~~~~~~

Optional path to a directory with grok patterns.

GeoIP Enricher
--------------

Parameter
^^^^^^^^^

type
~~~~

The value `geoip_enricher` chooses the processor type GeoIPEnricher, which will be described here in greater detail.

rules
~~~~~

List of directory paths with rule files, i.e.:

  * /var/git/logprep-rules/geoip_enricher_rules/

tree_config
~~~~~~~~~~~

Path to JSON file with rule tree matcher config.

geoip_enricher.db_path
~~~~~~~~~~~~~~~~~~~~~~

Path to a `Geo2Lite` city database by `Maxmind` in binary format.
This must be downloaded separately.

.. _begin:

    This product includes GeoLite2 data created by MaxMind, available from
    https://www.maxmind.com.

Generic Adder
-------------

Parameter
^^^^^^^^^

type
~~~~

The value `generic_adder` chooses the processor type GenericAdder, which will be described here in greater detail.

rules
~~~~~

List of directory paths with rule files, i.e.:

  * /var/git/logprep-rules/generic_adder_rules/

tree_config
~~~~~~~~~~~

Path to JSON file with rule tree matcher config.

Datetime Extractor
------------------

Parameter
^^^^^^^^^

type
~~~~

The value `datetime_extractor` chooses the processor type DateTimeExtractor, which will be described here in greater detail.

rules
~~~~~

List of directory paths with rule files, i.e.:

  * /var/git/logprep-rules/datetime_extractor_rules/

tree_config
~~~~~~~~~~~

Path to JSON file with rule tree matcher config.

Generic Resolver
----------------

Parameter
^^^^^^^^^

type
~~~~

The value `generic_resolver` chooses the processor type GenericResolver, which will be described here in greater detail.

rules
~~~~~

List of directory paths with rule files, i.e.:

  * /var/git/logprep-rules/generic_resolver_rules/

tree_config
~~~~~~~~~~~

Path to JSON file with rule tree matcher config.

generic_resolver.resolve_mapping
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Path to a JSON mapping with abbreviations of network device types.

Domain Resolver
---------------

Parameter
^^^^^^^^^

type
~~~~

The value `domain_resolver` chooses the processor type DomainResolver, which will be described here in greater detail.

rules
~~~~~

List of directory paths with rule files, i.e.:

  * /var/git/logprep-rules/domain_resolver_rules/

tree_config
~~~~~~~~~~~

Path to JSON file with rule tree matcher config.

domain_resolver.tld_list
~~~~~~~~~~~~~~~~~~~~~~~~

Path to a file with a list of top-level domains (like https://publicsuffix.org/list/public_suffix_list.dat).

domain_resolver.timeout
~~~~~~~~~~~~~~~~~~~~~~~

Timeout for resolving of domains.

domain_resolver.hash_salt
~~~~~~~~~~~~~~~~~~~~~~~~~

A salt that is used for hashing.

domain_resolver.max_caching_days
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Number of days a domains is cached after the last time it appeared.
This caching reduces the CPU load of Logprep (no demanding encryption must be performed repeatedly) and the load on subsequent components (i.e. Logstash or Elasticsearch).
Setting the caching days to Null deactivates the caching.
In case the cache size has been exceeded (see `domain_resolver.max_cached_domains`_), the oldest cached pseudonyms will be discarded first.
Thus, it is possible that a domain is re-added to the cache before max_caching_days has elapsed if it was discarded due to the size limit.

domain_resolver.max_cached_domains
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The maximum number of cached domains.
One cache entry requires ~250 Byte, thus 10 million elements would require about 2.3 GB RAM.
The cache is not persisted.
Restarting Logprep does therefore clear the cache.

Domain Label Extractor
----------------------

Parameter
^^^^^^^^^

type
~~~~

The value `domain_label_extractor` chooses the processor type DomainLabelExtractor, which configurations will be
described here.

rules
~~~~~

List of directory paths with rule files, i.e.:

  * /var/git/logprep-rules/domain_label_extractor/rules/

tree_config
~~~~~~~~~~~

Path to JSON file with rule tree matcher config.

tld_lists
~~~~~~~~~

Optional list of path to files with top-level domain lists (like https://publicsuffix.org/list/public_suffix_list.dat).
If no path is given a default list will be retrieved online and cached in a local directory. For local files the path
has to be given with :code:`file:///path/to/file.dat`.

tagging_field_name
~~~~~~~~~~~~~~~~~~

Optional configuration field that defines into which field in the event the error indication 'unrecognized_domain'
should be written to. If this field is not present it defaults to 'tags'.

List Comparison Enricher
------------------------

Parameter
^^^^^^^^^

type
~~~~

The value `list_comparison` chooses the processor type ListComparison, which configurations will be
described here.

rules
~~~~~

List of directory paths with rule files, i.e.:

  * /var/git/logprep-rules/list_comparison/rules/

tree_config
~~~~~~~~~~~

Path to JSON file with rule tree matcher config.

Selective Extractor
-------------------

Parameter
^^^^^^^^^

type
~~~~

The value `selective_extractor` chooses the processor type SelectiveExtractor, which configurations will be
described here.

selective_extractor_topic
~~~~~~~~~~~~~~~~~~~~~~~~~

This parameter defines the kafka topic the extracted fields should be written to.

extractor_list
~~~~~~~~~~~~~~

Path to a list of fields which should be extracted and written to the configured Kafka topic. These can be dotted fields.
Fields are only extracted if they are contained in given log messages. If fields are provided more than once in the
extractor list, they are only extracted once.

Template Replacer
--------------------

Parameter
^^^^^^^^^

type
~~~~

The value `template_replacer` chooses the processor type TemplateReplacer, which will be described here in greater detail.

rules
~~~~~

List of directory paths with rule files, i.e.:

  * /var/git/logprep-rules/template_replacer_rules/

tree_config
~~~~~~~~~~~

Path to JSON file with rule tree matcher config.

template
~~~~~~~~

Path to a YML file with a list of replacements in the format `%{provider_name}-%{event_id}: %{new_message}`.

pattern
~~~~~~~

Configures how to use the template file.

delimiter
+++++++++

Delimiter to use to split the template.

fields
++++++

A list of dotted fields that are being checked by the template.

allowed_delimiter_field
+++++++++++++++++++++++

One of the fields in the fields list can contain the delimiter. This must be specified here.

target_field
++++++++++++

The field that gets replaced by the template.

PreDetector
-----------

Parameter
^^^^^^^^^

type
~~~~

The value `pre_detector` chooses the processor type Predetector, which will be described here in greater detail.

rules
~~~~~

List of directory path with rule files for the Predetector, i.e.:

  * /var/git/logprep-rules/pre_detector_rules/
  * /var/git/other-rules/pre_detector_rules/

tree_config
~~~~~~~~~~~

Path to JSON file with rule tree matcher config.

pre_detector_topic
~~~~~~~~~~~~~~~~~~
A Kafka topic for the detection results of the Predetector.
Results in this topic can be linked to the original event via a `pre_detector_id`.

alert_ip_list
~~~~~~~~~~~~~

Path to a YML file with a dictionary of IPs.
It is used by the Predetector to throw alerts if one of the IPs is found in fields that were defined in a rule.

It uses IPs or networks in the CIDR format as keys and can contain expiration dates in the ISO format as values.
If a value is empty, then there is no expiration date for the IP check.
If a checked IP is covered by an IP and a network in the dictionary (i.e. IP 127.0.0.1 and network 127.0.0.0/24 when checking 127.0.0.1),
then the expiration date of the IP is being used.

Example
^^^^^^^

..  code-block:: yaml
    :linenos:

    123.123.123.123: 2077-08-31T16:47+00:00
    222.222.0.0/24: 1900-08-31T16:47+00:00  # A comment
    222.222.0.0:

Pseudonymizer
-------------

Parameter
^^^^^^^^^

type
~~~~

The value `pseudonymizer` chooses the processor type Pseudonymizer, which will be described here in greater detail.

pubkey_analyst
~~~~~~~~~~~~~~
Path to the public key of an analyst.

* /var/git/analyst_pub.pem

pubkey_depseudo
~~~~~~~~~~~~~~~
Path to the public key for depseudonymization

* /var/git/depseudo_pub.pem

regex_mapping
~~~~~~~~~~~~~
Path to a file with a regex mapping for pseudonymization, i.e.:

* /var/git/logprep-rules/pseudonymizer_rules/regex_mapping.json

specific_rules
~~~~~~~~~~~~~~

List of directory paths with rule files that are specific for some event IDs.
These rules are being executed before generic rules, i.e.:

  * /var/git/logprep-rules/pseudonymizer_rules/specific/
  * /var/git/other-rules/pseudonymizer_rules/specific/

generic_rules
~~~~~~~~~~~~~

List of directory paths with generic rule files that can match multiple event types.
These rules are being executed after specific rules, i.e.:

  * /var/git/logprep-rules/pseudonymizer_rules/generic/
  * /var/git/other-rules/pseudonymizer_rules/generic/

hash_salt
~~~~~~~~~
A salt that is used for hashing.

pseudonyms_topic
~~~~~~~~~~~~~~~~
A Kafka-topic for pseudonyms.
These are not the pseudonymized events, but just the pseudonyms with the encrypted real values.

max_caching_days
~~~~~~~~~~~~~~~~
Number of days a pseudonym is cached after the last time it appeared.
This caching reduces the CPU load of Logprep (no demanding encryption must be performed repeatedly) and the load on subsequent components (i.e. Logstash or Elasticsearch).
Setting the caching days to Null deactivates the caching.
In case the cache size has been exceeded (see max_cached_pseudonyms), the oldest cached pseudonyms will be discarded first.
Thus, it is possible that a pseudonym is re-added to the cache before max_caching_days has elapsed if it was discarded due to the size limit.

max_cached_pseudonyms
~~~~~~~~~~~~~~~~~~~~~
The maximum number of cached pseudonyms.
One cache entry requires ~250 Byte, thus 10 million elements would require about 2.3 GB RAM.
The cache is not persisted.
Restarting Logprep does therefore clear the cache.

tld_list
~~~~~~~~

Path to a file with a list of top-level domains (i.e. https://publicsuffix.org/list/public_suffix_list.dat).

Clusterer
----------

Parameter
^^^^^^^^^

type
~~~~

The value `clusterer` chooses the processor type Clusterer, which will be described here in greater detail.
The log clustering is mainly developed for Syslogs, unstructured and semi-structured logs.
The clusterer calculates a log signature based on the message field.
The log signature is calculated with heuristic and deterministic rules.
The idea of a log signature is to extract a subset of the constant parts of a log and to delete the dynamic parts.
If the fields syslog.facility and event.severity are in the log, then they are prefixed to the log signature.

Logs are only clustered if at least one of the following criteria is fulfilled:

..  code-block:: yaml

    Criteria 1: { "message": "A sample message", "tags": ["clusterable", ...], ... }
    Criteria 2: { "message": "A sample message", "clusterable": true, ... }
    Criteria 3: { "message": "A sample message", "syslog": { "facility": <number> }, "event": { "severity": <string> }, ... }

rules
~~~~~

List of directory paths with rule files, i.e.:

  * /var/git/logprep-rules/clusterer_rules/

output_field_name
~~~~~~~~~~~~~~~~~

The value `output_field_name` defines in which field results of the clustering should be stored.

Dropper
-------

Parameter
^^^^^^^^^

type
~~~~

The value `dropper` chooses the processor type Dropper, which will be described here in greater detail.

rules
~~~~~

List of directory paths with rule files, i.e.:

  * /var/git/logprep-rules/dropper_rules/

output_field_name
~~~~~~~~~~~~~~~~~

The value `output_field_name` defines in which field results of the clustering should be stored.
