"""
|PROCESSOR_NAME|
================

A processor to invoke http requests. Can be used to enrich events from an external api or
to trigger external systems by and with event field values.

.. security-best-practice::
   :title: |PROCESSOR|

   As the `requester` can execute arbitrary http requests it is advised to execute requests only
   against known and trusted endpoints and that the communication is protected with a valid
   SSL-Certificate. Do so by setting a certificate path with the option :code:`cert`.
   To ensure that the communication is trusted it is also recommended to set either an
   :code:`Authorization`-Header or a corresponding authentication with a username and password, via
   :code:`auth`.

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - requestername:
        type: requester
        rules:
            - tests/testdata/rules/rules

.. autoclass:: logprep.processor.requester.processor.Requester.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.requester.rule
"""

import json
import ssl
import typing
from dataclasses import dataclass
from os import PathLike
from urllib.parse import urlparse

import aiohttp

from logprep.ng.processor.field_manager.processor import FieldManager
from logprep.processor.base.exceptions import FieldExistsWarning
from logprep.processor.base.rule import Rule
from logprep.processor.requester.rule import RequesterRule
from logprep.util.helper import (
    FieldValue,
    add_fields_to,
    create_template_resolver,
    get_source_fields_dict,
    transform_field_value,
)

TEMPLATE_KWARGS = ("url", "json", "data", "params")


@dataclass(frozen=True, slots=True)
class RequesterResponse:
    """Response data required for requester result handling."""

    content: bytes


