from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from backend.common import Problem

VIEW_CHANNEL = 1 << 10
ADMINISTRATOR = 1 << 3


@dataclass(frozen=True)
class Audience:
    guild: str
    size: int
    timezone: str = "UTC"


class Discord(Protocol):
    async def audience(self, channel: str, guild: str) -> Audience: ...
    async def member(self, channel: str, guild: str, user: str) -> bool: ...


def can_view(member: dict[str, Any], guild: dict[str, Any], channel: dict[str, Any]) -> bool:
    """Discord's guild base, everyone, aggregate role, then member overwrite order."""
    user = member["user"]["id"]
    if user == guild["owner_id"]:
        return True
    roles = {r["id"]: int(r["permissions"]) for r in guild["roles"]}
    permission = roles.get(guild["id"], 0)
    for role in member["roles"]:
        permission |= roles.get(role, 0)
    if permission & ADMINISTRATOR:
        return True
    overrides = channel.get("permission_overwrites", [])
    for overwrite in overrides:
        if overwrite["id"] == guild["id"]:
            permission = (permission & ~int(overwrite["deny"])) | int(overwrite["allow"])
    deny, allow = 0, 0
    for overwrite in overrides:
        if overwrite["type"] == 0 and overwrite["id"] in member["roles"]:
            deny |= int(overwrite["deny"])
            allow |= int(overwrite["allow"])
    permission = (permission & ~deny) | allow
    for overwrite in overrides:
        if overwrite["type"] == 1 and overwrite["id"] == user:
            permission = (permission & ~int(overwrite["deny"])) | int(overwrite["allow"])
    return bool(permission & VIEW_CHANNEL)


class DiscordREST:
    """Verifies text-channel permissions and enumerates its actual current audience.

    Requires Guild Members intent. Incomplete pagination or unsupported thread/DM
    channels fail closed. No approximate guild counts are used for consent.
    """

    def __init__(self, token: str, transport: Any = None):
        self.token = token
        self.transport = transport

    async def fetch(self, path: str):
        if not self.token:
            raise Problem(503, "Channel verification unavailable")
        try:
            async with httpx.AsyncClient(
                base_url="https://discord.com/api/v10/",
                headers={"Authorization": f"Bot {self.token}"},
                transport=self.transport,
            ) as client:
                response = await client.get(path, timeout=5)
                if response.status_code != 200:
                    raise Problem(403)
                return response.json()
        except (httpx.HTTPError, ValueError):
            raise Problem(503, "Channel verification unavailable") from None

    async def document(self, path: str) -> dict[str, Any]:
        """A 200 is not enough: the body has to be the object we asked for.

        Without this, a non-object body reaches `.get(...)` and escapes as AttributeError
        instead of the service's fail-closed 503, surfacing to the caller as a 500.
        """
        value = await self.fetch(path)
        if not isinstance(value, dict):
            raise Problem(503, "Channel verification unavailable")
        return value

    async def context(self, channel: str, guild: str):
        if not channel.isdigit() or not guild.isdigit():
            raise Problem(403)
        room = await self.document(f"channels/{channel}")
        if room.get("guild_id") != guild or room.get("type") != 0:
            raise Problem(403)
        server = await self.document(f"guilds/{guild}")
        bot = await self.document("users/@me")
        identity = bot.get("id")
        if not isinstance(identity, str) or not identity.isdigit():
            raise Problem(503, "Channel verification unavailable")
        membership = await self.document(f"guilds/{guild}/members/{identity}")
        if not can_view(membership, server, room):
            raise Problem(403)
        return server, room, identity

    async def audience(self, channel: str, guild: str) -> Audience:
        try:
            server, room, identity = await self.context(channel, guild)
            after, visible = "0", set()
            for _page in range(100):
                members = await self.fetch(f"guilds/{guild}/members?limit=1000&after={after}")
                if not isinstance(members, list):
                    raise Problem(503, "Channel verification unavailable")
                for member in members:
                    if can_view(member, server, room):
                        visible.add(member["user"]["id"])
                if len(members) < 1000:
                    # context() already proved this bot is a member who can view the room,
                    # so a result without it means the enumeration was incomplete. Consent
                    # is given against this number, and an undercount is the dangerous
                    # direction: re-consent only fires when the audience GREW.
                    if identity not in visible:
                        raise Problem(503, "Channel verification unavailable")
                    return Audience(guild, len(visible))
                following = str(max(int(m["user"]["id"]) for m in members))
                if int(following) <= int(after):
                    break
                after = following
            raise Problem(503, "Channel verification unavailable")
        except (KeyError, TypeError, ValueError):
            raise Problem(503, "Channel verification unavailable") from None

    async def member(self, channel: str, guild: str, user: str) -> bool:
        if not user.isdigit():
            return False
        try:
            server, room, _ = await self.context(channel, guild)
            membership = await self.document(f"guilds/{guild}/members/{user}")
            return can_view(membership, server, room)
        except (KeyError, TypeError, ValueError):
            raise Problem(503, "Channel verification unavailable") from None
