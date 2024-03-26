Verifying the Configuration
===========================

Verification of the given configruation is automatically performed on starting Logprep.
The following command can be used to verify the configuration without running Logprep:

..  code-block:: bash
    :caption: Directly with Python

    logprep test config $CONFIG

..  code-block:: bash
    :caption: With PEX file

     logprep.pex test config $CONFIG

Where :code:`$CONFIG` is the path to a configuration file (see :ref:`configuration`).
