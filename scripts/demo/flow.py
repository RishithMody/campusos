"""Drive the full CampusOS consent flow against the live backend and real Discord.

Posts into the real #general channel only via the real T9 code path:
groupchat.api.API -> groupchat.publisher.Publisher -> groupchat.render.render.
"""

import asyncio
import pathlib
import re
import sys
from datetime import timedelta

import httpx
import jwt

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.common import now  # noqa: E402
from groupchat.api import API  # noqa: E402
from groupchat.publisher import Publisher  # noqa: E402

ENV_FILE = ROOT / ".env"
env = {}
for line in ENV_FILE.read_text().splitlines():
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line.strip())
    if m:
        env[m.group(1)] = m.group(2).strip().strip('"').strip("'")

KEY = env["CAMPUSOS_JWT_KEY"]
BASE = "http://127.0.0.1:8000/v1"
GUILD, CHANNEL_ID = env["DISCORD_GUILD_ID"], env["DISCORD_CHANNEL_ID"]
DISCORD_TOKEN = env["DISCORD_BOT_TOKEN"]
STUDENTS = {"alice": "alice-demo", "bob": "bob-demo", "carol": "carol-demo"}
AGENTS = {}

posted = []


def token(subject, kind="human", **extra):
    claims = {
        "sub": subject,
        "kind": kind,
        "iat": now(),
        "exp": now() + timedelta(hours=2),
        "iss": "campusos",
        "aud": "campusos-api",
        **extra,
    }
    return jwt.encode(claims, KEY, algorithm="HS256")


def headers(who, kind="human", **extra):
    subject = STUDENTS.get(who, who)
    if kind == "agent":
        extra.setdefault("agent_id", AGENTS[who])
    return {"Authorization": "Bearer " + token(subject, kind, **extra)}


def call(method, path, who="alice", kind="human", body=None, expect=None, **extra):
    r = httpx.request(
        method, BASE + path, headers=headers(who, kind, **extra), json=body, timeout=30
    )
    if expect is not None and r.status_code != expect:
        raise SystemExit(f"{method} {path} -> {r.status_code} (wanted {expect})\n{r.text[:400]}")
    return r


def step(n, text):
    print(f"\n\033[1m{n}. {text}\033[0m")


async def send_to_discord(text):
    """Exactly what groupchat.bot's `send` does: post the rendered sentence, no mentions."""
    async with httpx.AsyncClient(base_url="https://discord.com/api/v10/") as client:
        r = await client.post(
            f"channels/{CHANNEL_ID}/messages",
            headers={"Authorization": f"Bot {DISCORD_TOKEN}"},
            json={"content": text, "allowed_mentions": {"parse": []}},
            timeout=20,
        )
        r.raise_for_status()
        posted.append(text)
        print(f"   \033[32m-> posted to #general:\033[0m {text!r}")


