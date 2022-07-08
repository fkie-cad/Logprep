## Next Release

### Features

* Add ability to add fields from SQL Database via in GenericAdder
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
* Fix crashes of the generic adder if sql-based rules are processed without having set the sql config 

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
* Add functionality to generic adder to add data from MySQL tables
* refactor `domain_resolver` to make code cleaner and increase test coverage

### Bugfixes

* remove `ujson` dependency because of CVE

