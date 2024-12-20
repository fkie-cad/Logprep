# pylint: disable=missing-docstring
# pylint: disable=line-too-long
# pylint: disable=too-many-locals
import os
import re
import tempfile
import time
from pathlib import Path

import requests

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
    pipeline = get_full_pipeline(exclude=["normalizer", "geoip_enricher"])
    config = get_default_logprep_config(pipeline, with_hmac=False)
    config.output.update({"kafka": {"type": "dummy_output", "default": False}})
    config_path = tmp_path / "generated_config.yml"
    config_path.write_text(config.as_yaml(), encoding="utf-8")
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
    pipeline = get_full_pipeline(exclude=["normalizer", "geoip_enricher"])
    config = get_default_logprep_config(pipeline, with_hmac=False)
    config.output.update({"kafka": {"type": "dummy_output", "default": False}})
    endpoint = "http://localhost:32000"
    config = convert_to_http_config(config, endpoint)
    config_path = Path("generated_config.yml")
    config_path.write_text(config.as_yaml(), encoding="utf-8")
    with HTTPServerForTesting.run_in_thread():
        proc = start_logprep(f"{endpoint}/{str(config_path)}")
        output = proc.stdout.readline().decode("utf8")
        while True:
            assert not re.search("Invalid", output), output
            assert not re.search("Exception", output), output
            assert not re.search("critical", output), output
            assert not re.search("Error", output), output
            assert not re.search("ERROR", output), output
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
        schema: examples/exampledata/rules/labeler/schema.json
        include_parent_labels: true
        rules:
            - examples/exampledata/rules/labeler/rules
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


