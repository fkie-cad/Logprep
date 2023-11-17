## Upcoming Changes

## next release
### Breaking

### Features

### Improvements

### Bugfix


## v8.0.0
### Breaking

* reimplemented metrics so the former metrics configuration won't work anymore
* metric content changed and existent grafana dashboards will break
* new rule `id` could possibly break configurations if the same rule is used in both rule trees
  - can be fixed by adding a unique `id` to each rule or delete the possibly redundant rule

### Features

* add possibility to convert hex to int in `calculator` processor with new added function `from_hex`
* add metrics on rule level
* add grafana example dashboards under `quickstart/exampledata/config/grafana/dashboards`
* add new configuration field `id` for all rules to identify rules in metrics and logs
  - if no `id` is given, the `id` will be generated in a stable way
  - add verification of rule `id` uniqueness on processor level over both rule trees to ensure metrics are counted correctly on rule level

### Improvements

* reimplemented prometheus metrics exporter to provide gauges, histograms and counter metrics
* removed shared counter, because it is redundant to the metrics
* get exception stack trace by setting environment variable `DEBUG`

### Bugfix

## v7.0.0
### Breaking

* removed metric file target
* move kafka config options to `kafka_config` dictionary for `confluent_kafka_input` and `confluent_kafka_output` connectors

### Features

* add a preprocessor to enrich by systems env variables
* add option to define rules inline in pipeline config under processor configs `generic_rules` or `specific_rules`
* add option to `field_manager` to ignore missing source fields to suppress warnings and failure tags
* add ignore_missing_source_fields behavior to `calculator`, `concatenator`, `dissector`, `grokker`, `ip_informer`, `selective_extractor`
* kafka input connector
  - implemented manual commit behaviour if `enable.auto.commit: false`
  - implemented on_commit callback to check for errors during commit
  - implemented statistics callback to collect metrics from underlying librdkafka library
  - implemented per partition offset metrics
  - get logs and handle errors from underlying librdkafka library
* kafka output connector
  - implemented statistics callback to collect metrics from underlying librdkafka library
  - get logs and handle errors from underlying librdkafka library

### Improvements

* `pre_detector` processor now adds the field `creation_timestamp` to pre-detections. 
It contains the time at which a pre-detection was created by the processor.
* add `prometheus` and `grafana` to the quickstart setup to support development
* provide confluent kafka test setup to run tests against a real kafka cluster

### Bugfix

* fix CVE-2023-37920 Removal of e-Tugra root certificate
* fix CVE-2023-43804 `Cookie` HTTP header isn't stripped on cross-origin redirects
* fix CVE-2023-37276 aiohttp.web.Application vulnerable to HTTP request smuggling via llhttp HTTP request parser

## v6.8.1
### Bugfix

* Fix writing time measurements into the event after the deleter has deleted the event. The bug only
happened when the `metrics.measure_time.append_to_event` configuration was set to `true`.

* Fix memory leak by removing the log aggregation capability

## v6.8.0
### Features

* Add option to repeat input documents for the following connectors: `DummyInput`, `JsonInput`,
`JsonlInput`. This enables easier debugging by introducing a continues input stream of documents.

### Bugfix

* Fix restarting of logprep every time the kafka input connector receives events that aren't valid
json documents. Now the documents will be written to the error output.
* Fix ProcessCounter to actually print counts periodically and not only once events are processed

## v6.7.0
### Improvements

* Print logprep warnings in the rule corpus tester only in the detailed reports instead of the
summary.

### Bugfix

* Fix error when writing too large documents into Opensearch/Elasticsearch
* Fix dissector pattern that end with a dissect, e.g `system_%{type}`
* Handle long-running grok pattern in the `Grokker` by introducing a timeout limit of one second
* Fix time handling: If no year is given assume the current year instead of 1900 and convert time
zone only once

## v6.6.0

### Improvements

* Replace rule_filter with lucene_filter in predetector output. The old internal logprep rule 
representation is not present anymore in the predetector output, the name `rule_filter` will stay
in place of the `lucene_filter` name.
* 'amides' processor now stores confidence values of processed events in the `amides.confidence` field.
In case of positive detection results, rule attributions are now inserted in the `amides.attributions` field.

### Bugfix

