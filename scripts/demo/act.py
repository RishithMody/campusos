#!/usr/bin/env python
"""Stage-manager for a live CampusOS demo. One short command per beat.

    check       everything that has to be up, before you walk on stage
    seed        provision the three demo students, once per database
    stage       a fresh negotiation, consented and ready to /watch. Posts nothing
    changed     the channel's membership changes -> re-consent required
    restored    put the room back as it was
    reconsent   all three approve the audience as it now stands
    converge    all three confirm the time -> "Locked in: ..." posts live
    withdraw    one student revokes channel consent -> posting stops
    say         print the current state in words, for the room
    watch       run the real watcher from the terminal -- the same code /watch runs,
                in case the slash-command UI misbehaves on stage

Read-only by default: `check` and `say` change nothing. Everything else is a
deliberate beat you trigger.
"""

import argparse
import asyncio
import json
import os
import pathlib
import re
import subprocess
import sys
from datetime import timedelta

import httpx
import jwt

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.common import now  # noqa: E402
from groupchat.api import API  # noqa: E402
from groupchat.publisher import Publisher  # noqa: E402

BASE = "http://127.0.0.1:8000/v1"
STUDENTS = {"alice": "alice-demo", "bob": "bob-demo", "carol": "carol-demo"}
ROSTER_FILE = pathlib.Path(__file__).resolve().parent / "roster.txt"
DEFAULT_ROSTER = pathlib.Path(__file__).resolve().parent / "roster.default.txt"
STATE_FILE = pathlib.Path(__file__).resolve().parent / "state.json"

env = {}
for line in (ROOT / ".env").read_text().splitlines():
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line.strip())
    if m:
        env[m.group(1)] = m.group(2).strip().strip('"').strip("'")

KEY = env["CAMPUSOS_JWT_KEY"]
GUILD, CHANNEL_ID = env["DISCORD_GUILD_ID"], env["DISCORD_CHANNEL_ID"]
DISCORD_TOKEN = env["DISCORD_BOT_TOKEN"]

GREEN, RED, YELLOW, BOLD, OFF = "\033[32m", "\033[31m", "\033[33m", "\033[1m", "\033[0m"


def token(subject, kind="human", **extra):
    return jwt.encode(
        {
            "sub": subject,
            "kind": kind,
            "iat": now(),
            "exp": now() + timedelta(hours=3),
            "iss": "campusos",
            "aud": "campusos-api",
            **extra,
        },
        KEY,
        algorithm="HS256",
    )


def call(method, path, who="alice", kind="human", body=None, expect=None, **extra):
    head = {"Authorization": "Bearer " + token(STUDENTS.get(who, who), kind, **extra)}
    r = httpx.request(method, BASE + path, headers=head, json=body, timeout=30)
    if expect is not None and r.status_code != expect:
        sys.exit(f"{RED}{method} {path} -> {r.status_code}, wanted {expect}{OFF}\n{r.text[:400]}")
    return r


def discord(method, path, body=None):
    return httpx.request(
        method,
        "https://discord.com/api/v10/" + path,
        headers={"Authorization": f"Bot {DISCORD_TOKEN}"},
        json=body,
        timeout=20,
    )


def state():
    if not STATE_FILE.exists():
        sys.exit(f"{RED}no staged negotiation -- run: act.py stage{OFF}")
    return json.loads(STATE_FILE.read_text())


def binding(neg, channel):
    bs = call("GET", f"/negotiations/{neg}/channel-bindings", expect=200).json()["bindings"]
    return next((b for b in bs if b["channel_id"] == channel), None)


def approve(neg, action):
    for who in STUDENTS:
        s = call("GET", f"/negotiations/{neg}", who, expect=200).json()
        pending = [a for a in s["pending_approvals"] if a["action"] == action]
        if not pending:
            print(f"   {who}: nothing to approve ({action})")
            continue
        a = pending[0]
        call(
            "POST",
            f"/approvals/{a['approval_id']}",
            who,
            body={"decision": "approve", "state_version": a["state_version"]},
            expect=200,
        )
        print(f"   {GREEN}{who} approved{OFF}")


# ----------------------------------------------------------------------- commands


