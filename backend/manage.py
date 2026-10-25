"""Trusted local account provisioning. Never exposed through an HTTP route."""

import argparse
import asyncio
import os
from datetime import timedelta

import httpx
import jwt

from backend.common import identifier, now
from backend.config import Settings
from backend.db.models import Student
from backend.db.session import database

MAX_BOT_TOKEN_HOURS = 24


async def verified_discord_identity(token: str) -> str:
    async with httpx.AsyncClient(base_url="https://discord.com/api/v10/") as client:
        response = await client.get(
            "users/@me", headers={"Authorization": f"Bearer {token}"}, timeout=5
        )
        if response.status_code != 200:
            raise ValueError("Discord OAuth identity verification failed")
        user = response.json().get("id")
        if not isinstance(user, str) or not user.isdigit():
            raise ValueError("Discord OAuth identity verification failed")
        return user


def bot_token(config: Settings, subject: str, guild: str, hours: int) -> str:
    """Mint the guild-bound service credential a channel bot presents.

    Not a student credential and never interchangeable with one: `kind` is `bot`, and
    `Service.student()` refuses that kind outright, so this token cannot read a
    negotiation, submit availability, or answer an approval. It authorises exactly two
    things -- registering a channel and reading a consented channel summary.
    """
    if not guild.isdigit():
        raise ValueError("Guild must be a numeric Discord snowflake")
    if not 1 <= hours <= MAX_BOT_TOKEN_HOURS:
        raise ValueError(f"Token lifetime must be between 1 and {MAX_BOT_TOKEN_HOURS} hours")
    claims = {
        "sub": subject,
        "kind": "bot",
        "guild": guild,
        "iat": now(),
        "exp": now() + timedelta(hours=hours),
        "iss": config.jwt_issuer,
        "aud": config.jwt_audience,
    }
    return jwt.encode(claims, config.jwt_key, algorithm="HS256")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["provision", "link-discord", "issue-bot"])
    parser.add_argument("subject", help="Subject from the trusted identity issuer")
    parser.add_argument("--guild", default="", help="issue-bot: the one Discord guild id")
    parser.add_argument(
        "--ttl", type=int, default=12, help=f"issue-bot: hours, max {MAX_BOT_TOKEN_HOURS}"
    )
    args = parser.parse_args()
    config = Settings.from_env()
    engine, sessions = database(config.database_url)
    try:
        with sessions.begin() as session:
            student = session.get(Student, args.subject)
            if args.action == "issue-bot":
                # A bot subject must never also be a student. The kind check already
                # refuses it, but one subject meaning two principals is how that kind of
                # check eventually gets reasoned away.
                if student is not None:
                    raise ValueError("That subject is a provisioned student, not a bot")
                token = bot_token(config, args.subject, args.guild, args.ttl)
                print(token)
                print(
                    "Issued once and not stored. Put it in the bot process environment as "
                    "CAMPUSOS_BOT_TOKEN. Never commit it, never give it to a student.",
                )
                return
            if args.action == "provision":
                if student is not None:
                    raise ValueError("Account already exists")
                session.add(
                    Student(
                        id=args.subject,
                        agent_id=identifier("agt"),
                        contact_handle=identifier("cnt"),
                        ceiling="free_busy",
                    )
                )
            else:
                if student is None:
                    raise ValueError("Account must be provisioned first")
                # The operator must bind the authenticated CampusOS subject to this
                # student's OAuth ceremony. Never take a Discord ID asserted by a bot.
                token = os.environ.get("CAMPUSOS_DISCORD_OAUTH_ACCESS_TOKEN", "")
                if not token:
                    raise ValueError("Student OAuth access token is required")
                student.discord_id = asyncio.run(verified_discord_identity(token))
        print("Account operation completed; no credentials retained.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
