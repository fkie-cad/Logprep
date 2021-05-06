# Build requirements(_dev).txt with pinned package versions from requirements(_dev).in
build-requirements:
	pip-compile requirements.in
	pip-compile requirements_dev.in

# Upgrade pinning in requirements(_dev).txt to newest available versions
upgrade-requirements:
	pip-compile --upgrade requirements.in
	pip-compile --upgrade requirements_dev.in

# Uninstall all packaged that are not present in requirements.txt and install what is in requirements.txt
install-packages:
	pip-sync

# Test in a fresh virtual environment if tests pass with current requirements(_dev).txt
test:
	tox -e all -r