def cmd_check(_args):
    ok = True

    def line(good, label, detail=""):
        nonlocal ok
        ok = ok and good
        mark = f"{GREEN}OK  {OFF}" if good else f"{RED}FAIL{OFF}"
        print(f"  {mark} {label}" + (f"   {detail}" if detail else ""))

    print(f"\n{BOLD}Services{OFF}")
    try:
        r = httpx.get(BASE + "/health", timeout=5)
        line(r.status_code == 401, "backend on :8000", f"unauthenticated health -> {r.status_code}")
    except Exception as e:
        line(False, "backend on :8000", f"{type(e).__name__} -- not running")
    bot_up = (
        subprocess.run(  # noqa: S603
            ["/usr/bin/pgrep", "-f", "groupchat.bot"], capture_output=True, check=False
        ).returncode
        == 0
    )
    line(bot_up, "Discord bot process")

    print(f"\n{BOLD}Discord{OFF}")
    me = discord("GET", "users/@me")
    line(
        me.status_code == 200,
        "bot credential",
        me.json().get("username", "") if me.status_code == 200 else me.text[:80],
    )
    room = discord("GET", f"channels/{CHANNEL_ID}")
    line(
        room.status_code == 200 and room.json().get("type") == 0,
        "channel is a guild text channel",
        f"#{room.json().get('name')}" if room.status_code == 200 else room.text[:80],
    )
    app = discord("GET", "applications/@me")
    intent = bool(app.json().get("flags", 0) & (1 << 16)) if app.status_code == 200 else False
    print(
        f"  {GREEN}OK  {OFF} Server Members Intent"
        if intent
        else f"  {YELLOW}NOTE{OFF} Server Members Intent is OFF -- the demo server supplies the"
        f" member list ({ROSTER_FILE.name})"
    )
    cmds = discord("GET", f"applications/{env['DISCORD_CLIENT_ID']}/guilds/{GUILD}/commands")
    names = sorted(c["name"] for c in cmds.json()) if cmds.status_code == 200 else []
    line(
        names == ["schedule", "watch"],
        "slash commands registered",
        ", ".join(f"/{n}" for n in names),
    )

    print(f"\n{BOLD}Credentials{OFF}")
    line(
        bool(env.get("DISCORD_BOT_TOKEN"))
        and env.get("CAMPUSOS_DISCORD_TOKEN") == env.get("DISCORD_BOT_TOKEN"),
        "backend's Discord token matches the bot's",
        "it verifies the channel audience with this; a placeholder fails every binding closed",
    )
    # The .env credential, not one minted here. An expired CAMPUSOS_BOT_TOKEN is refused
    # with the same uniform 403 as "nobody consented" -- correct, and indistinguishable
    # on stage. The one in .env had silently expired before a rehearsal.
    try:
        claims = jwt.decode(
            env.get("CAMPUSOS_BOT_TOKEN", ""),
            KEY,
            algorithms=["HS256"],
            issuer="campusos",
            audience="campusos-api",
        )
        hours = (claims["exp"] - now().timestamp()) / 3600
        line(
            claims.get("kind") == "bot" and claims.get("guild") == GUILD,
            "CAMPUSOS_BOT_TOKEN in .env",
            f"kind={claims.get('kind')}, guild matches, {hours:.1f}h left",
        )
        if hours < 2:
            print(f"  {YELLOW}NOTE{OFF} under two hours left. Re-mint and restart the bot:")
            print(
                "          export CAMPUSOS_BOT_TOKEN=$(backend/.venv/bin/python -m "
                "backend.manage \\\n            issue-bot campusos-bot --guild "
                '"$DISCORD_GUILD_ID" --ttl 24 | head -1)'
            )
    except jwt.ExpiredSignatureError:
        line(False, "CAMPUSOS_BOT_TOKEN in .env", "EXPIRED -- re-mint it and restart the bot")
    except (jwt.InvalidTokenError, KeyError, TypeError) as e:
        line(False, "CAMPUSOS_BOT_TOKEN in .env", f"{type(e).__name__} -- re-mint it")

    print(f"\n{BOLD}Room{OFF}")
    ids = [u for u in ROSTER_FILE.read_text().split() if u] if ROSTER_FILE.exists() else []
    line(bool(ids), f"{ROSTER_FILE.name}", f"{len(ids)} account(s) can read the channel")

    print(f"\n{BOLD}Staged negotiation{OFF}")
    try:
        if (
            httpx.get(
                BASE + "/me",
                headers={"Authorization": "Bearer " + token(STUDENTS["alice"])},
                timeout=10,
            ).status_code
            != 200
        ):
            line(False, "demo students provisioned", "run: act.py seed")
            print()
            print(f"{RED}{BOLD}Not ready -- see FAIL above.{OFF}\n")
            return 1
    except Exception as e:
        line(False, "backend reachable for /me", f"{type(e).__name__}")
    if not STATE_FILE.exists():
        line(False, "staged", "run: act.py stage")
    else:
        s = state()
        try:
            view = call("GET", f"/negotiations/{s['negotiation']}", expect=200).json()
            b = binding(s["negotiation"], s["channel"])
            line(True, "negotiation", f"{s['negotiation']}  status={view['status']}")
            line(
                b is not None and b["status"] == "confirmed",
                "channel binding",
                f"status={b['status'] if b else 'missing'}",
            )
            # Deliberately the .env credential: that is the one the bot presents, and a
            # locally minted stand-in would hide exactly the failure that bit us.
            summary = httpx.get(
                BASE + f"/negotiations/{s['negotiation']}/channel-summary"
                f"?channel_id={s['channel']}",
                headers={"Authorization": "Bearer " + env.get("CAMPUSOS_BOT_TOKEN", "")},
                timeout=30,
            )
            note = ""
            if summary.status_code == 200:
                note = f"  template={summary.json()['template_id']}"
            elif summary.status_code == 503:
                note = (
                    "  Discord throttled us -- wait two seconds and re-run; not a consent problem"
                )
            line(
                summary.status_code == 200,
                "bot may read the summary",
                f"HTTP {summary.status_code}{note}",
            )
        except SystemExit:
            raise
        except Exception as e:
            line(False, "negotiation reachable", f"{type(e).__name__}")

    print()
    if ok:
        print(
            f"{GREEN}{BOLD}Ready.{OFF}  In the channel run:  /watch {state()['negotiation']}\n"
            if STATE_FILE.exists()
            else f"{GREEN}{BOLD}Ready to stage.{OFF}\n"
        )
    else:
        print(
            f"{RED}{BOLD}Not ready -- see FAIL above. scripts/demo/PRESENTATION.md has the fixes.{OFF}\n"
        )
    return 0 if ok else 1


