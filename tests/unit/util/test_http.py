# pylint: disable=missing-docstring
from unittest import mock

from logprep.util.http import ThreadingHTTPServer


class TestThreadingHTTPServer:

    def test_start_server(self):
        uvicorn_config = {}
        app = None
        server = ThreadingHTTPServer(uvicorn_config, app, False)
        server.start()
        assert server.thread.is_alive()
        server.shut_down(0.1)

    def test_shutdown_server(self):
        uvicorn_config = {}
        app = None
        server = ThreadingHTTPServer(uvicorn_config, app, False)
        server.start()
        thread = server.thread
        uvicorn_server = server.server
        server.shut_down(0.1)
        assert not thread.is_alive()
        assert uvicorn_server.should_exit

    def test_shutdown_server_double_checks_thread_is_dead(self):
        uvicorn_config = {}
        app = None
        server = ThreadingHTTPServer(uvicorn_config, app, False)
        server.thread = mock.MagicMock()
        server.server = mock.MagicMock()
        server.thread.is_alive.return_value = False
        server.shut_down(0.1)
        assert server.thread.is_alive.call_count == 2

    def test_restart_server(self):
        uvicorn_config = {}
        app = None
        server = ThreadingHTTPServer(uvicorn_config, app, False)
        server.start()
        thread = server.thread
        server.restart(0.1)
        assert server.thread is not thread
        server.shut_down(0.1)
