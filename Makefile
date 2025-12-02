# Install all packages
install-packages:
	uv pip install -e .[dev]

# Test all pytests
test:
	pytest ./tests --cov=logprep --cov-report=xml -vvv
