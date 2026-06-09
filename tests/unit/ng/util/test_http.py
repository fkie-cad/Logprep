# pylint: disable=missing-docstring,protected-access

import asyncio
import logging
from contextlib import asynccontextmanager

import aiohttp
import pytest
from asgiref.typing import (
    ASGIReceiveCallable,
    ASGISendCallable,
    HTTPResponseBodyEvent,
    HTTPResponseStartEvent,
    Scope,
)

from logprep.ng.util.http import AsyncHTTPServer


async def simple_echo_asgi_app(
    scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable
) -> None:
    """
    Basic and low-level asgi app which simply responds with request bodys and status 200.
    """
    assert scope["type"] == "http", "only http traffic expected"
    body = b""
    while True:
        message = await receive()
        assert message["type"] == "http.request", "only basic http traffic expected"
        body += message.get("body", b"")
        if not message.get("more_body", False):
            break

    response_start: HTTPResponseStartEvent = {
        "type": "http.response.start",
        "status": 200,
        "headers": [(b"content-type", b"text/plain")],
        "trailers": False,
    }
    response_body: HTTPResponseBodyEvent = {
        "type": "http.response.body",
        "body": body,
        "more_body": False,
    }
    await send(response_start)
    await send(response_body)


@asynccontextmanager
async def run_server(
    server: AsyncHTTPServer,
    wait_until_started: bool = True,
    auomatic_cleanup: bool = True,
):
    """
    Convenience function for running `AsyncHTTPServer`
    """
    server_task = None
    try:
        server_task = asyncio.create_task(server.run())

        if wait_until_started:
            await server.wait_until_started()

        yield server_task
    finally:
        if auomatic_cleanup:
            if server_task is not None:
                if not server._server.should_exit:
                    server._server.should_exit = True
                    async with asyncio.timeout(1):
                        await server_task
                server_task.cancel()
                await server_task


class TestAsyncHTTPServer:

    @pytest.mark.timeout(1)
    async def test_basic_server_run(self, unused_tcp_port):
        url = f"http://127.0.0.1:{unused_tcp_port}"
        server = AsyncHTTPServer({"port": unused_tcp_port}, app=simple_echo_asgi_app)

        async with run_server(server):
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    assert response.status == 200

                async with session.post(url, data=b"test") as response:
                    response.raise_for_status()
                    assert await response.text() == "test"

    @pytest.mark.timeout(1)
    async def test_basic_server_run_repeatedly(self, unused_tcp_port):
        url = f"http://127.0.0.1:{unused_tcp_port}"

        server = AsyncHTTPServer({"port": unused_tcp_port}, app=simple_echo_asgi_app)

        async with run_server(server, auomatic_cleanup=False) as server_task:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    assert response.status == 200

            server.stop()
            await server_task

        server2 = AsyncHTTPServer({"port": unused_tcp_port}, app=simple_echo_asgi_app)

        async with run_server(server2) as server_task:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    assert response.status == 200

    @pytest.mark.timeout(1)
    async def test_uvicorn_logs_are_propagated(self, unused_tcp_port, caplog):
        url = f"http://127.0.0.1:{unused_tcp_port}"
        with caplog.at_level(logging.DEBUG, logger="root"):

            server = AsyncHTTPServer(
                uvicorn_config={"port": unused_tcp_port}, app=simple_echo_asgi_app
            )

            # uvicorn.error is a misleading name for the general purpose server logger
            assert len([r for r in caplog.records if r.name == "uvicorn.error"]) == 0

            async with run_server(server):
                assert len([r for r in caplog.records if r.name == "uvicorn.error"]) > 0
                assert len([r for r in caplog.records if r.name == "uvicorn.access"]) == 0

                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        response.raise_for_status()
                        assert response.status == 200

                assert len([r for r in caplog.records if r.name == "uvicorn.access"]) == 1
