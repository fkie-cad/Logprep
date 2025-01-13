## Upcoming Changes

## next release
### Breaking
### Features
### Improvements
### Bugfix

## 15.1.0
### Breaking
### Features

* add multiarch container builds for AMD64 and ARM64

### Improvements
### Bugfix

## 15.0.0
### Breaking

* drop support for python 3.10 and add support for python 3.13
* `CriticalInputError` is raised when the input preprocessor values can't be set, this was so far only true
  for the hmac preprocessor, but is now also applied for all other preprocessors.
* fix `delimiter` typo in `StringSplitterRule` configuration
* removed the configuration `tld_lists` in `domain_resolver`, `domain_label_extractor` and `pseudonymizer` as
the list is now fixed inside the packaged logprep
* remove SQL feature from `generic_adder`, fields can only be added from rule config or from file
* use a single rule tree instead of a generic and a specific rule tree
* replace the `extend_target_list` parameter with `merge_with_target` for improved naming clarity
and functionality across `FieldManager` based processors (e.g., `FieldManager`, `Clusterer`,
`GenericAdder`).

### Features

* configuration of `initContainers` in logprep helm chart is now possible

### Improvements

* fix `requester` documentation
* replace `BaseException` with `Exception` for custom errors
* refactor `generic_resolver` to validate rules on startup instead of application of each rule
* regex pattern lists for the `generic_resolver` are pre-compiled
* regex matching from lists in the `generic_resolver` is cached
* matching in the `generic_resolver` can be case-insensitive
* rewrite the helper method `add_field_to` such that it always raises an `FieldExistsWarning` instead of return a bool.
* add new helper method `add_fields_to` to directly add multiple fields to one event
* refactored some processors to make use of the new helper methods
* add `pre-commit` hooks to the repository, install new dev dependency and run `pre-commit install` in the root dir
* the default `securityContext`for the pod is now configurable
* allow `TimeParser` to get the current time with a specified timezone instead of always using local time and setting the timezone to UTC
* remove `tldextract` dependency
* remove `urlextract` dependency
* fix wrong documentation for `timestamp_differ`
* add container signatures to images build in ci pipeline
* add sbom to images build in ci pipeline
* `FieldManager` supports merging dictionaries

### Bugfix

* fix `confluent_kafka.store_offsets` if `last_valid_record` is `None`, can happen if a rebalancing happens
  before the first message was pulled.
* fix pseudonymizer cache metrics not updated
* fix incorrect timezones for log arrival time and delta time in input preprocessing
* fix `_get_value` in `FilterExpression` so that keys don't match on values
* fix `auto_rule_tester` to work with `LOGPREP_BYPASS_RULE_TREE` enabled
* fix `opensearch_output` not draining `message_backlog` on shutdown
* silence `FieldExists` warning in metrics when `LOGPREP_APPEND_MEASUREMENT_TO_EVENT` is active

## 14.0.0
### Breaking

* remove AutoRuleCorpusTester
* removes the option to use synchronous `bulk` or `parallel_bulk` operation in favor of `parallel_bulk` in `opensearch_output`
* reimplement error handling by introducing the option to configure an error output
  * if no error output is configured, failed event will be dropped

### Features

* adds health check endpoint to metrics on path `/health`
* changes helm chart to use new readiness check
* adds `healthcheck_timeout` option to all components to tweak the timeout of healthchecks
* adds `desired_cluster_status` option to opensearch output to signal healthy cluster status
* initially run health checks on setup for every configured component
* make `imagePullPolicy` configurable for helm chart deployments
* it is now possible to use Lucene compliant Filter Expressions
* make `terminationGracePeriodSeconds` configurable in helm chart values
* adds ability to configure error output
* adds option `default_op_type` to `opensearch_output` connector to set the default operation for indexing documents (default: index)
* adds option `max_chunk_bytes` to `opensearch_output` connector to set the maximum size of the request in bytes (default: 100MB)
* adds option `error_backlog_size` to logprep configuration to configure the queue size of the error queue
* the opensearch default index is now only used for processed events, errors will be written to the error output, if configured

### Improvements

* remove AutoRuleCorpusTester
* adds support for rust extension development
* adds prebuilt wheels for architectures `x86_64` on `manylinux` and `musllinux` based linux platforms to releases
* add manual how to use local images with minikube example setup to documentation
* move `Configuration` to top level of documentation
* add `CONTRIBUTING` file
* sets the default for `flush_timeout` and `send_timeout` in `kafka_output` connector to `0` seconds
* changed python base image for logprep to `bitnami/python` in cause of better CVE governance

