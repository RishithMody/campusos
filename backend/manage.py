"""Trusted local account provisioning. Never exposed through an HTTP route."""

import argparse
import asyncio
import os

import httpx

from backend.common import identifier
from backend.config import Settings
from backend.db.models import Student
from backend.db.session import database


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["provision", "link-discord"])
    parser.add_argument("subject", help="Subject from the trusted identity issuer")
    args = parser.parse_args()
    config = Settings.from_env()
    engine, sessions = database(config.database_url)
    try:
        with sessions.begin() as session:
            student = session.get(Student, args.subject)
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