* Fix lucene rule filter representation such that it is aligned with opensearch lucene query syntax
* Fix grok pattern `UNIXPATH` by internally converting `[[:alnum:]]` to `\w"`
* Fix overwriting of temporary tld-list with empty content

## v6.5.1
### Bugfix

* Fix creation of logprep temp dir 
* Fix `dry_runner` to support extra outputs of the `selective_extractor`

## v6.5.0
### Improvements

* Make the `PROMETHEUS_MULTIPROC_DIR` environment variable optional, will default to
`/tmp/PROMETHEUS_MULTIPROC_DIR` if not given

### Bugfix

* All temp files will now be stored inside the systems default temp directory 

## v6.4.0
### Improvements

* Bump `requests` to `>=2.31.0` to circumvent `CVE-2023-32681`
* Include a lucene representation of the rule filter into the predetector results. The
representation is not completely lucene compatible due to non-existing regex functionality.
* Remove direct dependency of `python-dateutil`

### Bugfix

* Fix error handling of FieldManager if no mapped source field exists in the event.
* Fix Grokker such that only the first grok pattern match is applied instead of all matching
pattern
* Fix Grokker such that nested parentheses in oniguruma pattern are working (3 levels are supported
now)
* Fix Grokker such that two or more oniguruma can point to the same target. This ensures
grok-pattern compatibility with the normalizer and other grok tools

## v6.3.0
### Features

* Extend dissector such that it can trim characters around dissected field with `%{field-( )}`
notation.
* Extend timestamper such that it can take multiple source_formats. First format that matches
will be used, all following formats will be ignored
 
### Improvements

* Extend the `FieldManager` such that it can move/copy multiple source fields into multiple targets
inside one rule.

### Bugfix

* Fix error handling of missing source fields in grokker
* Fix using same output fields in list of grok pattern in grokker

## v6.2.0

### Features
* add `timestamper` processor to extract timestamp functionality from normalizer

### Improvements
* removed `arrow` dependency and depending features for performance reasons
  * switched to `datetime.strftime` syntax in `timestamp_differ`, `s3_output`, `elasticsearch_output` and `opensearch_output`
* encapsulate time related functionality in `logprep.util.time.TimeParser`


### Bugfix
* Fix missing default grok patterns in packaged logprep version


## v6.1.0

### Features

* Add `amides` processor to extends conventional rule matching by applying machine learning components
* Add `grokker` processor to extract grok functionality from normalizer
* `Normalizer` writes failure tags if nomalization fails
* Add `flush_timeout` to `opensearch` and `elasticsearch` outputs to ensure message delivery within a configurable period
* add `kafka_config` option to `confluent_kafka_input` and `confluent_kafka_output` connectors to provide additional config options to `librdkafka`

### Improvements

* Harmonize error messages and handling for processors and connectors
* Add ability to schedule periodic tasks to all components
* Improve performance of pipeline processing by switching form builtin `json` to `msgspec` in pipeline and kafka connectors
* Rewrite quickstart setup:
  * Remove logstash, replace elasticsearch by opensearch and use logprep opensearch connector to stick to reference architecture
  * Use kafka without zookeeper and switch to bitnami container images

### Bugfix

* Fix resetting processor caches in the `auto_rule_corpus_tester` by initializing all processors
between test cases.
* Fix processing of generic rules after there was an error inside the specific rules.
* Remove coordinate fields from results of the geoip enricher if one of them has `None` values

## v6.0.0

## Breaking

* Remove rules deprecations introduced in `v4.0.0`
* Changes rule language of `selective_extractor`, `pseudonymizer`, `pre_detector` to support multiple outputs

### Features

* Add `string_splitter` processor to split strings of variable length into lists
* Add `ip_informer` processor to enrich events with ip information
* Allow running the `Pipeline` in python without input/output connectors
* Add `auto_rule_corpus_tester` to test a whole rule corpus against defined expected outputs.
* Add shorthand for converting datatypes to `dissector` dissect pattern language
* Add support for multiple output connectors
* Apply processors multiple times until no new rule matches anymore. This enables applying rules on 
results of previous rules.

### Improvements

* Bump `attrs` to `>=22.2.0` and delete redundant `min_len_validator`
* Specify the metric labels for connectors (add name, type and direction as labels)
* Rename metric names to clarify their meanings (`logprep_pipeline_number_of_warnings` to
`logprep_pipeline_sum_of_processor_warnings` and `logprep_pipeline_number_of_errors` to
`logprep_pipeline_sum_of_processor_errors`)

