==========
Processors
==========


Common Configurations
=====================

Most processors share the following configurations.
The only exceptions at this point is the :code:`Dropper` as it does not yet support 
generic and specific rules.

type
----

The type value defines the processor type that is being configured.
The exact values that are currently possible are given at the specific processor
configurations below.

generic_rules
-------------

List of directory paths with generic rule files that can match multiple event types, e.g.:

  * /var/git/logprep-rules/processor/generic/
  * /var/git/other-rules/processor/generic/

specific_rules
--------------

List of directory paths with rule files that are specific for only some specific events, e.g.:

  * /var/git/logprep-rules/processor/specific/
  * /var/git/other-rules/processor/specific/

tree_config
-----------

Path to a JSON file with a valid rule tree configuration.

--------

Processor Specific Configurations
=================================

Labeler
-------

Parameter
^^^^^^^^^

type
~~~~

The value `labeler` chooses the processor type Labeler.

schema
~~~~~~

Path to a labeling schema file (like `/var/git/logprep-rules/labeling/schema.json`).

include_parent_labels
~~~~~~~~~~~~~~~~~~~~~

If the option is deactivated (`off`) only labels defined in a rule will be activated.
Otherwise, also allowed labels in the path to the *root* of the corresponding category of a label will be added.
This allows to search for higher level labels if this option was activated in the rule.

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

--------

Normalizer
----------

Parameter
^^^^^^^^^

type
~~~~

The value `normalizer` chooses the processor type Normalizer.

regex_mapping
~~~~~~~~~~~~~

Path to regex mapping file with regex keywords that are replaced with regex expressions by the normalizer.

grok_patterns
~~~~~~~~~~~~~

Optional path to a directory with grok patterns.

count_grok_pattern_matches
~~~~~~~~~~~~~~~~~~~~~~~~~~

Optional configuration to count matches of grok patterns.
Counting will be disabled if this value is omitted.

count_directory_path
^^^^^^^^^^^^^^^^^^^^

Path to directory in which files with counts of grok pattern matches will be stored.
One file is created for each day where there was at least one match.

write_period
^^^^^^^^^^^^

Period to wait before a file with grok pattern match counts will be written.
Setting this value very low can have a drastic impact on the performance,
since it requires a file lock and reading from and writing to disc.

lock_file_path
^^^^^^^^^^^^^^

Optional path to lock file.
This lock will be used before writing a grok match count file by a process.
By default, this is set to 'count_grok_pattern_matches.lock'.

--------

GeoIP Enricher
--------------

Parameter
^^^^^^^^^

type
~~~~

The value `geoip_enricher` chooses the processor type GeoIPEnricher.

geoip_enricher.db_path
~~~~~~~~~~~~~~~~~~~~~~

Path to a `Geo2Lite` city database by `Maxmind` in binary format.
This must be downloaded separately.

.. _begin:

    This product includes GeoLite2 data created by MaxMind, available from
    https://www.maxmind.com.

--------

Generic Adder
-------------

Parameter
^^^^^^^^^

type
~~~~

The value `generic_adder` chooses the processor type GenericAdder.

sql_config
~~~~~~~~~~

Configuration of the connection to a MySQL database and settings on how to add data from the database.
This field is optional. The database feature will not be used if `sql_config` is omitted.

sql_config.user
~~~~~~~~~~~~~~~

The user to use when connecting to the MySQL database.

sql_config.password
~~~~~~~~~~~~~~~~~~~

The password to use when connecting to the MySQL database.

sql_config.host
~~~~~~~~~~~~~~~

The host to use when connecting to the MySQL database.

sql_config.database
~~~~~~~~~~~~~~~~~~~

The database name to use when connecting to the MySQL database.

sql_config.table
~~~~~~~~~~~~~~~~

The table name to use when connecting to the MySQL database.

sql_config.target_column
~~~~~~~~~~~~~~~~~~~~~~~~

The name of the column whose values are being matched against a value from an event.
If a value matches, the remaining values of the row with the match are being added to the event.

sql_config.add_target_column
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Determines if the target column itself will be added to the event.
This is set to false per default.

sql_config.timer
~~~~~~~~~~~~~~~~

Period how long to (wait in seconds) before the database table is being checked for changes.
If there is a change, the table is reloaded by Logprep.

Datetime Extractor
------------------

Parameter
^^^^^^^^^

type
~~~~

The value `datetime_extractor` chooses the processor type DateTimeExtractor.

rules
~~~~~

List of directory paths with rule files, i.e.:

  * /var/git/logprep-rules/datetime_extractor_rules/

tree_config
~~~~~~~~~~~

Path to JSON file with rule tree matcher config.

--------

Generic Resolver
----------------

Parameter
^^^^^^^^^

type
~~~~

The value `generic_resolver` chooses the processor type GenericResolver.

Hyperscan Resolver
------------------

.. WARNING::
   The hyperscan resolver is only supported for x86_64 linux with python version 3.6-3.8.

Parameter
^^^^^^^^^

type
~~~~

The value `hyperscan_resolver` chooses the processor type HyperscanResolver.

hyperscan_db_path
~~~~~~~~~~~~~~~~~

Path to a directory where the compiled `Hyperscan <https://python-hyperscan.readthedocs.io/en/latest/>`_ databases will be stored persistently.
Persistent storage is set to false per default.
If the specified directory does not exist, it will be created.
The database will be stored in the directory of the `hyperscan_resolver` if no path has been specified within the pipeline config.
To update and recompile a persistently stored databases simply delete the whole directory.
The databases will be compiled again during the next run.

--------

Domain Resolver
---------------

Parameter
^^^^^^^^^

type
~~~~

The value `domain_resolver` chooses the processor type DomainResolver.

rules
~~~~~