def cmd_seed(_args):
    """Provision the three demo students and link one Discord identity.

    The link is the one control this cannot satisfy honestly. `manage link-discord`
    verifies the student's own OAuth access token against Discord's `users/@me`; we have
    no OAuth callback, so with CAMPUSOS_DISCORD_OAUTH_ACCESS_TOKEN set it uses the real
    command, and without it the operator asserts the id taken from the guild's owner_id.
    An asserted link is not a proved one, and the demo says so out loud rather than
    quietly standing in for a ceremony that did not happen.
    """
    python = str(ROOT / "backend/.venv/bin/python")
    for subject in STUDENTS.values():
        r = subprocess.run(  # noqa: S603
            [python, "-m", "backend.manage", "provision", subject],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        done = r.returncode == 0
        note = "provisioned" if done else r.stderr.strip().splitlines()[-1][:60]
        print(f"  {GREEN + 'OK  ' + OFF if done else YELLOW + 'NOTE' + OFF} {subject}: {note}")

    status, guild = (
        discord("GET", f"guilds/{GUILD}").status_code,
        discord("GET", f"guilds/{GUILD}").json(),
    )
    if status != 200:
        sys.exit(f"{RED}cannot read the guild to find a Discord identity to link{OFF}")
    owner = guild["owner_id"]
    linked = STUDENTS["alice"]

    if os.environ.get("CAMPUSOS_DISCORD_OAUTH_ACCESS_TOKEN"):
        r = subprocess.run(  # noqa: S603
            [python, "-m", "backend.manage", "link-discord", linked],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        ok = r.returncode == 0
        print(
            f"  {GREEN + 'OK  ' + OFF if ok else RED + 'FAIL' + OFF} {linked}: "
            f"Discord identity verified by OAuth"
            + ("" if ok else f" -- {r.stderr.strip().splitlines()[-1][:70]}")
        )
        return
    import sqlalchemy

    engine = sqlalchemy.create_engine(env["CAMPUSOS_DATABASE_URL"])
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("UPDATE students SET discord_id = :d WHERE id = :s"),
            {"d": owner, "s": linked},
        )
    engine.dispose()
    print(f"  {YELLOW}NOTE{OFF} {linked}: discord_id set to the guild owner ({owner}) by the")
    print("          operator. No OAuth ceremony happened -- this link is asserted, not")
    print("          proved. Set CAMPUSOS_DISCORD_OAUTH_ACCESS_TOKEN to do it properly.")


def cmd_stage(_args):
    print(f"{BOLD}Staging a fresh negotiation (nothing is posted to Discord){OFF}")
    handles = {w: call("GET", "/me", w, expect=200).json()["contact_handle"] for w in STUDENTS}
    start = (now() + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0)
    window = {"start": start.isoformat(), "end": (start + timedelta(hours=5)).isoformat()}
    neg = call(
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
    ).json()["negotiation_id"]
    print(f"   negotiation {neg}")

    agents = {
        w: call("GET", f"/negotiations/{neg}", w, expect=200).json()["viewer"]["agent_id"]
        for w in STUDENTS
    }
    for owner in STUDENTS:
        for other in STUDENTS:
            if owner != other:
                call(
                    "POST",
                    "/grants",
                    owner,
                    body={
                        "negotiation_id": neg,
                        "grantee_agent_id": agents[other],
                        "max_disclosure_level": "free_busy",
                        "expires_at": window["end"],
                    },
                    expect=201,
                )
    print("   6 grants")

    for i, who in enumerate(STUDENTS):
        own = call("GET", f"/negotiations/{neg}", who, expect=200).json()
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
                "slots": [
                    {
                        "start": (start + timedelta(hours=i)).isoformat(),
                        "end": window["end"],
                        "state": "free",
                    }
                ],
            },
            expect=204,
        )
    view = call("GET", f"/negotiations/{neg}", expect=200).json()
    print(f"   availability in; status={view['status']}")
    if view["proposals"]:
        s = view["proposals"][-1]["slot"]
        print(f"   agents proposed {s['start']} -> {s['end']}")

    channel = call(
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
    ).json()["channel_id"]
    call("POST", f"/channels/{channel}/members", "alice", expect=204)
    call(
        "POST",
        f"/negotiations/{neg}/channel-bindings",
        "alice",
        body={"channel_id": channel},
        expect=201,
    )
    approve(neg, "post_to_channel")
    b = binding(neg, channel)
    print(f"   binding {b['status']}, audience_size_at_consent={b['audience_size_at_consent']}")
    STATE_FILE.write_text(json.dumps({"negotiation": neg, "channel": channel}, indent=2) + "\n")
    print(f"\n{BOLD}In the channel run:{OFF}  /watch {neg}\n")


