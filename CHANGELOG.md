## next release

## Features

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

## Bugfixes

* remove `ujson` dependency because of CVE