### Bugfix

* Fixes a bug that breaks templating config and rule files with environment variables if one or more variables are not set in environment
* Fixes a bug for `opensearch_output` and `elasticsearch_output` not handling authentication issues
* Fix metric `logprep_pipeline_number_of_processed_events` to actually count the processed events per pipeline
* Fix a bug for enrichment with environment variables. Variables must have one of the following prefixes now: `LOGPREP_`, `CI_`, `GITHUB_` or `PYTEST_`

### Improvements

* reimplements the `selective_extractor`

## v5.0.1

### Breaking

* drop support for python `3.6`, `3.7`, `3.8`
* change default prefix behavior on appending to strings of `dissector`

### Features

* Add an `http input connector` that spawns a uvicorn server which parses requests content to events.
* Add an `file input connector` that reads generic logfiles.
* Provide the possibility to consume lists, rules and configuration from files and http endpoints
* Add `requester` processor that enriches by making http requests with field values
* Add `calculator` processor to calculate with or without field values
* Make output subfields of the `geoip_enricher` configurable by introducing the rule config
`customize_target_subfields`
* Add a `timestamp_differ` processor that can parse two timestamps and calculate their respective time delta.
* Add `config_refresh_interval` configuration option to refresh the configuration on a given timedelta
* Add option to `dissector` to use a prefix pattern in dissect language for appending to strings and add the default behavior to append to strings without any prefixed separator

### Improvements

* Add support for python `3.10` and `3.11`
* Add option to submit a template with `list_search_base_path` config parameter in `list_comparison` processor
* Add functionality to `geoip_enricher` to download the geoip-database
* Add ability to use environment variables in rules and config
* Add list access including slicing to dotted field notation for getting values
* Add processor boilerplate generator to help adding new processors

### Bugfixes

* Fix count of `number_of_processed_events` metric in `input` connector. Will now only count actual
events.

## v4.0.0
### Breaking

* Splitting the general `connector` config into `input` and `output` to compose connector config independendly
* Removal of Deprecated Feature: HMAC-Options in the connector consumer options have to be 
under the subkey `preprocessing` of the `input` processor
* Removal of Deprecated Feature: `delete` processor was renamed to `deleter`
* Rename `writing_output` connector to `jsonl_output`

### Features

* Add an opensearch output connector that can be used to write directly into opensearch.
* Add an elasticsearch output connector that can be used to write directly into elasticsearch.
* Split connector config into seperate config keys `input` and `output`
* Add preprocessing capabillities to all input connectors
* Add preprocessor for log_arrival_time
* Add preprocessor for log_arrival_timedelta
* Add metrics to connectors
* Add `concatenator` processor that can combine multiple source fields
* Add `dissector` processor that tokinizes messages into new or existing fields
* Add `key_checker` processor that checks if all dotted fields from a list are present in the event
* Add `field_manager` processor that copies or moves fields and merges lists
* Add ability to delete source fields to `concatenator`, `datetime_extractor`, `dissector`, `domain_label_extractor`, `domain_resolver`, `geoip_enricher` and `list_comparison`
* Add ability to overwrite target field to `datetime_extractor`, `domain_label_extractor`, `domain_resolver`, `geoip_enricher` and `list_comparison`

### Improvements
* Validate connector config on class level via attrs classes
* Implement a common interface to all connectors
* Refactor connector code
* Revise the documentation
* Add `sphinxcontrib.datatemplates` and `testcase-renderer` to docs
* Reimplement `get_dotted_field_value` helper method which should lead to increased performance
* Reimplement `dropper` processor code to improve performance

### Deprecations

#### Rule Language

