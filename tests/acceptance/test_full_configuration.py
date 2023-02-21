# pylint: disable=missing-docstring
from pathlib import Path
import re
from tests.acceptance.util import (
    get_full_pipeline,
    get_default_logprep_config,
    start_logprep,
    stop_logprep,
    convert_to_http_config,
    HTTPServerForTesting,
)
from logprep.util.json_handling import dump_config_as_file


def teardown_function():
    Path("generated_config.yml").unlink(missing_ok=True)
    stop_logprep()


def test_start_of_logprep_with_full_configuration_from_file(tmp_path):
    pipeline = get_full_pipeline()
    config = get_default_logprep_config(pipeline, with_hmac=False)
    config.get("output").update({"kafka": {"type": "dummy_output", "default": False}})
    config_path = str(tmp_path / "generated_config.yml")
    dump_config_as_file(config_path, config)
    proc = start_logprep(config_path)
    output = proc.stdout.readline().decode("utf8")
    while True:
        assert not re.search("Invalid", output)
        assert not re.search("Exception", output)
        assert not re.search("critical", output)
        assert not re.search("Error", output)
        assert not re.search("ERROR", output)
        if re.search("Startup complete", output):
            break
        output = proc.stdout.readline().decode("utf8")


def test_start_of_logprep_with_full_configuration_http():
    pipeline = get_full_pipeline()
    config = get_default_logprep_config(pipeline, with_hmac=False)
    config.get("output").update({"kafka": {"type": "dummy_output", "default": False}})
    endpoint = "http://localhost:32000"
    config = convert_to_http_config(config, endpoint)
    config_path = "generated_config.yml"
    dump_config_as_file(config_path, config)
    with HTTPServerForTesting.run_in_thread():
        proc = start_logprep(f"{endpoint}/{config_path}")
        output = proc.stdout.readline().decode("utf8")
        while True:
            assert not re.search("Invalid", output)
            assert not re.search("Exception", output)
            assert not re.search("critical", output)
            assert not re.search("Error", output)
            assert not re.search("ERROR", output)
            if re.search("Startup complete", output):
                break
            output = proc.stdout.readline().decode("utf8")


def test_start_of_logprep_from_http_with_templated_url_and_config():
    config_path = Path("generated_config.yml")
    config_path.write_text(
        """
version: $LOGPREP_VERSION
process_count: $LOGPREP_PROCESS_COUNT
timeout: 0.1
logger:
    level: $LOGPREP_LOG_LEVEL
$LOGPREP_PIPELINE
$LOGPREP_INPUT
$LOGPREP_OUTPUT
""",
        encoding="utf-8",
    )
    env = {
        "LOGPREP_API_ENDPOINT": "http://localhost:32000",
        "LOGPREP_VERSION": "1",
        "LOGPREP_PROCESS_COUNT": "1",
        "LOGPREP_LOG_LEVEL": "DEBUG",
        "LOGPREP_PIPELINE": """
pipeline:
    - labelername:
        type: labeler
        schema: quickstart/exampledata/rules/labeler/schema.json
        include_parent_labels: true
        specific_rules:
            - quickstart/exampledata/rules/labeler/specific
        generic_rules:
            - quickstart/exampledata/rules/labeler/generic
""",
        "LOGPREP_OUTPUT": """
output:
    kafka:
        type: dummy_output
""",
        "LOGPREP_INPUT": "input:\n    kafka:\n        type: dummy_input\n        documents: []\n",
    }
    with HTTPServerForTesting.run_in_thread():
        proc = start_logprep("${LOGPREP_API_ENDPOINT}/generated_config.yml", env=env)
        output = proc.stdout.readline().decode("utf8")
        while True:
            assert not re.search("Invalid", output)
            assert not re.search("Exception", output)
            assert not re.search("critical", output)
            assert not re.search("Error", output)
            assert not re.search("ERROR", output)
            if re.search("Startup complete", output):
                break
            output = proc.stdout.readline().decode("utf8")
