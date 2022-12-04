# pylint: disable=missing-docstring
import contextlib
from pathlib import Path
import subprocess
import sys
import threading
import pytest
import socketserver
import http.server
import re
from tests.acceptance.util import (
    get_full_pipeline,
    get_default_logprep_config,
    start_logprep,
    stop_logprep,
)
from logprep.util.json_handling import dump_config_as_file


class Server(socketserver.TCPServer):
    allow_reuse_address = True

    def install_signal_handlers(self):
        pass

    @classmethod
    def run_http_server(cls, port=32000):
        with Server(("", port), http.server.SimpleHTTPRequestHandler) as httpd:
            try:
                cls.httpd = httpd
                cls.httpd.serve_forever(1)
            finally:
                cls.httpd.server_close()

    @classmethod
    @contextlib.contextmanager
    def run_in_thread(cls):
        """Context manager to run the server in a separate thread"""
        cls.thread = threading.Thread(target=cls.run_http_server)
        cls.thread.start()
        yield
        cls.stop()

    @classmethod
    def stop(cls):
        cls.httpd.shutdown()
        cls.thread.join()


def teardown_function():
    Path("generated_config.yml").unlink()
    stop_logprep()


def test_full_configuration_logprep_start(tmp_path):
    pipeline = get_full_pipeline()
    config = get_default_logprep_config(pipeline, with_hmac=False)
    config_path = str(tmp_path / "generated_config.yml")
    dump_config_as_file(config_path, config)
    proc = start_logprep(config_path)
    output = proc.stdout.readline().decode("utf8")
    while True:
        assert not re.search("Invalid processor config", output)
        assert not re.search("Exception", output)
        assert not re.search("exception", output)
        assert not re.search("critical", output)
        if re.search("Startup complete", output):
            break
        output = proc.stdout.readline().decode("utf8")
    stop_logprep()


def test_full_configuration_from_http():
    pipeline = get_full_pipeline()
    config = get_default_logprep_config(pipeline, with_hmac=False)
    config_path = "generated_config.yml"
    dump_config_as_file(config_path, config)
    with Server.run_in_thread():
        proc = start_logprep(f"http://localhost:32000/{config_path}")
        output = proc.stdout.readline().decode("utf8")
        while True:
            assert not re.search("Invalid processor config", output)
            assert not re.search("Exception", output)
            if re.search("Startup complete", output):
                break
            output = proc.stdout.readline().decode("utf8")
        stop_logprep()
