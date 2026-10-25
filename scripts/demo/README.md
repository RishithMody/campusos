# CampusOS live demo (Discord)

Drives the whole consent flow against a **real Discord server** and posts the frozen
`ChannelSummary` sentences into a real channel, through the real T9 code path
(`groupchat.api` → `groupchat.publisher` → `groupchat.render`).

First run: **2026-10-25**. Evidence: [`docs/agents/handoffs/T7b-1.md`](../../docs/agents/handoffs/T7b-1.md).

## ⚠️ One substitution, until a toggle is flipped

`server.py` supplies the channel's member list from `CAMPUSOS_DEMO_ROSTER` instead of
enumerating it, because enumeration needs Discord's privileged **Server Members Intent**
and this application does not have it (`GET /applications/@me` returns `flags=0`).

Everything else is live: real member documents, the production `can_view()`, every guard
in `DiscordREST.audience`, and a real consent fingerprint.

**Enable the intent and stop using `server.py`:**

1. <https://discord.com/developers/applications> → CampusOS → Bot
2. Privileged Gateway Intents → **Server Members Intent** → on → Save
3. Then run the plain backend instead, and the demo is genuine end to end:

   ```sh
   backend/.venv/bin/uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8000
   ```

Nothing produced through `server.py` is evidence about `audience()`'s pagination,
deduplication, or incomplete-page handling. Those remain mock-tested only.

## Prerequisites

* `.env` filled in (see `backend/.env.example` and `groupchat/.env.example`).
  `CAMPUSOS_DISCORD_TOKEN` must be the **real** bot token — the backend verifies the
  channel audience with it.
* The bot invited to a test server with View Channel + Send Messages on a guild **text**
  channel (threads, forums and DMs fail closed by design).
* PostgreSQL and Redis on the ports in `.env`, migrations applied, and three provisioned
  students.

## Run it

```sh
set -a && . ./.env && set +a

# PostgreSQL + Redis
docker compose up -d
(cd backend && ../backend/.venv/bin/alembic upgrade head)

# three students; one needs a verified Discord identity to link the channel
for s in alice-demo bob-demo carol-demo; do
  backend/.venv/bin/python -m backend.manage provision "$s"
done
CAMPUSOS_DISCORD_OAUTH_ACCESS_TOKEN=... \
  backend/.venv/bin/python -m backend.manage link-discord alice-demo

# the backend
export CAMPUSOS_DEMO_ROSTER="<bot-user-id>,<each-human-user-id>"
PYTHONPATH=. backend/.venv/bin/uvicorn scripts.demo.server:build --factory \
    --host 127.0.0.1 --port 8000 &

# the whole consent flow, posting to the real channel
PYTHONPATH=. groupchat/.venv/bin/python scripts/demo/flow.py

# the bot, so /schedule and /watch appear in Discord
export CAMPUSOS_BOT_TOKEN=$(backend/.venv/bin/python -m backend.manage \
    issue-bot campusos-bot --guild "$DISCORD_GUILD_ID" --ttl 12 | head -1)
groupchat/.venv/bin/python -m groupchat.bot &
```

`flow.py` prints the negotiation id. Paste it into `/watch <negotiation>` in the channel
and the bot publishes updates for up to 15 minutes.

## What the flow shows, in order

1. Contact handles only — no names cross the boundary
2. A negotiation created by invitation, which grants nothing on its own
3. Six explicit, expiring, per-agent free/busy grants
4. Free/busy availability — no titles, no reasons
5. Agents converging on a slot without any student seeing another's calendar
6. The real Discord channel registered, its audience verified against Discord
7. A channel binding, needing every participant's separate approval
8. **403 before consent** — and the real publisher posting nothing
9. Each student shown exactly what would be disclosed, and to how many accounts
10. **200 after consent**, and one frozen sentence posted to the real channel

`flow.py` stops there. The audience-change, convergence and withdrawal steps are in the
handoff; change `CAMPUSOS_DEMO_ROSTER`, restart the server, and the binding moves to
`pending_reconsent` with posting stopped until everyone agrees again.

## Clean up

```sh
pkill -f groupchat.bot; pkill -f "scripts.demo.server"; docker compose down
```

Demo accounts and the demo database are disposable. The bot JWT is not stored.
