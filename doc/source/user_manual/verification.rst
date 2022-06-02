Verifying the Configuration
===========================

Verification is automatically performed on starting Logprep.
The following command can be used to verify the configuration without running Logprep:

..  code-block:: bash
    :caption: Directly with Python

    PYTHONPATH="." python3 logprep/run_logprep.py $CONFIG --verify-config

..  code-block:: bash
    :caption: With PEX file

     logprep.pex $CONFIG --verify-config

Where :code:`$CONFIG` is the path to a configuration file (see :doc:`configuration/configurationdata`).
