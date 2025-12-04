# Install all packages
install-packages:
    uv sync --extra dev

# Test all pytests
test:
	pytest ./tests --cov=logprep --cov-report=xml -vvv
