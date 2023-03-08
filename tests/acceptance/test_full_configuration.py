# pylint: disable=missing-docstring
import os
import re
import tempfile
import time
from pathlib import Path

import requests

from logprep.util.json_handling import dump_config_as_file
from tests.acceptance.util import (
    get_full_pipeline,
    get_default_logprep_config,
    start_logprep,
    stop_logprep,
    convert_to_http_config,
    HTTPServerForTesting,
)


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


def test_logprep_exposes_prometheus_metrics(tmp_path):
    temp_dir = tempfile.gettempdir()
    input_file_path = Path(os.path.join(temp_dir, "input.txt"))
    input_file_path.touch()
    pipeline = get_full_pipeline()
    config = get_default_logprep_config(pipeline, with_hmac=False)
    config |= {
        "metrics": {
            "enabled": True,
            "period": 1,
            "cumulative": False,
            "aggregate_processes": False,
            "measure_time": {"enabled": True, "append_to_event": False},
            "targets": [{"prometheus": {"port": 8000}}],
        },
        "input": {
            "fileinput": {
                "type": "file_input",
                "logfile_path": str(input_file_path),
                "start": "begin",
                "interval": 1,
                "watch_file": True,
            }
        },
        "output": {
            "kafka": {
                "type": "console_output",
            }
        },
    }
    config_path = str(tmp_path / "generated_config.yml")
    dump_config_as_file(config_path, config)
    proc = start_logprep(config_path, env={"PROMETHEUS_MULTIPROC_DIR": tmp_path})
    output = proc.stdout.readline().decode("utf8")
    while True:
        if re.search("Startup complete", output):
            break
        output = proc.stdout.readline().decode("utf8")
    input_file_path.write_text("test event\n")
    metrics = ""
    while "logprep_" not in metrics:
        response = requests.get("http://127.0.0.1:8000", timeout=0.1)
        response.raise_for_status()
        metrics = response.text
    time.sleep(0.2)  # nosemgrep
    response = requests.get("http://127.0.0.1:8000", timeout=0.1)
    response.raise_for_status()
    metrics = response.text
    proc.kill()
    metric_names = [
        "logprep_connector_number_of_processed_events",
        "logprep_connector_mean_processing_time_per_event",
        "logprep_connector_number_of_warnings",
        "logprep_connector_number_of_errors",
        "logprep_processor_number_of_processed_events",
        "logprep_processor_mean_processing_time_per_event",
        "logprep_processor_number_of_warnings",
        "logprep_processor_number_of_errors",
        "logprep_number_of_rules",
        "logprep_number_of_matches",
        "logprep_mean_processing_time",
        "logprep_processor_total_urls",
        "logprep_processor_resolved_new",
        "logprep_processor_resolved_cached",
        "logprep_processor_timeouts",
        "logprep_processor_pseudonymized_urls",
        "logprep_pipeline_kafka_offset",
        "logprep_pipeline_mean_processing_time_per_event",
        "logprep_pipeline_number_of_processed_events",
        "logprep_pipeline_number_of_warnings",
        "logprep_pipeline_number_of_errors",
    ]
    for metric_name in metric_names:
        assert metric_name in metrics, metric_name