### Bugfix

* ensure `logprep.abc.Component.Config` is immutable and can be applied multiple times
* remove lost callback reassign behavior from `kafka_input` connector
* remove manual commit option from `kafka_input` connector
* pin `mysql-connector-python` to >=9.1.0 to accommodate for CVE-2024-21272 and update `MySQLConnector` to work with the new version

## 13.1.2
### Bugfix

* fixes a bug not increasing but decreasing timeout throttle factor of ThrottlingQueue
* handle DecodeError and unexpected Exceptions on requests in `http_input` separately
* fixes unbound local error in http input connector

## 13.1.1
### Improvements

* adds ability to bypass the processing of events if there is no pipeline. This is useful for pure connector deployments.
* adds experimental feature to bypass the rule tree by setting `LOGPREP_BYPASS_RULE_TREE` environment variable

### Bugfix

* fixes a bug in the `http_output` used by the http generator, where the timeout parameter does only set the read_timeout not the write_timeout
* fixes a bug in the `http_input` not handling decode errors

## 13.1.0
### Features

* `pre_detector` now normalizes timestamps with configurable parameters timestamp_field, source_format, source_timezone and target_timezone
* `pre_detector` now writes tags in failure cases
* `ProcessingWarnings` now can write `tags` to the event
* add `timeout` parameter to logprep http generator to set the timeout in seconds for requests
* add primitive rate limiting to `http_input` connector

### Improvements

* switch to `uvloop` as default loop for the used threaded http uvicorn server
* switch to `httptools` as default http implementation for the used threaded http uvicorn server

### Bugfix

* remove redundant chart features for mounting secrets

## 13.0.1

### Improvements

* a result object was added to processors and pipelines
  * each processor returns an object including the processor name, generated extra_data, warnings
    and errors
  * the pipeline returns an object with the list of all processor result objects
* add kubernetes opensiem deployment example
* move quickstart setup to compose example

### Bugfix

* This release limits the mysql-connector-python dependency to have version less the 9

## 13.0.0

### Breaking

