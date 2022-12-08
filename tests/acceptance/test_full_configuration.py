# pylint: disable=missing-docstring
import contextlib
from pathlib import Path
import threading
import socketserver
import http.server
import re
from tests.acceptance.util import (
    get_full_pipeline,
    get_default_logprep_config,
    start_logprep,
    stop_logprep,
    convert_to_http_config,
)
from logprep.util.json_handling import dump_config_as_file


class TestServer(socketserver.TCPServer):
    allow_reuse_address = True

    @classmethod
    def run_http_server(cls, port=32000):
        with TestServer(("", port), http.server.SimpleHTTPRequestHandler) as httpd:
            try:
                cls.httpd = httpd
                cls.httpd.serve_forever()
            finally:
                cls.httpd.server_close()

    @classmethod
    @contextlib.contextmanager
    def run_in_thread(cls):
        """Context manager to run the server in a separate thread"""
        cls.thread = threading.Thread(target=cls.run_http_server)
        cls.thread.start()
        yield
        cls.httpd.shutdown()
        cls.thread.join()

    @classmethod
    def stop(cls):
        if hasattr(cls, "httpd"):
            cls.httpd.shutdown()
        if hasattr(cls, "thread"):
            cls.thread.join()


def teardown_function():
    Path("generated_config.yml").unlink(missing_ok=True)
    TestServer.stop()
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
    with TestServer.run_in_thread():
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
