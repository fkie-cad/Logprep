Testing Rules
=============

Dry Run
-------

Rules can be tested by executing them in a dry run of Logprep.
Instead of the connectors defined in the configuration file,
the dry run takes a path parameter to an input JSON (line) file that contains log messages.
The output is displayed in the console and changes made by Logprep are being highlighted:

..  code-block:: bash
    :caption: Directly with Python

    PYTHONPATH="." python3 logprep/run_logprep.py $CONFIG --dry-run $EVENTS

..  code-block:: bash
    :caption: With a PEX file

     logprep.pex $CONFIG --dry-run $EVENTS

Where :code:`$CONFIG` is the path to a configuration file (see :doc:`configuration/configurationdata`).
The only required section in the configuration is :code:`pipeline` (see tests/testdata/config/config-dry-run.yml for an example).
The remaining options are set internally or are being ignored.

:code:`$EVENTS` is the path to a file with one or multiple log messages.
A single log message can be provided with a file containing a plain json or wrapped in brackets
(beginning with `[` and ending with `]`).
For multiple events it must be a list wrapped inside brackets, while each log object separated by a comma.
By specifying the parameter :code:`--dry-run-input-type jsonl` a list of JSON lines can be used instead.
Additional output, like pseudonyms, will be printed if :code:`--dry-run-full-output` is added.

..  code-block:: bash
    :caption: Example for execution with a JSON lines file (dry-run-input-type jsonl) printing all results, including pseudonyms (dry-run-full-output)

    logprep.pex tests/testdata/config/config-dry-run.yml --dry-run tests/testdata/input_logdata/wineventlog_raw.jsonl --dry-run-input-type jsonl --dry-run-full-output

Rule Tests
----------

It is possible to write tests for rules.
In those tests it is possible to define inputs and expected outputs for these inputs.
Only one test file can exist per rule file.
The tests must be located in the same directory as the rule files.
They are identified by naming them like the rule, but ending with `_test.json`.
For example `rule_one.json` and `rule_one_test.json`.

The rule file must contain a JSON list of JSON objects.
Each object corresponds to a test.
They must have the fields `raw` and `processed`.
`raw` contains an input log message and `processed` the corresponding processed result.

When using multi-rules it may be necessary to restrict tests to specific rules in the file.
This can be achieved by the field `target_rule_idx`.
The value of that field corresponds to the index of the rule in the JSON list of multi-rules (starting with 0).

Logprep gets the events in `raw` as input.
The result will be compared with the content of `processed`.

Fields with variable results can be matched via regex expressions by appending `|re` to a field name and using a regex expression as value.
It is furthermore possible to use GROK patterns.
Some patterns are pre-defined, but others can be added by adding a directory with GROK patterns to the configuration file.

The rules get automatically validated if an auto-test is being executed.
The rule tests will be only performed if the validation was successful.

The output is printed to the console, highlighting differences between `raw` and `processed`:

..  code-block:: bash
    :caption: Directly with Python

    PYTHONPATH="." python3 logprep/run_logprep.py $CONFIG --auto-test

..  code-block:: bash
    :caption: With PEX file

     logprep.pex $CONFIG --auto-test

Where :code:`$CONFIG` is the path to a configuration file (see :doc:`configuration/configurationdata`).

Auto-testing does also perform a verification of the pipeline section of the Logprep configuration.

Custom Tests
------------

Some processors can not be tested with regular auto-tests.
Therefore, it is possible to implement custom tests for there processors.
Processors that use custom tests must have set the instance variable :code:`has_custom_tests` to `True` and they must implement the method :code:`test_rules`.
Custom tests are performed before other auto-tests and they do not require additional test files.
One processor that uses custom tests is the clusterer (see :doc:`rule_language`).

Example Tests
-------------

Example Test for a single Rule
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The `raw` value of the test triggers the rule, since the filter matches.
The result of the rule is, as expected, a pseudonymization of `param1`.
The test is successful.

..  code-block:: json
    :linenos:
    :caption: Example - Rule that shall be tested

    [{
      "filter": "event_id: 1 AND source_name: \"Test\"",
      "pseudonymize": {
        "event_data.param1": "RE_WHOLE_FIELD"
      },
      "description": "..."
    }]

..  code-block:: json
    :linenos:
    :caption: Example - Test for one Rule

    [{
      "raw": {
        "event_id": 1,
        "source_name": "Test",
        "event_data.param1": "ANYTHING"
      },
      "processed": {
        "event_id": 1,
        "source_name": "Test",
        "event_data.param1|re": "%{PSEUDONYM}"
      }
    }]

Example Tests for a Multi-Rule
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

With multi-rules it has to be noted that all tests will be performed for all rules in the multi-rule file,
unless restricted via `target_rule_idx`.
In this example the second rule would trigger for both test inputs and fail for the first rule.
Therefore, the test was specified so that it triggers for the appropriate rules and thus succeeds.

..  code-block:: json
    :linenos:
    :caption: Example - Multi-Rule to be tested

    [{
      "filter": "event_id: 1 AND source_name: \"Test\"",
      "pseudonymize": {
        "event_data.param1": "RE_WHOLE_FIELD"
      },
      "description": "..."
    },
    {
      "filter": "event_id: 1",
      "pseudonymize": {
        "event_data.param2": "RE_WHOLE_FIELD"
      },
      "description": "..."
    }]

..  code-block:: json
    :linenos:
    :caption: Example - Test for a Multi-Rule with specified rule indices

    [{
      "target_rule_idx": 0,
      "raw": {
        "event_id": 1,
        "source_name": "Test",
        "event_data.param1": "ANYTHING"
      },
      "processed": {
        "event_id": 1,
        "source_name": "Test",
        "event_data.param1|re": "%{PSEUDONYM}"
      }
    },
    {
      "target_rule_idx": 1,
      "raw": {
        "event_id": 1,
        "event_data.param1": "ANYTHING"
      },
      "processed": {
        "event_id": 1,
        "event_data.param2|re": "%{PSEUDONYM}"
      }
    }]
