# Install all packages
install-packages:
    uv sync --frozen --extra dev

# Test all pytests
test:
	uv run pytest ./tests --cov=logprep --cov-report=xml -vvv
