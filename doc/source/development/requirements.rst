Python Packages
===============

The used Python packages in requirements.txt and requirements_dev.txt should be always in a state that ensures a functioning installation of Logprep.
To achieve this, package versions are being pinned for a tested state.

Pinning of Python Packages
--------------------------

:code:`pip-tools` is used for the pinning process.
It should be installed in a virtual Python environment.

The Python packages that are being used are defined in requirements.in and requirements_dev.in.
Only packages that must be necessarily pinned should be pinned within those files.
By using :code:`pip-compile` of :code:`pip-tools` the .in files can be used to generate the requirements.txt and the requirements_dev.txt.
All packages in those generated files will be pinned.

Versions Upgrade of Python Packages
-----------------------------------

Pinned package versions in requirements(_dev).txt can be updated via :code:`pip-compile --upgrade`.
After updating the packages :code:`pip-sync` should be executed.
It removes all unused packages from the current virtual Python environment and then installs the requirements.
pip-tools itself should be installed in the virtual environment and not globally.
The updated requirements can be committed if all tests were successful.

Helper Scripts
--------------

A Makefile simplifies this process.
:code:`make` must be present on the system.
It might have to be installed (i.e. via :code:`build-essential`).
requirements(_dev).txt can be build with :code:`make build-requirements`.
:code:`make upgrade-requirements` updates requirements(_dev).txt.
Executing :code:`make install-packages` runs pip-sync.
:code:`make test` creates a new virtual test environment, installs all requirements and runs all tests.