* `datetime_extractor.datetime_field` is deprecated. Use `datetime_extractor.source_fields` as list instead.
* `datetime_extractor.destination_field` is deprecated. Use `datetime_extractor.target_field` instead.
* `delete` is deprecated. Use `deleter.delete` instead.
* `domain_label_extractor.target_field` is deprecated. Use `domain_label_extractor.source_fields` as list instead.
* `domain_label_extractor.output_field` is deprecated. Use `domain_label_extractor.target_field` instead.
* `domain_resolver.source_url_or_domain` is deprecated. Use `domain_resolver.source_fields` as list instead.
* `domain_resolver.output_field` is deprecated. Use `domain_resolver.target_field` instead.
* `drop` is deprecated. Use `dropper.drop` instead.
* `drop_full` is deprecated. Use `dropper.drop_full` instead.
* `geoip_enricher.source_ip` is deprecated. Use `geoip_enricher.source_fields` as list instead.
* `geoip_enricher.output_field` is deprecated. Use `geoip_enricher.target_field` instead.
* `label` is deprecated. Use `labeler.label` instead.
* `list_comparison.check_field` is deprecated. Use `list_comparison.source_fields` as list instead.
* `list_comparison.output_field` is deprecated. Use `list_comparison.target_field` instead.
* `pseudonymize` is deprecated. Use `pseudonymizer.pseudonyms` instead.
* `url_fields is` deprecated. Use `pseudonymizer.url_fields` instead.


### Bugfixes

* Fix resetting of some metric, e.g. `number_of_matches`.

### Breaking

## v3.3.0

### Features

* Normalizer can now write grok failure fields to an event when no grok pattern matches and if 
`failure_target_field` is specified in the configuration

### Bugfixes

* Fix config validation of the preprocessor `version_info_target_field`.

## v3.2.0

### Features

* Add feature to automatically add version information to all events, configured via the 
`connector > consumer > preprocessing` configuration
* Expose logprep and config version in metric targets
* Dry-Run accepts now a single json without brackets for input type `json` 

### Improvements

* Move the config hmac options to the new subkey `preprocessing`, maintain backward compatibility, 
but mark old version as deprecated.
* Make the generic adder write the SQL table to a file and load it from there instead of loading it 
from the database for every process of the multiprocessing pipeline.
Furthermore, only connect to the SQL database on checking if the database table has changed and the 
file is stale.
This reduces the SQL connections.
Before, there was permanently one connection per multiprocessing pipeline active and now there is 
only one connection per Logprep instance active when accessing the database. 

### Bugfixes

* Fix SelectiveExtractor output. The internal extracted list wasn't cleared between each event, 
leading to duplication in the output of the processor. Now the events are cleared such that only
the result of the current event is returned.

## v3.1.0

### Features

* Add metric for mean processing time per event for the full pipeline, in addition to per processor

### Bugfixes

* Fix performance of the metrics tracking. Due to a store metrics statement at the wrong position
the logprep performance was dramatically decreased when tracking metrics was activated.
* Fix Auto Rule Tester which tried to access processor stats that do not exist anymore. 

## v3.0.0

### Features

* Add ability to add fields from SQL database via GenericAdder
* Prometheus Exporter now exports also processor specific metrics
* Add `--version` cli argument to print the current logprep version, as well as the configuration
version if found

### Improvements

* Automatically release logprep on pypi
* Configure abstract dependencies for pypi releases
* Refactor domain resolver
* Refactor `processor_stats` to `metrics`. Metrics are now collected in separate dataclasses

### Bugfixes

* Fix processor initialization in auto rule tester
* Fix generation of RST-Docs

### Breaking 

* Metrics refactoring: 
  * The json output format of the previously known status_logger has changed
  * The configuration key word is now `metrics` instead of `status_logger`
  * The configuration for the time measurement is now part of the metrics configuration
  * The metrics tracking still includes values about how many warnings and errors happened, but 
  not of what type. For that the regular logprep logging should be consolidated.

## v2.0.1

### Bugfixes

* Clear matching rules before processing in clusterer
* Add missing sphinxcontrib-mermaid in tox.ini

## v2.0.0

### Features

* Add generic processor interface `logprep.abc.processor.Processor`
* Add `delete` processor to be used with rules.
* Delete `donothing` processor
* Add `attrs` based `Config` classes for each processor
* Add validation of processor config in config class
* Make all processors using python `__slots__`
* Add `ProcessorRegistry` to register all processors
* Remove plugins feature
* Add `ProcessorConfiguration` as an adapter to create configuration for processors
* Remove all specific processor factories in favor of `logprep.processor.processor_factory.ProcessorFactory`
* Rewrite `ProcessorFactory`
* Automate processor configuration documentation
* generalize config parameter for using tld lists to `tld_lists` for `domain_resolver`, `domain_label_extractor`, `pseudonymizer`
* refactor `domain_resolver` to make code cleaner and increase test coverage

### Bugfixes

* remove `ujson` dependency because of CVE