def test_logprep_exposes_prometheus_metrics_and_healthchecks(tmp_path):
    temp_dir = tempfile.gettempdir()
    input_file_path = Path(os.path.join(temp_dir, "input.txt"))
    input_file_path.touch()
    # requester is excluded because it tries to connect to non-existing server
    # selective_extractor is excluded because of output mismatch (rules expect kafka as output)
    # normalizer is excluded because of deprecation
    # geoip_enricher is excluded because of missing maxmind license
    pipeline = get_full_pipeline(
        exclude=["requester", "selective_extractor", "normalizer", "geoip_enricher"]
    )
    config = get_default_logprep_config(pipeline, with_hmac=False)
    config.version = "my_custom_version"
    config.config_refresh_interval = 300
    config.metrics = {"enabled": True, "port": 8003}
    config.input = {
        "fileinput": {
            "type": "file_input",
            "logfile_path": str(input_file_path),
            "start": "begin",
            "interval": 1,
            "watch_file": True,
        }
    }
    config.output = {
        "kafka": {  # the name has to be kafka for some default rules
            "type": "console_output",
        },
        "second_output": {
            "type": "console_output",
        },
    }
    config_path = tmp_path / "generated_config.yml"
    # duplicate one processor to test that rule metrics are separated by processor names and not by type
    config.pipeline.append(
        {
            "calculator2": {
                "rules": ["tests/testdata/unit/calculator/rules"],
                "type": "calculator",
            }
        }
    )
    config_path.write_text(config.as_yaml(), encoding="utf-8")
    proc = start_logprep(config_path, env={"PROMETHEUS_MULTIPROC_DIR": tmp_path})
    input_file_path.write_text("user root logged in\n", encoding="utf8")
    while True:
        output = proc.stdout.readline().decode("utf8")
        assert "error" not in output.lower(), "error message"
        assert "critical" not in output.lower(), "error message"
        assert "exception" not in output.lower(), "error message"
        assert not re.search("Shutting down", output)
        if "Startup complete" in output:
            break
    time.sleep(2)
    response = requests.get("http://127.0.0.1:8003", timeout=7)
    response.raise_for_status()
    metrics = response.text
    expected_metrics = [
        r"logprep_number_of_processed_events_total\{component=\"input\",description=\"FileInput \(fileinput\)\",name=\"fileinput\",type=\"file_input\"}",
        r"logprep_number_of_processed_events_total\{component=\"rule\",description=\"id:.+\",name=\".+\",type\=\".+\"}",
        r"logprep_number_of_processed_events_total\{component=\"output\",description=\".+\",name=\"kafka\",type=\"console_output\"}",
        r"logprep_number_of_processed_events_total\{component=\"output\",description=\".+\",name=\"second_output\",type=\"console_output\"}",
        r"logprep_number_of_warnings_total{component=\"rule\",description=\"id:.+\",name=\".+\",type=\".+\"}",
        r"logprep_number_of_warnings_total{component=\"input\",description=\".+\",name=\"fileinput\",type=\"file_input\"}",
        r"logprep_number_of_warnings_total{component=\"output\",description=\".+\",name=\"kafka\",type=\"console_output\"}",
        r"logprep_number_of_warnings_total{component=\"output\",description=\".+\",name=\"second_output\",type=\"console_output\"}",
        r"logprep_number_of_errors_total{component=\"rule\",description=\"id:.+\",name=\".+\",type=\".+\"}",
        r"logprep_number_of_errors_total{component=\"input\",description=\".+\",name=\"fileinput\",type=\"file_input\"}",
        r"logprep_number_of_errors_total{component=\"output\",description=\".+\",name=\"kafka\",type=\"console_output\"}",
        r"logprep_number_of_errors_total{component=\"output\",description=\".+\",name=\"second_output\",type=\"console_output\"}",
        r"logprep_processing_time_per_event_sum{component=\"rule\",description=\"id:.+\",name=\".+\",type=\".+\"}",
        r"logprep_processing_time_per_event_count{component=\"rule\",description=\"id:.+\",name=\".+\",type=\".+\"}",
        r"logprep_processing_time_per_event_bucket{component=\"rule\",description=\"id:.+\",name=\".+\",type=\".+\"}",
        r"logprep_processing_time_per_event_sum{component=\"input\",description=\".+\",name=\"fileinput\",type=\"file_input\"}",
        r"logprep_processing_time_per_event_count{component=\"input\",description=\".+\",name=\"fileinput\",type=\"file_input\"}",
        r"logprep_processing_time_per_event_bucket{component=\"input\",description=\".+\",name=\"fileinput\",type=\"file_input\"}",
        r"logprep_processing_time_per_event_sum{component=\"output\",description=\".+\",name=\"kafka\",type=\"console_output\"}",
        r"logprep_processing_time_per_event_count{component=\"output\",description=\".+\",name=\"kafka\",type=\"console_output\"}",
        r"logprep_processing_time_per_event_bucket{component=\"output\",description=\".+\",name=\"kafka\",type=\"console_output\"}",
        r"logprep_processing_time_per_event_sum{component=\"output\",description=\".+\",name=\"second_output\",type=\"console_output\"}",
        r"logprep_processing_time_per_event_count{component=\"output\",description=\".+\",name=\"second_output\",type=\"console_output\"}",
        r"logprep_processing_time_per_event_bucket{component=\"output\",description=\".+\",name=\"second_output\",type=\"console_output\"}",
        r"logprep_domain_resolver_total_urls_total",
        r"logprep_domain_resolver_resolved_new_total",
        r"logprep_domain_resolver_resolved_cached_total",
        r"logprep_domain_resolver_timeouts_total",
        r"logprep_pseudonymizer_pseudonymized_urls_total",
        r"logprep_amides_total_cmdlines_total",
        r"logprep_amides_new_results",
        r"logprep_amides_cached_results",
        r"logprep_amides_num_cache_entries",
        r"logprep_amides_cache_load",
        r"logprep_amides_mean_misuse_detection_time_sum",
        r"logprep_amides_mean_misuse_detection_time_count",
        r"logprep_amides_mean_misuse_detection_time_bucket",
        r"logprep_amides_mean_rule_attribution_time_sum",
        r"logprep_amides_mean_rule_attribution_time_count",
        r"logprep_amides_mean_rule_attribution_time_bucket",
        r"logprep_version_info.*config=\"my_custom_version\"",
        r"logprep_config_refresh_interval.+300",
        r"logprep_number_of_config_refreshes.+0",
    ]
    for expeced_metric in expected_metrics:
        assert re.search(expeced_metric, metrics), f"Metric {expeced_metric} not found in metrics"
    forbidden_metrics = [
        r"component=\"None\"",
        r"type=\"None\"",
        r"name=\"None\"",
        r"description=\"None\"",
    ]
    for forbidden_metric in forbidden_metrics:
        assert not re.search(
            forbidden_metric, metrics
        ), f"Metric {forbidden_metric} found in metrics"

    first_calculator = r"logprep_number_of_processed_events_total\{component=\"rule\",description=\"id:.+\",name=\"calculator\",type\=\"calculator\"}"
    assert re.search(first_calculator, metrics), "First calculator not found"
    assert (
        len(re.findall(first_calculator, metrics)) == 2
    ), "More or less than two rules were found for first calculator"
    second_calculator = r"logprep_number_of_processed_events_total\{component=\"rule\",description=\"id:.+\",name=\"calculator2\",type\=\"calculator\"}"
    assert re.search(second_calculator, metrics), "Second calculator not found"
    assert (
        len(re.findall(second_calculator, metrics)) == 2
    ), "More or less than two rules were found for second calculator"
    both_calculators = r"logprep_number_of_processed_events_total\{component=\"rule\",description=\"id:.+\",name=\".+\",type\=\"calculator\"}"
    assert (
        len(re.findall(both_calculators, metrics)) == 4
    ), "More or less than 4 rules were found for both calculator"

    # check health endpoint
    response = requests.get("http://127.0.0.1:8003/health", timeout=7)
    response.raise_for_status()
    assert "OK" == response.text

    proc.kill()
