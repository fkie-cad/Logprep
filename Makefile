# Install all packages
install-packages:
	pip install -e .[dev]

# Test all pytests
test:
	pytest ./tests --cov=logprep --cov-report=xml -vvv
