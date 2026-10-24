from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from backend.common import Problem


class Ephemeral:
    """Redis contains opaque negotiation IDs and versions, never calendar payloads."""

    def __init__(self, client: Any, ttl: int = 300):
        self.client = client
        self.ttl = ttl

    @classmethod
    def connect(cls, url: str, ttl: int = 300) -> "Ephemeral":
        return cls(Redis.from_url(url, decode_responses=True, socket_timeout=2), ttl)

    async def ping(self) -> None:
        try:
            await self.client.ping()
        except (RedisError, OSError):
            raise Problem(503, "State notifications unavailable") from None

    async def publish(self, negotiation: str, version: int) -> None:
        try:
            async with self.client.pipeline(transaction=True) as pipe:
                pipe.set(f"session:{negotiation}", str(version), ex=self.ttl)
                pipe.publish(f"updates:{negotiation}", str(version))
                await pipe.execute()
        except (RedisError, OSError):
            raise Problem(503, "State notifications unavailable") from None