def main():
    step(1, "Each student reads their own contact handle (GET /v1/me)")
    handles = {}
    for who in STUDENTS:
        handles[who] = call("GET", "/me", who, expect=200).json()["contact_handle"]
        print(f"   {who:6} {handles[who]}")

    step(2, "Alice creates a negotiation inviting Bob and Carol")
    start = (now() + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0)
    window = {"start": start.isoformat(), "end": (start + timedelta(hours=5)).isoformat()}
    state = call(
        "POST",
        "/negotiations",
        "alice",
        body={
            "invitees": [handles["bob"], handles["carol"]],
            "window": window,
            "max_rounds": 5,
            "min_duration_minutes": 60,
            "title": "study group",
        },
        expect=201,
    ).json()
    neg = state["negotiation_id"]
    print(f"   {neg}  status={state['status']}")
    for who in STUDENTS:
        AGENTS[who] = call("GET", f"/negotiations/{neg}", who, expect=200).json()["viewer"][
            "agent_id"
        ]

    step(3, "Every student grants every other agent a scoped, expiring free/busy grant")
    for owner in STUDENTS:
        for other in STUDENTS:
            if owner == other:
                continue
            call(
                "POST",
                "/grants",
                owner,
                body={
                    "negotiation_id": neg,
                    "grantee_agent_id": AGENTS[other],
                    "max_disclosure_level": "free_busy",
                    "expires_at": window["end"],
                },
                expect=201,
            )
    print("   6 grants created. Invitation alone granted nothing.")

    step(4, "Each student submits free/busy only -- no titles, no reasons")
    for i, who in enumerate(STUDENTS):
        own = call("GET", f"/negotiations/{neg}", who, expect=200).json()
        slot_start = start + timedelta(hours=i)
        call(
            "PUT",
            "/me/availability",
            who,
            body={
                "schema_version": "1.0",
                "student_ref": own["viewer"]["student_ref"],
                "generated_at": now().isoformat(),
                "timezone": "UTC",
                "window": window,
                "disclosure_level": "free_busy",
                "slots": [{"start": slot_start.isoformat(), "end": window["end"], "state": "free"}],
            },
            expect=204,
        )
    final = call("GET", f"/negotiations/{neg}", "alice", expect=200).json()
    print(f"   status={final['status']}  proposals={len(final['proposals'])}")
    if final["proposals"]:
        s = final["proposals"][-1]["slot"]
        print(f"   agents proposed: {s['start']} -> {s['end']}")

    step(5, "The bot registers the REAL Discord channel (audience verified against Discord)")
    reg = call(
        "POST",
        "/channels",
        "campusos-bot",
        "bot",
        body={
            "platform": "discord",
            "platform_channel_id": CHANNEL_ID,
            "max_disclosure_level": "free_busy",
        },
        guild=GUILD,
        expect=201,
    ).json()
    channel = reg["channel_id"]
    print(f"   {channel}  (confirmed={reg['confirmed']})")

    step(6, "Alice links her verified Discord identity to that channel")
    call("POST", f"/channels/{channel}/members", "alice", expect=204)
    print("   204 -- Discord confirmed she can actually view the room")

    step(7, "Alice requests a channel binding; approvals go out to all three")
    binding = call(
        "POST",
        f"/negotiations/{neg}/channel-bindings",
        "alice",
        body={"channel_id": channel},
        expect=201,
    ).json()
    print(
        f"   status={binding['status']}  outstanding={binding['confirmations_outstanding']}"
        f"  audience_size_at_consent={binding['audience_size_at_consent']}"
    )

    step(8, "Before consent, the bot asks for the summary")
    r = call(
        "GET",
        f"/negotiations/{neg}/channel-summary?channel_id={channel}",
        "campusos-bot",
        "bot",
        guild=GUILD,
    )
    print(f"   HTTP {r.status_code}  body={r.text.strip()}")

    async def publish_once(_label):
        api = API(BASE, token("campusos-bot", "bot", guild=GUILD))
        try:
            keep = await Publisher(api).update(neg, channel, send_to_discord)
            print(f"   publisher kept watching: {keep}")
        finally:
            await api.close()

    print("   the real T9 publisher, given that refusal:")
    asyncio.run(publish_once("pre-consent"))
    print(f"   messages posted to Discord so far: {len(posted)}")

    step(9, "All three students approve the channel disclosure")
    for who in STUDENTS:
        s = call("GET", f"/negotiations/{neg}", who, expect=200).json()
        appr = next(a for a in s["pending_approvals"] if a["action"] == "post_to_channel")
        print(f"   {who:6} is shown: {appr['discloses']['summary']}")
        call(
            "POST",
            f"/approvals/{appr['approval_id']}",
            who,
            body={"decision": "approve", "state_version": appr["state_version"]},
            expect=200,
        )
    b = call("GET", f"/negotiations/{neg}/channel-bindings", "alice", expect=200).json()[
        "bindings"
    ][0]
    print(f"   binding now: status={b['status']} outstanding={b['confirmations_outstanding']}")

    step(10, "Now the bot may read the summary -- and posts it to the real channel")
    r = call(
        "GET",
        f"/negotiations/{neg}/channel-summary?channel_id={channel}",
        "campusos-bot",
        "bot",
        guild=GUILD,
        expect=200,
    )
    print(f"   HTTP 200  {r.json()}")
    asyncio.run(publish_once("consented"))

    return neg, channel, window


if __name__ == "__main__":
    negotiation, room, _ = main()
    print(f"\n\033[1mMessages actually posted to Discord: {len(posted)}\033[0m")
    for sentence in posted:
        print(f"   {sentence!r}")
    print(f"\n\033[1mNow run this in the channel:\033[0m  /watch {negotiation}")
    print(f"   (channel {room})")
