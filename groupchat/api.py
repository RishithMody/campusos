"""Small HTTPS client. Response bodies and credentials never enter errors or logs."""

import re
from typing import Any
from urllib.parse import urlsplit

import httpx


class APIError(Exception):
    def __init__(self, status: int = 503):
        self.status = status
        super().__init__("CampusOS request could not be completed.")


def identifier(value: str, prefix: str) -> str:
    minimum = 16 if prefix in {"neg", "cnt", "agt"} else 8
    if not re.fullmatch(rf"{prefix}_[A-Za-z0-9]{{{minimum},64}}", value):
        raise ValueError("Invalid identifier.")
    return value


def base_url(value: str) -> str:
    url = urlsplit(value)
    local = url.hostname in {"localhost", "127.0.0.1", "::1"}
    if (
        url.username
        or url.password
        or url.query
        or url.fragment
        or url.path.rstrip("/") != "/v1"
        or not (url.scheme == "https" and url.port in {None, 443} or url.scheme == "http" and local)
    ):
        raise ValueError("Use an HTTPS/443 API URL ending in /v1 (HTTP only on loopback).")
    return value.rstrip("/") + "/"


class API:
    def __init__(self, url: str, token: str, *, transport: Any = None):
        if not token or any(c.isspace() for c in token):
            raise ValueError("A valid credential is required in the environment.")
        self.client = httpx.AsyncClient(
            base_url=base_url(url),
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
            follow_redirects=False,
            transport=transport,
            trust_env=False,
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def request(self, method: str, path: str, body: Any = None) -> Any:
        try:
            response = await self.client.request(method, path, json=body)
            if not 200 <= response.status_code < 300:
                raise APIError(response.status_code)
            if response.status_code == 204:
                return None
            return response.json()
        except (httpx.HTTPError, ValueError):
            raise APIError() from None

    async def register(self, platform_channel: int) -> str:
        result = await self.request(
            "POST",
            "channels",
            {
                "platform": "discord",
                "platform_channel_id": str(platform_channel),
                "max_disclosure_level": "free_busy",
            },
        )
        try:
            return identifier(result["channel_id"], "chn")
        except (KeyError, TypeError, ValueError):
            raise APIError() from None

    async def summary(self, negotiation: str, channel: str) -> Any:
        identifier(negotiation, "neg")
        identifier(channel, "chn")
        return await self.request(
            "GET", f"negotiations/{negotiation}/channel-summary?channel_id={channel}"
        )
