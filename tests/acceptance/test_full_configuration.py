# pylint: disable=missing-docstring
from pathlib import Path
import time
import requests
import re
from tests.acceptance.util import (
    get_full_pipeline,
    get_default_logprep_config,
    start_logprep,
    stop_logprep,
    convert_to_http_config,
    TestingHTTPServer,
)
from logprep.util.json_handling import dump_config_as_file


def teardown_function():
    Path("generated_config.yml").unlink(missing_ok=True)
    stop_logprep()


def test_start_of_logprep_with_full_configuration_from_file(tmp_path):
    pipeline = get_full_pipeline()
    config = get_default_logprep_config(pipeline, with_hmac=False)
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
    endpoint = "http://localhost:32000"
    config = convert_to_http_config(config, endpoint)
    config_path = "generated_config.yml"
    dump_config_as_file(config_path, config)
    with TestingHTTPServer.run_in_thread():
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


def test_logprep_collects_metrics(tmp_path):
    pipeline = get_full_pipeline(exclude=("requester"))
    config = get_default_logprep_config(pipeline, with_hmac=False)
    config |= {
        "metrics": {
            "enabled": True,
            "period": 10,
            "cumulative": False,
            "aggregate_processes": False,
            "measure_time": {"enabled": True, "append_to_event": False},
            "targets": [{"prometheus": {"port": 8000}}],
        },
        "input": {
            "testinput": {
                "type": "http_input",
                "uvicorn_config": {
                    "host": "127.0.0.1",
                    "port": 9000,
                },
                "endpoints": {"/json": "json", "/jsonl": "jsonl", "/plaintext": "plaintext"},
            }
        },
    }
    config_path = str(tmp_path / "generated_config.yml")
    dump_config_as_file(config_path, config)
    proc = start_logprep(config_path, env={"PROMETHEUS_MULTIPROC_DIR": tmp_path})
    output = proc.stdout.readline().decode("utf8")
    while True:
        if re.search("Prometheus Exporter started on port 8000", output):
            break
        output = proc.stdout.readline().decode("utf8")
    requests.post("http://127.0.0.1:9000/plaintext", data="my message", timeout=5)
    time.sleep(1)
    metrics = requests.get("http://127.0.0.1:8000").text
    assert metrics
