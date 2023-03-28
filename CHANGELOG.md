## Upcoming Changes

## next release

### Features

* Add `amides` processor to extends conventional rule matching by applying machine learning components
* Add feature to all rule filters to match against specific elements in lists

### Improvements

* refactor `FilterExpressions`, `RuleTree`, `RuleParser`
* use `get_dotted_field` function in `FilterExpressions`
* change behavior of `RuleTree` that it won't return rules for empty documents

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
* `Normalizer` writes failure tags if nomalization fails
* Add `flush_timeout` to `opensearch` and `elasticsearch` outputs to ensure message delivery within a configurable period

### Improvements

* Bump `attrs` to `>=22.2.0` and delete redundant `min_len_validator`
* Specify the metric labels for connectors (add name, type and direction as labels)
* Rename metric names to clarify their meanings (`logprep_pipeline_number_of_warnings` to
`logprep_pipeline_sum_of_processor_warnings` and `logprep_pipeline_number_of_errors` to
`logprep_pipeline_sum_of_processor_errors`)
* Harmonize error messages and handling for processors and connectors
* Add ability to schedule periodic tasks to all components

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

