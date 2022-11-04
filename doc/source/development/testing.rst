=======
Testing
=======

Executing Tests
===============

For testing `tox` is being used.

`Tox` can be installed via the following command:

..  code-block:: bash

    python3 -m pip install tox

By executing :code:`tox` in the root directory of the project a virtual test environment is created in which tests are being executed.

Various test environments have been defined for `tox` that offer additional functionality.
An overview can be obtained via :code:`tox -av`.

Specific test environments can be executed via :code:`tox -e [name of the test environment]`.

**Example:** Acceptance-Tests can be executed with the following command:

..  code-block:: bash

    tox -e acceptance

If something changes in the dependencies, the test environment must be recreated by adding the parameter `-r`.

..  code-block:: bash

    tox -e acceptance -r

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