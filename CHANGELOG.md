## Upcoming Changes


## Next Release
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
* Add concatenator processor that can combine multiple source fields
* Add a dissecter processor that tokinize messages into new or existing fields

### Improvements
* Validate connector config on class level via attrs classes
* Implement a common interface to all connectors
* Refactor connector code
* Revise the documentation
* Add sphinxcontrib.datatemplates and testcase-renderer to docs

### Bugfixes
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

