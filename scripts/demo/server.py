#!/usr/bin/env python
"""Demo server: real PostgreSQL, real Redis, REAL Discord, mock inference.

Use this only while the Discord application's **Server Members Intent** is off. One
thing is substituted, and it is the one thing that intent provides: guild member
*enumeration*. The member list comes from `CAMPUSOS_DEMO_ROSTER` instead.

Everything else is live. Each member document is fetched from Discord, the production
`can_view()` runs against the real guild and channel documents, every guard in
`DiscordREST.audience` is kept including the bot-must-be-in-its-own-audience check, and
the consent fingerprint is computed over exactly the viewers that computation admits.

**Turn the intent on and delete this file.** Then
`uvicorn backend.app:create_app --factory` does the same thing with real enumeration,
and the demo is genuine end to end. Until then, no result produced through this server
is evidence about `audience()`'s pagination, deduplication or incomplete-page handling.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app import create_app
from backend.channels.discord import Audience, DiscordREST, can_view, fingerprint
from backend.common import Problem
from backend.config import Settings


class RosterDiscord(DiscordREST):
    """`DiscordREST` with the member list supplied rather than enumerated."""

    def __init__(self, token: str, roster: list[str]):
        super().__init__(token)
        self.roster = roster

    async def audience(self, channel: str, guild: str) -> Audience:
        try:
            server, room, identity = await self.context(channel, guild)
            visible = set()
            for uid in self.roster:
                member = await self.document(f"guilds/{guild}/members/{uid}")
                if can_view(member, server, room):
                    visible.add(member["user"]["id"])
            # Production's guard, kept: context() proved this bot can view the room, so
            # an audience without it means the member set is incomplete. Fail closed.
            if identity not in visible:
                raise Problem(503, "Channel verification unavailable")
            return Audience(guild, len(visible), fingerprint=fingerprint(channel, guild, visible))
        except (KeyError, TypeError, ValueError):
            raise Problem(503, "Channel verification unavailable") from None


def build():
    roster = [u for u in os.environ["CAMPUSOS_DEMO_ROSTER"].split(",") if u]
    if not roster:
        raise SystemExit("CAMPUSOS_DEMO_ROSTER must list the Discord user ids in the room")
    config = Settings.from_env()
    return create_app(config, discord=RosterDiscord(config.discord_token, roster))
