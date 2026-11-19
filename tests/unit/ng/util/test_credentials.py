# pylint: disable=missing-docstring,protected-access
from unittest import mock

import aiohttp
import pytest
from aiohttp import web

from logprep.util.credentials import (
    BasicAuthCredentials,
    Credentials,
    CredentialsBadRequestError,
    MTLSCredentials,
    OAuth2ClientFlowCredentials,
    OAuth2PasswordFlowCredentials,
    OAuth2TokenCredentials,
)


@pytest.fixture
async def credential_cleanup():
    credentials = []
    yield credentials
    for credential in credentials:
        await credential.close_aiohttp_session()


class TestAiohttpCredentials:
    async def test_session_is_reused_and_closed(self, credential_cleanup):
        credentials = Credentials()
        credential_cleanup.append(credentials)

        first = await credentials.get_aiohttp_session()
        second = await credentials.get_aiohttp_session()
        assert first is second
        assert not first.closed

        await credentials.close_aiohttp_session()
        assert first.closed
        third = await credentials.get_aiohttp_session()
        assert third is not first

    def test_retry_configuration_matches_requests(self):
        credentials = Credentials()
        retry = credentials.get_retry_config()
        assert retry.total == 3
        assert set(retry.status_forcelist) == {500, 502, 503, 504}

    async def test_basic_auth(self, credential_cleanup):
        credentials = BasicAuthCredentials(username="user", password="password")
        credential_cleanup.append(credentials)
        session = await credentials.get_aiohttp_session()
        assert session.headers["Authorization"] == aiohttp.encode_basic_auth("user", "password")
        assert await credentials.get_aiohttp_session() is session

    async def test_bearer_token(self, credential_cleanup):
        credentials = OAuth2TokenCredentials(token="token")
        credential_cleanup.append(credentials)
        session = await credentials.get_aiohttp_session()
        assert session.headers["Authorization"] == "Bearer token"

    async def test_trust_env(self, credential_cleanup):
        credentials = Credentials()
        credential_cleanup.append(credentials)
        session = await credentials.get_aiohttp_session()
        assert session.trust_env is True

    async def test_mtls_connector(self, credential_cleanup):
        credentials = MTLSCredentials(
            cert="client.pem",
            client_key="client.key",
            ca_cert="ca.pem",
        )
        credential_cleanup.append(credentials)

        ssl_context = mock.MagicMock()
        connector = mock.MagicMock()
        session = mock.MagicMock(spec=aiohttp.ClientSession)
        session.closed = False

        with (
            mock.patch(
                "logprep.util.credentials.ssl.create_default_context",
                return_value=ssl_context,
            ) as create_context,
            mock.patch(
                "logprep.util.credentials.aiohttp.TCPConnector",
                return_value=connector,
            ) as create_connector,
            mock.patch(
                "logprep.util.credentials.aiohttp.ClientSession",
                return_value=session,
            ) as create_session,
        ):
            result = await credentials.get_aiohttp_session()

        assert result is session

        create_context.assert_called_once_with(cafile="ca.pem")
        ssl_context.load_cert_chain.assert_called_once_with(
            certfile="client.pem",
            keyfile="client.key",
        )
        create_connector.assert_called_once_with(ssl=ssl_context)
        create_session.assert_called_once_with(
            connector=connector,
            trust_env=True,
        )

    async def test_password_flow_retrieves_and_reuses_token(
        self, aiohttp_server, credential_cleanup
    ):
        calls = []

        async def token_handler(request):
            data = await request.post()
            calls.append(dict(data))
            return web.json_response(
                {"access_token": "first", "expires_in": 3600, "refresh_token": "refresh"}
            )

        app = web.Application()
        app.router.add_post("/token", token_handler)
        server = await aiohttp_server(app)
        credentials = OAuth2PasswordFlowCredentials(
            endpoint=str(server.make_url("/token")), username="user", password="password"
        )
        credential_cleanup.append(credentials)
        session = await credentials.get_aiohttp_session()
        assert session.headers["Authorization"] == "Bearer first"
        assert await credentials.get_aiohttp_session() is session
        assert calls == [{"grant_type": "password", "username": "user", "password": "password"}]

    async def test_password_flow_refreshes_expired_token(self, aiohttp_server, credential_cleanup):
        calls = []

        async def token_handler(request):
            data = dict(await request.post())
            calls.append(data)
            if len(calls) == 1:
                return web.json_response(
                    {"access_token": "first", "expires_in": 3600, "refresh_token": "refresh"}
                )
            return web.json_response(
                {"access_token": "second", "expires_in": 3600, "refresh_token": "refresh2"}
            )

        app = web.Application()
        app.router.add_post("/token", token_handler)
        server = await aiohttp_server(app)
        credentials = OAuth2PasswordFlowCredentials(
            endpoint=str(server.make_url("/token")), username="user", password="password"
        )
        credential_cleanup.append(credentials)
        await credentials.get_aiohttp_session()
        credentials._token.expiry_time = credentials._token.expiry_time.replace(year=2000)
        session = await credentials.get_aiohttp_session()
        assert session.headers["Authorization"] == "Bearer second"
        assert calls[-1] == {"grant_type": "refresh_token", "refresh_token": "refresh"}

    async def test_client_flow_retrieves_and_reuses_token(self, aiohttp_server, credential_cleanup):
        calls = []

        async def token_handler(request):
            calls.append((dict(await request.post()), request.headers.get("Authorization")))
            return web.json_response({"access_token": "client-token", "expires_in": 3600})

        app = web.Application()
        app.router.add_post("/token", token_handler)
        server = await aiohttp_server(app)
        credentials = OAuth2ClientFlowCredentials(
            endpoint=str(server.make_url("/token")), client_id="client", client_secret="secret"
        )
        credential_cleanup.append(credentials)
        session = await credentials.get_aiohttp_session()
        assert session.headers["Authorization"] == "Bearer client-token"
        assert await credentials.get_aiohttp_session() is session
        assert calls == [
            ({"grant_type": "client_credentials"}, aiohttp.encode_basic_auth("client", "secret"))
        ]

    @pytest.mark.parametrize("flow", ["password", "client"])
    async def test_oauth_bad_request(self, flow, aiohttp_server, credential_cleanup):
        async def token_handler(_):
            return web.json_response({"error": "invalid_grant"}, status=400)

        app = web.Application()
        app.router.add_post("/token", token_handler)
        server = await aiohttp_server(app)
        endpoint = str(server.make_url("/token"))
        if flow == "password":
            credentials = OAuth2PasswordFlowCredentials(
                endpoint=endpoint, username="user", password="password"
            )
        else:
            credentials = OAuth2ClientFlowCredentials(
                endpoint=endpoint, client_id="client", client_secret="secret"
            )
        credential_cleanup.append(credentials)
        with pytest.raises(CredentialsBadRequestError, match="invalid_grant"):
            await credentials.get_aiohttp_session()