List of directory paths with rule files, i.e.:

  * /var/git/logprep-rules/domain_resolver_rules/

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
This caching reduces the CPU load of Logprep (no demanding encryption must be performed repeatedly)
and the load on subsequent components (i.e. Logstash or Elasticsearch).
Setting the caching days to Null deactivates the caching.
In case the cache size has been exceeded (see `domain_resolver.max_cached_domains`_), the oldest
cached pseudonyms will be discarded first.
Thus, it is possible that a domain is re-added to the cache before max_caching_days has elapsed
if it was discarded due to the size limit.

domain_resolver.max_cached_domains
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The maximum number of cached domains.
One cache entry requires ~250 Byte, thus 10 million elements would require about 2.3 GB RAM.
The cache is not persisted.
Restarting Logprep does therefore clear the cache.

--------

Domain Label Extractor
----------------------

Parameter
^^^^^^^^^

type
~~~~

The value `domain_label_extractor` chooses the processor type DomainLabelExtractor.

tld_lists
~~~~~~~~~

Optional list of path to files with top-level domain lists
(like https://publicsuffix.org/list/public_suffix_list.dat).
If no path is given, a default list will be retrieved online and cached in a local directory.
For local files the path
has to be given with :code:`file:///path/to/file.dat`.

tagging_field_name
~~~~~~~~~~~~~~~~~~

Optional configuration field that defines into which field in the event the informational tags
should be written to.
If this field is not present it defaults to :code:`tags`. More about the tags can be found in
the introduction of the :ref:`intro_domain_label_extractor`.

--------

List Comparison Enricher
------------------------

Parameter
^^^^^^^^^

type
~~~~

The value `list_comparison` chooses the processor type ListComparison.

list_search_base_path
~~~~~~~~~~~~~~~~~~~~~

Relative list paths in rules will be relative to this path if this is set.
This parameter is optional.

--------

Selective Extractor
-------------------

Parameter
^^^^^^^^^

type
~~~~

The value `selective_extractor` chooses the processor type SelectiveExtractor.

--------

Template Replacer
--------------------

Parameter
^^^^^^^^^

type
~~~~

The value `template_replacer` chooses the processor type TemplateReplacer.

template
~~~~~~~~

Path to a YML file with a list of replacements in the format
`%{provider_name}-%{event_id}: %{new_message}`.

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

--------

PreDetector
-----------

Parameter
^^^^^^^^^

type
~~~~

The value `pre_detector` chooses the processor type Predetector.

pre_detector_topic
~~~~~~~~~~~~~~~~~~
A Kafka topic for the detection results of the Predetector.
Results in this topic can be linked to the original event via a `pre_detector_id`.

alert_ip_list
~~~~~~~~~~~~~

Path to a YML file or a list of paths to YML files with dictionaries of IPs.
It is used by the Predetector to throw alerts if one of the IPs is found
in fields that were defined in a rule.

It uses IPs or networks in the CIDR format as keys and can contain expiration
dates in the ISO format as values.
If a value is empty, then there is no expiration date for the IP check.
If a checked IP is covered by an IP and a network in the dictionary
(i.e. IP 127.0.0.1 and network 127.0.0.0/24 when checking 127.0.0.1),
then the expiration date of the IP is being used.

Example
^^^^^^^

..  code-block:: yaml
    :linenos:

    123.123.123.123: 2077-08-31T16:47+00:00
    222.222.0.0/24: 1900-08-31T16:47+00:00  # A comment
    222.222.0.0:

--------

Pseudonymizer
-------------

Parameter
^^^^^^^^^

type
~~~~

The value `pseudonymizer` chooses the processor type Pseudonymizer.

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
This caching reduces the CPU load of Logprep (no demanding encryption must be performed repeatedly)
and the load on subsequent components (i.e. Logstash or Elasticsearch).
Setting the caching days to Null deactivates the caching.
In case the cache size has been exceeded (see max_cached_pseudonyms), the oldest cached
pseudonyms will be discarded first.
Thus, it is possible that a pseudonym is re-added to the cache before max_caching_days has elapsed
if it was discarded due to the size limit.

max_cached_pseudonyms
~~~~~~~~~~~~~~~~~~~~~
The maximum number of cached pseudonyms.
One cache entry requires ~250 Byte, thus 10 million elements would require about 2.3 GB RAM.
The cache is not persisted.
Restarting Logprep does therefore clear the cache.

tld_list
~~~~~~~~

Path to a file with a list of top-level domains (i.e. https://publicsuffix.org/list/public_suffix_list.dat).

--------

Clusterer
----------

Parameter
^^^^^^^^^

type
~~~~

The value `clusterer` chooses the processor type Clusterer.
The log clustering is mainly developed for Syslogs, unstructured and semi-structured logs.
The clusterer calculates a log signature based on the message field.
The log signature is calculated with heuristic and deterministic rules.
The idea of a log signature is to extract a subset of the constant parts of a log and
to delete the dynamic parts.
If the fields syslog.facility and event.severity are in the log, then they are prefixed
to the log signature.

Logs are only clustered if at least one of the following criteria is fulfilled:

..  code-block:: yaml

    Criteria 1: { "message": "A sample message", "tags": ["clusterable", ...], ... }
    Criteria 2: { "message": "A sample message", "clusterable": true, ... }
    Criteria 3: { "message": "A sample message", "syslog": { "facility": <number> }, "event": { "severity": <string> }, ... }

output_field_name
~~~~~~~~~~~~~~~~~

The value `output_field_name` defines in which field results of the clustering should be stored.

--------

Dropper
-------

Parameter
^^^^^^^^^

type
~~~~

The value `dropper` chooses the processor type Dropper.

rules
~~~~~

List of directory paths with rule files, i.e.:

  * /var/git/logprep-rules/dropper_rules/