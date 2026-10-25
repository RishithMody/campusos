# Live demo runbook

Rehearsed end to end on 2026-10-25 against the real `CampusOS Test` server. Every beat
below was run and its Discord output verified.

**One terminal, one Discord window.** Keep the terminal in the repo root with the
environment loaded:

```sh
cd ~/campusos && set -a && . ./.env && set +a
A="backend/.venv/bin/python scripts/demo/act.py"
```

---

## Cold start (do this 15 minutes before, not on stage)

```sh
# 1. PostgreSQL and Redis on the ports .env asks for, plus migrations.
#    Uses Docker when the daemon is up and local binaries when it is not, so this
#    works on a laptop that has just booted. Data lives in ~/.campusos-demo --
#    deliberately not a temp directory, so a rehearsal's database survives to the talk.
./scripts/demo/services.sh up

# 2. A FRESH bot credential, BEFORE starting the bot. The one in .env expires, and an
#    expired credential is refused with the same uniform 403 as "nobody consented" --
#    correct, and indistinguishable on stage.
export CAMPUSOS_BOT_TOKEN=$(backend/.venv/bin/python -m backend.manage \
    issue-bot campusos-bot --guild "$DISCORD_GUILD_ID" --ttl 24 | head -1)

# 3. The backend
nohup backend/.venv/bin/python -m uvicorn scripts.demo.server:build \
    --factory --host 127.0.0.1 --port 8000 > /tmp/campusos-api.log 2>&1 &

# 4. The Discord bot. Startup re-syncs /schedule and /watch to the guild.
nohup groupchat/.venv/bin/python -m groupchat.bot > /tmp/campusos-bot.log 2>&1 &

# 5. The three demo students, once per database
$A seed
```

**Do not restart the backend after this.** The bot does not retry: a slash command that
lands while the API is unreachable gets the generic "CampusOS is unavailable" ephemeral
reply. That is correct behaviour -- nothing is said in the room and nothing is confirmed
-- but from the stage it reads as a failure. One rehearsal restart cost a 58-second
window and a `/schedule` landed inside it.

## Two minutes before you speak

```sh
$A check     # every service, the Discord credential, the intent, the slash commands
$A stage     # a fresh consented negotiation. Posts NOTHING -- the channel stays clean
```

`check` must end in **`Ready.`** and print the `/watch` line. `stage` prints it too.
Copy that negotiation id — you will paste it once.

---

## The demo — six beats, about six minutes

### 1 · The problem (no terminal)

> "Four friends need two hours this week. Every tool that solves this asks for your
> calendar. We ask for the answer instead."

### 2 · What the agents did without seeing each other's calendars

```sh
$A say
```

Points to make: three students, each shared **free/busy only** — no titles, no reasons.
Six explicit expiring grants; being invited granted nothing. The agents converged on a
time. `consented to 2 accounts` is the room this is allowed to reach.

### 3 · The bot posts — but only because three humans said yes

In Discord: **`/watch <negotiation id>`**

Within a second the channel shows:

```
Waiting on everyone to confirm.
```

> "That sentence is one of nine the server can choose from. There is no free text in
> this path and no model in it. Neither side can emit a sentence nobody wrote in
> advance."

Mention the reply you just got was **ephemeral**, and that it is identical whether
consent is missing, pending, declined or confirmed — a bot that could tell those apart
could report a private 'no' into the room it was about.

### 4 · Someone's access to the channel changes

```sh
$A changed
$A say
```

The bot goes quiet. `say` shows `binding=pending_reconsent` and `the bot asks HTTP 403`.

> "Nobody told CampusOS. It re-derives who can read this room before every single post,
> and this is not the audience the three of them agreed to — so it stops.
>
> An independent review found this exact bug in our code this morning: we were comparing
> the audience **size**. Swap one member for another and the count never moves. Consent
> is now recorded against a one-way fingerprint of *which* accounts can read the room."

This is the strongest 30 seconds in the demo. It is a real bug, found today, fixed today,
and you can show it refusing.

### 5 · They agree again, and the time is confirmed

```sh
$A reconsent
```

In Discord: **`/watch <same negotiation id>`** → it posts again.

Then, while the watcher is running:

```sh
$A converge
```

Within ten seconds the channel shows:

```
Locked in: 2026-10-27 12:00 UTC – 2026-10-27 13:00 UTC.
```

> "A time, for everyone. Nobody learned why anyone else was busy."

### 6 · Close

> "Privacy here is not a policy page. It is a schema that cannot carry a reason, a server
> filter on the way out, nine fixed sentences, and a consent check that runs before every
> post and fails closed when it cannot verify the room."

---

## Optional extra beat: revocation

Show it **before** step 5, while the negotiation is still open:

```sh
$A withdraw bob
```

> "Any participant, any time, including after messages were posted. One withdrawal ends
> it for everyone, because an audience cannot be partly un-told. What was posted stays
> posted; nothing further is published."

Then `$A stage` again to continue — a withdrawn binding is final.

---

## If something breaks on stage

| Symptom | Do this |
|---|---|
| `/watch` does nothing | Run `$A watch` in the terminal. It is the same `Publisher` loop `/watch` runs, and it posts to the same channel |
| Slash commands missing in Discord | The bot process died. Restart it (cold start step 5). Commands re-sync on startup |
| Everything returns 403 | The bot credential expired. Re-mint it (cold start step 4) and restart the bot |
| `503` / "Channel verification unavailable" | Discord throttled us -- `guilds/{id}/members/{user}` allows five a second. Wait two seconds and repeat. It is not a consent problem, and since 2026-10-25 it no longer pretends to be one |
| The bot vanished mid-demo | It exits on a dropped gateway and prints one line. `$A check` catches it; restart with cold-start steps 4 and 5. Space the demo commands a second apart |
| `check` says the backend is down | Restart it (cold start step 3); `tail /tmp/campusos-api.log`. Then re-run `$A stage` -- a negotiation staged against a previous database is gone |
| "CampusOS is unavailable" in Discord | The bot could not reach the API at all: it is down or restarting. `$A check` confirms which. Nothing was posted and nothing was confirmed |
| `$A check` says students are not provisioned | A fresh database. `$A seed`, then `$A stage` |
| The bot posts nothing and `say` shows 403 | Someone is out of consent. `$A restored` then `$A reconsent` |
| Confused state, under a minute left | `$A stage` — it builds a clean consented negotiation from scratch |

Keep a screenshot of a successful run as a fallback. `docs/agents/handoffs/T7b-1.md`
has a verified transcript you can show if Discord itself is having a bad day.

---

## Say this if you are asked what is not real

Be straight about it; it is a better answer than hedging.

* **The audience member *list* is supplied, not enumerated.** Discord's privileged Server
  Members Intent is off for this application, so `GET /guilds/{id}/members` is refused and
  production `audience()` cannot run — it fails closed, correctly. Every member document
  is still fetched from Discord and the real permission computation still decides who can
  view the channel. Flip that one toggle and `scripts/demo/server.py` is deleted.
* **Inference is mocked.** `CAMPUSOS_INFERENCE_MODE=mock`. The negotiation logic is real;
  no GPU is in this path and the demo needs none.
* **The three students are local accounts** on one machine, not three people on three
  devices.
* **The Discord identity link was asserted by the operator**, not proved by an OAuth
  ceremony, because we have no OAuth callback yet.

## Afterwards

```sh
pkill -f groupchat.bot; pkill -f "scripts.demo.server"; docker compose down
```

To clear the channel, delete the bot's messages in Discord. The demo database and the
demo accounts are disposable; the bot credential was never stored.