* This release limits the maximum python version to `3.12.3` because of the issue
[#612](https://github.com/fkie-cad/Logprep/issues/612).
* Remove `normalizer` processor, as it's functionality was replaced by the `grokker`, `timestamper` and `field_manager` processors
* Remove `elasticsearch_output` connector to reduce maintenance effort

### Features

* add a helm chart to install logprep in kubernetes based environments

### Improvements

* add documentation about behavior of the `timestamper` on `ISO8601` and `UNIX` time parsing
* add unit tests for helm chart templates
* add helm to github actions runner
* add helm chart release to release pipeline

### Bugfix

* fixes a bug where it could happen that a config value could be overwritten by a default in a later configuration in a multi source config scenario
* fixes a bug in the `field_manager` where extending a non list target leads to a processing failure
* fixes a bug in `pseudonymizer` where a missing regex_mapping from an existing config_file causes logprep to crash continuously

## 12.0.0

### Breaking

* `pseudonymizer` change rule config field `pseudonyms` to `mapping`
* `clusterer` change rule config field `target` to `source_fields`
* `generic_resolver` change rule config field `append_to_list` to `extend_target_list`
* `hyperscan_resolver` change rule config field `append_to_list` to `extend_target_list`
* `calculator` now adds the error tag `_calculator_missing_field_warning` to the events tag field instead of `_calculator_failure` in case of missing field in events
* `domain_label_extractor` now writes `_domain_label_extractor_missing_field_warning` tag to event tags in case of missing fields
* `geoip_enricher` now writes `_geoip_enricher_missing_field_warning` tag to event tags in case of missing fields
* `grokker` now writes `_grokker_missing_field_warning` tag to event tags instead of `_grokker_failure` in case of missing fields
* `requester` now writes `_requester_missing_field_warning` tag to event tags instead of `_requester_failure` in case of missing fields
* `timestamp_differ` now writes `_timestamp_differ_missing_field_warning` tag to event tags instead of `_timestamp_differ_failure` in case of missing fields
* `timestamper` now writes `_timestamper_missing_field_warning` tag to event tags instead of `_timestamper_failure` in case of missing fields
* rename `--thread_count` parameter to `--thread-count` in http generator
* removed `--report` parameter and feature from http generator
* when using `extend_target_list` in the `field manager`the ordering of the given source fields is now preserved
* logprep now exits with a negative exit code if pipeline restart fails 5 times
  * this was implemented because further restart behavior should be configured on level of a system init service or container orchestrating service like k8s
  * the `restart_count` parameter is configurable. If you want the old behavior back, you can set this parameter to a negative number
* logprep now exits with a exit code of 2 on configuration errors

### Features

* add UCL into the quickstart setup
* add logprep http output connector
* add pseudonymization tools to logprep -> see: `logprep pseudo --help`
* add `restart_count` parameter to configuration
* add option `mode` to `pseudonymizer` processor and to pseudonymization tools to chose the AES Mode for encryption and decryption
* add retry mechanism to opensearch parallel bulk, if opensearch returns 429 `rejected_execution_exception`

### Improvements

* remove logger from Components and Factory signatures
* align processor architecture to use methods like `write_to_target`, `add_field_to` and `get_dotted_field_value` when reading and writing from and to events
  * required substantial refactoring of the `hyperscan_resolver`, `generic_resolver` and `template_replacer`
* change `pseudonymizer`, `pre_detector`, `selective_extractor` processors and `pipeline` to handle `extra_data` the same way
* refactor `clusterer`, `pre_detector` and `pseudonymizer` processors and change `rule_tree` so that the processor do not require `process` override
  * required substantial refactoring of the `clusterer`
* handle missing fields in processors via `_handle_missing_fields` from the field_manager
* add `LogprepMPQueueListener` to outsource logging to a separate process
* add a single `Queuehandler` to root logger to ensure all logs were handled by `LogprepMPQueueListener`
* refactor `http_generator` to use a logprep http output connector
* ensure all `cached_properties` are populated during setup time

### Bugfix

* make `--username` and `--password` parameters optional in http generator
* fixes a bug where `FileNotFoundError` is raised during processing

## 11.3.0

### Features

* add gzip handling to `http_input` connector
* adds advanced logging configuration
  * add configurable log format
  * add configurable datetime formate in logs
  * makes `hostname` available in custom log formats
  * add fine grained log level configuration for every logger instance

### Improvements

* rename `logprep.event_generator` module to `logprep.generator`
* shorten logger instance names

### Bugfix

* fixes exposing OpenSearch/ElasticSearch stacktraces in log when errors happen by making loglevel configurable for loggers `opensearch` and `elasticsearch`
* fixes the logprep quickstart profile

## 11.2.1

### Bugfix

* fixes bug, that leads to spawning exporter http server always on localhost

## 11.2.0

### Features

* expose metrics via uvicorn webserver
  * makes all uvicorn configuration options possible
  * add security best practices to server configuration
* add following metrics to `http_input` connector
  * `nummer_of_http_requests`
  * `message_backlog_size`

### Bugfix

* fixes a bug in grokker rules, where common field prefixes wasn't possible
* fixes bug where missing key in credentials file leads to AttributeError

## 11.1.0

### Features

* new documentation part with security best practices which compiles to `user_manual/security/best_practices.html`
  * also comes with excel export functionality of given best practices
* add basic auth to http_input

### Bugfix

* fixes a bug in http connector leading to only first process working
* fixes the broken gracefull shutdown behaviour

## 11.0.1
### Bugfix

* fixes a bug where the pipeline index increases on every restart of a failed pipeline
* fixes closed log queue issue by run logging in an extra process

## 11.0.0
### Breaking

* configuration of Authentication for getters is now done by new introduced credentials file

### Features

* introducing an additional file to define the credentials for every configuration source
* retrieve oauth token automatically from different oauth endpoints
* retrieve configruation with mTLS authentication
* reimplementation of HTTP Input Connector with following Features:
  * Wildcard based HTTP Request routing
  * Regex based HTTP Request routing
  * Improvements in thread-based runtime
  * Configuration and possibility to add metadata

### Improvements

* remove `versioneer` dependency in favor of `setuptools-scm`

### Bugfix

* fix version string of release versions
* fix version string of container builds for feature branches
* fix merge of config versions for multiple configs


## v10.0.4
### Improvements

* refactor logprep build process and requirements management

### Bugfix

* fix `generic_adder` not creating new field from type `list`

## v10.0.3
### Bugfix
* fix loading of configuration inside the `AutoRuleCorpusTester` for `logprep test integration`
* fix auto rule tester (`test unit`), which was broken after adding support for multiple configuration files and resolving paths in configuration files

## v10.0.2
### Bugfix
* fix versioneer import
* fix logprep does not complain about missing PROMETHEUS_MULTIPROC_DIR

## v10.0.1
### Bugfix

* fix entrypoint in `setup.py` that corrupted the install


## v10.0.0
### Breaking

* reimplement the logprep CLI, see `logprep --help` for more information.
* remove feature to reload configuration by sending signal `SIGUSR1`
* remove feature to validate rules because it is already included in `logprep test config`

### Features

* add a `number_of_successful_writes` metric to the s3 connector, which counts how many events were successfully written to s3
* make the s3 connector work with the new `_write_backlog` method introduced by the `confluent_kafka` commit bugfix in v9.0.0
* add option to Opensearch Output Connector to use parallel bulk implementation (default is True)
* add feature to logprep to load config from multiple sources (files or uris)
* add feature to logprep to print the resulting configruation with `logprep print json|yaml <Path to config>` in json or yaml
* add an event generator that can send records to Kafka using data from a file or from Kafka
* add an event generator that can send records to a HTTP endpoint using data from local dataset

### Improvements

* a do nothing option do dummy output to ensure dummy does not fill memory
* make the s3 connector raise `FatalOutputError` instead of warnings
* make the s3 connector blocking by removing threading
* revert the change from v9.0.0 to always check the existence of a field for negated key-value based lucene filter expressions
* make store_custom in s3, opensearch and elasticsearch connector not call `batch_finished_callback` to prevent data loss that could be caused by partially processed events
* remove the `schema_and_rule_checker` module
* rewrite Logprep Configuration object see documentation for more details
* rewrite Runner
* delete MultiProcessingPipeline class to simplify multiprocesing
* add FDA to the quickstart setup
* bump versions for `fastapi` and `aiohttp` to address CVEs

### Bugfix

* make the s3 connector actually use the `max_retries` parameter
* fixed a bug which leads to a `FatalOutputError` on handling `CriticalInputError` in pipeline

## v9.0.3
### Breaking

### Features

* make `thread_count`, `queue_size` and `chunk_size` configurable for `parallel_bulk` in opensearch output connector

### Improvements

### Bugfix

* fix `parallel_bulk` implementation not delivering messages to opensearch

## v9.0.2

### Bugfix

* remove duplicate pseudonyms in extra outputs of pseudonymizer

## v9.0.1
### Breaking

### Features

### Improvements

* use parallel_bulk api for opensearch output connector

### Bugfix


## v9.0.0
### Breaking

* remove possibility to inject auth credentials via url string, because of the risk leaking credentials in logs
    - if you want to use basic auth, then you have to set the environment variables
        * :code:`LOGPREP_CONFIG_AUTH_USERNAME=<your_username>`
        * :code:`LOGPREP_CONFIG_AUTH_PASSWORD=<your_password>`
    - if you want to use oauth, then you have to set the environment variables
        * :code:`LOGPREP_CONFIG_AUTH_TOKEN=<your_token>`
        * :code:`LOGPREP_CONFIG_AUTH_METHOD=oauth`

### Features

### Improvements

* improve error message on empty rule filter
* reimplemented `pseudonymizer` processor
  - rewrote tests till 100% coverage
  - cleaned up code
  - reimplemented caching using pythons `lru_cache`
  - add cache metrics
  - removed `max_caching_days` config option
  - add `max_cached_pseudonymized_urls` config option which defaults to 1000
  - add lru caching for peudonymizatin of urls
* improve loading times for the rule tree by optimizing the rule segmentation and sorting
* add support for python 3.12 and remove support for python 3.9
* always check the existence of a field for negated key-value based lucene filter expressions
* add kafka exporter to quickstart setup

### Bugfix

* fix the rule tree parsing some rules incorrectly, potentially resulting in more matches
* fix `confluent_kafka` commit issue after kafka did some rebalancing, fixes also negative offsets

## v8.0.0
### Breaking

* reimplemented metrics so the former metrics configuration won't work anymore
* metric content changed and existent grafana dashboards will break
* new rule `id` could possibly break configurations if the same rule is used in both rule trees
  - can be fixed by adding a unique `id` to each rule or delete the possibly redundant rule

### Features

* add possibility to convert hex to int in `calculator` processor with new added function `from_hex`
* add metrics on rule level
* add grafana example dashboards under `examples/exampledata/config/grafana/dashboards`
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
