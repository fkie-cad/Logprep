# pylint: disable=missing-docstring
from logprep.util.http import ThreadingHTTPServer


class TestThreadingHTTPServer:

    def test_start_server(self):
        uvicorn_config = {}
        app = None
        server = ThreadingHTTPServer(uvicorn_config, app, False)
        server.start()
        assert server.thread.is_alive()

    def test_shutdown_server(self):
        uvicorn_config = {}
        app = None
        server = ThreadingHTTPServer(uvicorn_config, app, False)
        server.start()
        thread = server.thread
        uvicorn_server = server.server
        server.shut_down()
        assert not thread.is_alive()
        assert uvicorn_server.should_exit
        assert server.thread is None
        assert server.server is None

    def test_restart_server(self):
        uvicorn_config = {}
        app = None
        server = ThreadingHTTPServer(uvicorn_config, app, False)
        server.start()
        thread = server.thread
        server.restart()
        assert server.thread is not thread
        server.shut_down()
        assert server.thread is None
