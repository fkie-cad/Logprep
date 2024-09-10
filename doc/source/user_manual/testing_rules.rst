Testing Rules
=============

.. automodule:: logprep.util.rule_dry_runner
.. automodule:: logprep.util.auto_rule_tester.auto_rule_tester


Custom Tests
------------

Some processors can not be tested with regular auto-tests.
Therefore, it is possible to implement custom tests for these processors.
Processors that use custom tests must have set the instance variable :code:`has_custom_tests` to `True` and they must implement the method :code:`test_rules`.
Custom tests are performed before other auto-tests and they do not require additional test files.
One processor that uses custom tests is the clusterer (see :ref:`rules`).

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
      "pseudonymizer": {
        "pseudonyms": {
          "event_data.param1": "RE_WHOLE_FIELD"
        }
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
      "pseudonymizer": {
        "pseudonyms": {
          "event_data.param1": "RE_WHOLE_FIELD"
        }
      },
      "description": "..."
    },
    {
      "filter": "event_id: 1",
      "pseudonymizer": {
        "pseudonyms": {
          "event_data.param2": "RE_WHOLE_FIELD"
        }
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
