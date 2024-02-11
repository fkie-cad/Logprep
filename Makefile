# Uninstall all packaged that are not present in requirements.txt and install what is in requirements.txt
install-packages:
	pip install .

# Test all pytests
test:
	pytest ./tests --cov=logprep --cov-report=xml -vvv