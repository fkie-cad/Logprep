Validating Rules
================

The following command can be used to validate the rules:

..  code-block:: bash
    :caption: Directly with Python

    PYTHONPATH="." python3 logprep/run_logprep.py $CONFIG --validate-rules

..  code-block:: bash
    :caption: With PEX file

     logprep.pex $CONFIG --validate-rules

The paths to the rules that will be validated are found in :code:`$CONFIG` under each processor entry.
Where :code:`$CONFIG` is the path to a configuration file (see :doc:`configuration/configurationdata`).