def cmd_changed(_args):
    """Change who can read the room.

    Shown as a member leaving, because the test guild holds two accounts and Discord will
    not answer a member fetch for an id that is not in it -- an invented id fails closed
    instead, which is correct but is not what we are demonstrating. The gate compares
    audience *identity*, so a join and a same-size swap fire it identically. To show a
    literal join, add a second account to the server and append its user id to
    roster.default.txt.
    """
    ids = [u for u in ROSTER_FILE.read_text().split() if u]
    if len(ids) < 2:
        print(f"{YELLOW}only one account in the room already -- run `restored` first{OFF}")
        return
    ROSTER_FILE.write_text("\n".join(ids[:-1]) + "\n")
    print(
        f"{BOLD}Who can read the channel just changed.{OFF} {len(ids)} accounts -> {len(ids) - 1}."
    )
    print("   Nobody told CampusOS. Its next read recomputes the audience, finds a different")
    print("   one than the three students agreed to, and stops. Watch the bot go quiet.")


def cmd_restored(_args):
    ROSTER_FILE.write_text(DEFAULT_ROSTER.read_text())
    ids = [u for u in ROSTER_FILE.read_text().split() if u]
    print(f"{BOLD}The room is back as it was.{OFF} {len(ids)} accounts.")
    print("   Consent is still required: the binding is pinned to the audience that was")
    print("   approved, and going back is a change too.")


def cmd_reconsent(_args):
    s = state()
    print(f"{BOLD}All three approve the audience as it now stands{OFF}")
    approve(s["negotiation"], "post_to_channel")
    b = binding(s["negotiation"], s["channel"])
    print(f"   binding {b['status']}, audience_size_at_consent={b['audience_size_at_consent']}")
    print(f"\n{BOLD}In the channel run:{OFF}  /watch {s['negotiation']}\n")


def cmd_converge(_args):
    s = state()
    print(f"{BOLD}All three confirm the time{OFF}")
    approve(s["negotiation"], "commit_slot")
    view = call("GET", f"/negotiations/{s['negotiation']}", expect=200).json()
    print(f"   status={view['status']}  outcome={view.get('outcome', {}).get('kind')}")
    slot = view.get("outcome", {}).get("agreed_slot")
    if slot:
        print(f"   agreed {slot['start']} -> {slot['end']}")
    print(f"\n   {GREEN}If /watch is running, 'Locked in: ...' appears within 10 seconds.{OFF}\n")


