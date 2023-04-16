# pylint: disable=missing-docstring
import os
import re
import tempfile
from pathlib import Path

import requests

from logprep.util.json_handling import dump_config_as_file
from tests.acceptance.util import (
    HTTPServerForTesting,
    convert_to_http_config,
    get_default_logprep_config,
    get_full_pipeline,
    start_logprep,
    stop_logprep,
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
    # requester is excluded because it tries to connect to non-existing server
    # selective_extractor is excluded because of output mismatch (rules expect kafka as output)
    pipeline = get_full_pipeline(exclude=["requester", "selective_extractor"])
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
            "kafka": {  # the name has to be kafka for some default rules
                "type": "console_output",
            },
            "second_output": {
                "type": "console_output",
            },
        },
    }
    config_path = str(tmp_path / "generated_config.yml")
    dump_config_as_file(config_path, config)
    proc = start_logprep(config_path, env={"PROMETHEUS_MULTIPROC_DIR": tmp_path})
    input_file_path.write_text("user root logged in\n", encoding="utf8")
    while True:
        output = proc.stdout.readline().decode("utf8")
        assert "error" not in output.lower(), "error message"
        assert "critical" not in output.lower(), "error message"
        assert "exception" not in output.lower(), "error message"
        assert "error" not in output.lower(), "error message"
        if "Started exposing metrics" in output:
            break
    response = requests.get("http://127.0.0.1:8000", timeout=0.1)
    response.raise_for_status()
    metrics = response.text
    connector_name_type_tuples = [
        ("fileinput", "file_input"),
        ("kafka", "console_output"),
        ("second_output", "console_output"),
    ]
    for name, connector_type in connector_name_type_tuples:
        assert re.search(
            rf"logprep_connector_number_of_processed_events.*{name}.*{connector_type}.* 1\.0",
            metrics,
        )
        assert re.search(
            rf"logprep_connector_mean_processing_time_per_event.*{name}.*{connector_type}.* \d\..*",
            metrics,
        )
        assert re.search(
            rf"logprep_connector_number_of_warnings.*{name}.*{connector_type}.* 0\.0", metrics
        )
        assert re.search(
            rf"logprep_connector_number_of_errors.*{name}.*{connector_type}.* 0\.0", metrics
        )

    processor_names = [list(p.keys())[0] for p in config.get("pipeline")]
    for processor_name in processor_names:
        assert re.search(
            rf"logprep_processor_number_of_processed_events.*{processor_name}.* 1\.0", metrics
        )
        assert re.search(
            rf"logprep_processor_mean_processing_time_per_event.*{processor_name}.* \d\..*", metrics
        )
        assert re.search(rf"logprep_processor_number_of_warnings.*{processor_name}.* 0\.0", metrics)
        assert re.search(rf"logprep_processor_number_of_errors.*{processor_name}.* 0\.0", metrics)
        assert re.search(rf"logprep_number_of_rules.*{processor_name}.*generic.* \d\.0", metrics)
        assert re.search(rf"logprep_number_of_rules.*{processor_name}.*specific.* \d\.0", metrics)
        assert re.search(rf"logprep_number_of_matches.*{processor_name}.*specific.* \d\.0", metrics)
        assert re.search(rf"logprep_number_of_matches.*{processor_name}.*generic.* \d\.0", metrics)
        assert re.search(
            rf"logprep_mean_processing_time.*{processor_name}.*specific.* \d\..*", metrics
        )
        assert re.search(
            rf"logprep_mean_processing_time.*{processor_name}.*generic.* \d\..*", metrics
        )

    assert re.search("logprep_processor_total_urls.*domain_resolver.* 0\.0", metrics)
    assert re.search("logprep_processor_resolved_new.*domain_resolver.* 0\.0", metrics)
    assert re.search("logprep_processor_resolved_cached.*domain_resolver.* 0\.0", metrics)
    assert re.search("logprep_processor_timeouts.*domain_resolver.* 0\.0", metrics)
    assert re.search("logprep_processor_pseudonymized_urls.*pseudonymizer.* 0\.0", metrics)

    assert re.search("logprep_pipeline_kafka_offset.*pipeline-1.* 0\.0", metrics)
    assert re.search(
        r"logprep_pipeline_mean_processing_time_per_event.*pipeline-1.* \d\..*", metrics
    )
    assert re.search("logprep_pipeline_number_of_processed_events.*pipeline-1.* 1\.0", metrics)
    assert re.search("logprep_pipeline_sum_of_processor_warnings.*pipeline-1.* 0\.0", metrics)
    assert re.search("logprep_pipeline_sum_of_processor_errors.*pipeline-1.* 0\.0", metrics)

    assert re.search(
        r"logprep_tracking_interval_in_seconds.*config_version.*logprep_version.* 1\.0", metrics
    )
    proc.kill()
