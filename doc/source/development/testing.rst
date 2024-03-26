=======
Testing
=======

Executing Tests
===============

For testing `pytest` is being used. It is installed with the `requirements_dev.txt` file.

Run acceptance tests with:

..  code-block:: bash

    pytest tests/acceptance --cov=logprep --cov-report=xml -vvv

or unittests with:

..  code-block:: bash

    pytest tests/unit --cov=logprep --cov-report=xml -vvv

Log Messages
============

..  note::
    The log messages are not being evaluated. Thus, the success of error handling will not be checked.
    If an error message appears repeatedly, the cause must be handled manually.

Critical
--------

Logprep could not be started or it will be shut down completely.
The affected instance will not process any more log messages.

Error
-----

A severe error has occurred, but Logprep tries to function with limitations.
This could mean that Logprep keeps running with an old configuration.

Warning
-------

An error has occurred that does not stop Logprep from running, but might impact the performance of Logprep.

Info
----

A notable event occurred, which is not an error.
This could be status information of Logprep.

Debug
-----

More detailed information that can be useful to find errors.
This should be activated only during debugging, since it creates a large amount of log messages.