def cmd_withdraw(args):
    s = state()
    call(
        "DELETE",
        f"/negotiations/{s['negotiation']}/channel-bindings/{s['channel']}",
        args.who,
        expect=204,
    )
    print(
        f"{BOLD}{args.who} revoked channel consent.{OFF}  binding "
        f"{binding(s['negotiation'], s['channel'])['status']}"
    )
    print("   One withdrawal ends it for everyone -- an audience cannot be partly un-told.")
    print("   Messages already posted stay posted. Nothing further is published.\n")


def cmd_watch(args):
    """The same thing `/watch` does, driven from a terminal.

    `groupchat.bot.publish` is this loop: one `Publisher`, re-authorized before every
    post, ten seconds apart, stopping the moment it is refused. Nothing here is a
    shortcut around the consent gate -- it is the gate's own client.
    """
    s = state()
    neg, channel = s["negotiation"], s["channel"]

    async def send(text):
        r = discord(
            "POST",
            f"channels/{CHANNEL_ID}/messages",
            {"content": text, "allowed_mentions": {"parse": []}},
        )
        r.raise_for_status()
        print(f"   {GREEN}posted to the channel:{OFF} {text!r}")

    async def go():
        api = API(BASE, token("campusos-bot", "bot", guild=GUILD))
        publisher = Publisher(api)
        try:
            for tick in range(max(1, args.seconds // 10)):
                if not await publisher.update(neg, channel, send):
                    settled = call("GET", f"/negotiations/{neg}", expect=200).json()["status"]
                    if settled in {"converged", "failed", "expired", "cancelled"}:
                        print(
                            f"   {GREEN}the negotiation is settled ({settled})"
                            f" -- nothing left to say.{OFF}"
                        )
                    else:
                        print(f"   {YELLOW}refused -- the watcher stops and will not retry.{OFF}")
                        print("   A human re-authorizes, then starts a new watcher.")
                    return
                if tick == 0:
                    print("   authorized. re-checking every 10s; it posts only on a change.")
                await asyncio.sleep(10)
            print("   watch window ended.")
        finally:
            await api.close()

    print(f"{BOLD}Watching {neg}{OFF}")
    asyncio.run(go())


def cmd_say(_args):
    s = state()
    view = call("GET", f"/negotiations/{s['negotiation']}", expect=200).json()
    # Ask for the summary FIRST: that read is what re-derives the audience and moves a
    # binding to pending_reconsent. Reading the binding before it would show the stale
    # status and make the gate look like it had not fired.
    summary = call(
        "GET",
        f"/negotiations/{s['negotiation']}/channel-summary?channel_id={s['channel']}",
        "campusos-bot",
        "bot",
        guild=GUILD,
    )
    b = binding(s["negotiation"], s["channel"])
    room = [u for u in ROSTER_FILE.read_text().split() if u]
    print(f"\n  negotiation   {s['negotiation']}   status={view['status']}")
    print(f"  channel       {s['channel']}   binding={b['status'] if b else 'none'}")
    print(
        f"  consented to  {b['audience_size_at_consent'] if b else '-'} accounts;"
        f" the room now holds {len(room)}"
    )
    print(
        f"  the bot asks  HTTP {summary.status_code}"
        + (
            f"   -> {summary.json()['template_id']}"
            if summary.status_code == 200
            else "   -> nothing to say in the room"
        )
    )
    msgs = discord("GET", f"channels/{CHANNEL_ID}/messages?limit=5")
    print("  last posted  ", end="")
    if msgs.status_code == 200 and msgs.json():
        print(repr(msgs.json()[0]["content"]))
    else:
        print("(nothing)")
    print()


COMMANDS = {
    "check": cmd_check,
    "seed": cmd_seed,
    "stage": cmd_stage,
    "changed": cmd_changed,
    "restored": cmd_restored,
    "reconsent": cmd_reconsent,
    "converge": cmd_converge,
    "withdraw": cmd_withdraw,
    "say": cmd_say,
    "watch": cmd_watch,
}


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in COMMANDS:
        p = sub.add_parser(name)
        if name == "withdraw":
            p.add_argument("who", nargs="?", default="bob", choices=list(STUDENTS))
        if name == "watch":
            p.add_argument("--seconds", type=int, default=120, help="how long to watch")
    args = parser.parse_args()
    raise SystemExit(COMMANDS[args.command](args) or 0)


if __name__ == "__main__":
    main()