class Requester(FieldManager):
    """A processor to invoke http requests with field data
    and parses response data to field values"""

    rule_class = RequesterRule

    _session: aiohttp.ClientSession | None = None

    async def setup(self) -> None:
        """Set up the requester HTTP client session."""
        await super().setup()

        previous_session = self._session

        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=None),
            trust_env=True,
        )

        if previous_session is not None and not previous_session.closed:
            await previous_session.close()

    async def shut_down(self) -> None:
        """Close the requester HTTP client session."""
        if self._session is not None:
            await self._session.close()
            self._session = None
        await super().shut_down()

    async def _apply_rules(self, event: dict[str, FieldValue], rule: Rule) -> None:
        rule = typing.cast(RequesterRule, rule)
        source_field_dict = get_source_fields_dict(event, rule)
        if self._handle_missing_fields(event, rule, rule.source_fields, source_field_dict.values()):
            return
        if self._has_missing_values(event, rule, source_field_dict):
            return
        kwargs = self._template_kwargs(rule.kwargs, source_field_dict)
        response = await self._request(event, rule, kwargs)
        if response is not None:
            self._handle_response(event, rule, response)

    def _handle_response(
        self, event: dict, rule: RequesterRule, response: RequesterResponse
    ) -> None:
        conflicting_fields = []
        if rule.target_field:
            try:
                add_fields_to(
                    event,
                    fields={rule.target_field: self._get_result(response)},
                    rule=rule,
                    merge_with_target=rule.merge_with_target,
                    overwrite_target=rule.overwrite_target,
                )
            except FieldExistsWarning as error:
                conflicting_fields.extend(error.skipped_fields)
        if rule.target_field_mapping:
            source_fields = rule.target_field_mapping.keys()
            contents = self._get_field_values(self._get_result(response), source_fields)
            targets = rule.target_field_mapping.values()
            try:
                add_fields_to(
                    event,
                    dict(zip(targets, contents)),
                    rule,
                    rule.merge_with_target,
                    rule.overwrite_target,
                )
            except FieldExistsWarning as error:
                conflicting_fields.extend(error.skipped_fields)
        if conflicting_fields:
            raise FieldExistsWarning(rule, event, conflicting_fields)

    async def _request(
        self, event: dict, rule: RequesterRule, kwargs: dict
    ) -> RequesterResponse | None:
        """Perform an asynchronous HTTP request."""
        if self._session is None:
            raise RuntimeError("Requester HTTP client session is not initialized")

        kwargs = self._prepare_request_kwargs(kwargs)

        try:
            async with self._session.request(**kwargs) as response:
                response.raise_for_status()
                return RequesterResponse(content=await response.read())
        except aiohttp.ClientResponseError as error:
            self._handle_warning_error(event, rule, error)
        except aiohttp.ConnectionTimeoutError as error:
            self._handle_warning_error(event, rule, error)
        return None

    @classmethod
    def _prepare_request_kwargs(cls, kwargs: dict) -> dict:
        """Convert requests-compatible kwargs to aiohttp kwargs."""
        kwargs = kwargs.copy()

        cls._convert_auth(kwargs)
        cls._convert_timeout(kwargs)
        cls._convert_proxies(kwargs)
        cls._convert_ssl(kwargs)

        return kwargs

    @staticmethod
    def _convert_auth(kwargs: dict) -> None:
        """Convert basic authentication to aiohttp format."""
        auth: tuple[str, str] | None = kwargs.pop("auth", None)
        if auth:
            username, password = auth
            kwargs.setdefault("headers", {})
            kwargs["headers"]["Authorization"] = aiohttp.encode_basic_auth(
                username,
                password,
            )

    @staticmethod
    def _convert_timeout(kwargs: dict) -> None:
        """Convert the request timeout to aiohttp timeout settings."""
        timeout = kwargs.get("timeout")
        if timeout is None:
            return

        if isinstance(timeout, (tuple, list)):
            connect_timeout, read_timeout = timeout
        else:
            connect_timeout = timeout
            read_timeout = timeout

        kwargs["timeout"] = aiohttp.ClientTimeout(
            total=None,
            sock_connect=connect_timeout,
            sock_read=read_timeout,
        )

    @classmethod
    def _convert_proxies(cls, kwargs: dict) -> None:
        """Convert the requests proxy mapping to an aiohttp proxy."""
        proxies: dict[str, str] | None = kwargs.pop("proxies", None)
        if not proxies:
            return

        proxy = cls._select_proxy(kwargs["url"], proxies)
        if proxy:
            kwargs["proxy"] = cls._normalize_proxy_url(proxy)

    @staticmethod
    def _select_proxy(url: str, proxies: dict[str, str]) -> str | None:
        """Select the proxy matching the request URL."""
        parsed_url = urlparse(url)
        scheme = parsed_url.scheme
        hostname = parsed_url.hostname

        proxy_keys = (
            f"{scheme}://{hostname}",
            scheme,
            f"all://{hostname}",
            "all",
        )

        for key in proxy_keys:
            if key in proxies:
                return proxies[key]

        return None

    @staticmethod
    def _normalize_proxy_url(proxy: str) -> str:
        """Ensure that a proxy URL contains a scheme."""
        if "://" not in proxy:
            return f"http://{proxy}"
        return proxy

    @staticmethod
    def _convert_ssl(kwargs: dict) -> None:
        """Convert requests SSL options to aiohttp SSL configuration."""
        verify: bool | str = kwargs.pop("verify", True)
        cert: str | tuple[str, str] | None = kwargs.pop("cert", None)

        if verify is True and cert is None:
            return

        if verify is False and cert is None:
            kwargs["ssl"] = False
            return

        if isinstance(verify, str):
            ssl_context = ssl.create_default_context(cafile=verify)
        else:
            ssl_context = ssl.create_default_context()

        if verify is False:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        if cert:
            if isinstance(cert, tuple):
                cert_file, key_file = cert
                ssl_context.load_cert_chain(
                    certfile=cert_file,
                    keyfile=key_file,
                )
            else:
                ssl_context.load_cert_chain(certfile=cert)

        kwargs["ssl"] = ssl_context

    @staticmethod
    def _get_result(response: RequesterResponse) -> dict | str:
        try:
            result = json.loads(response.content)
        except json.JSONDecodeError:
            result = response.content.decode("utf-8")
        return result

    def _template_kwargs(self, kwargs: dict, source: dict):
        template_resolver = create_template_resolver(source)
        for key, value in kwargs.items():
            if key in TEMPLATE_KWARGS:
                kwargs[key] = transform_field_value(
                    value,
                    transform_key=template_resolver,
                    transform_value=lambda d: template_resolver(d) if isinstance(d, str) else d,
                )
        return kwargs

    async def has_asyncio(self) -> bool:
        """Return whether the processor performs asynchronous I/O operations."""
        return True
