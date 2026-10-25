# CampusOS Discord assistant (T9)

A thin Discord bot posts only the frozen `ChannelSummary` templates. The separate
student terminal client makes human-authenticated requests directly to CampusOS.
It is a demo companion while T5's browser UI is queued, not a Discord identity issuer.
Neither client negotiates or calls a model. T2 enforces disclosure and commitments.

## Install and configure

From the repository root, Python 3.11:

```sh
uv venv --python 3.11 groupchat/.venv
uv pip install --python groupchat/.venv/bin/python -r groupchat/requirements-dev.txt
```

Run T2 using `backend/README.md`, with `CAMPUSOS_INFERENCE_MODE=mock`, PostgreSQL,
Redis and its environment configuration. Do not put a JWT signing key in either
client. An operator provisions human accounts and issues tokens as documented there.
Each participating student's Discord OAuth identity must be verified by the operator
using `backend.manage link-discord` before that student can link a channel.
There is no self-service OAuth callback in the backend yet.

Create/install a Discord application in a test server with `bot` and
`applications.commands` scopes and View Channel / Send Messages permissions.
Enable **Server Members Intent** in the developer portal: T2's REST audience verifier
needs guild-member enumeration. The bot itself uses only the Guilds gateway intent;
it does not read message content. Supported rooms are guild text channels, not DMs,
threads or forums. See the [Discord setup guide](https://docs.discord.com/developers/quick-start/getting-started)
and [discord.py interactions reference](https://discordpy.readthedocs.io/en/stable/interactions/api.html).

Set environment variables (names in `.env.example`; files are not loaded automatically):

- Bot process: `CAMPUSOS_API_URL`, `CAMPUSOS_BOT_TOKEN` (kind `bot`, correct guild),
  `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`.
- Each student's own terminal: `CAMPUSOS_API_URL`, `CAMPUSOS_HUMAN_TOKEN` (kind `human`).
- T2 also needs its Discord bot credential for audience verification.

API URLs must use HTTPS/443, except HTTP on loopback for local development. Never
paste credentials into Discord, command arguments, committed files, or shared terminals.

```sh
groupchat/.venv/bin/python -m groupchat.bot
```

Startup syncs `/schedule` and `/watch` to the configured guild. `/schedule` responds
ephemerally with the registered `chn_` reference and instructions. It neither creates
a negotiation nor authorizes publication. All public messages come from validated
summaries; mentions are disabled.

## Three-student demo, no GPU

Run these commands on each student's own device/terminal. Use real returned IDs in
place of the capitalized placeholders. Keep input JSON outside the repository.
The terminal prints response JSON only to that student, never to the Discord room.

1. Run `/schedule` in the test channel. Each student links the returned channel:

   ```sh
   groupchat/.venv/bin/python -m groupchat.student link CHANNEL
   groupchat/.venv/bin/python -m groupchat.student me
   ```

2. Share only the `cnt_` contact handles with the organizer. The organizer prepares
   a private JSON file and runs `student create /private/path/create.json`:

   ```json
   {"invitees":["cnt_REPLACE_WITH_BOB_HANDLE","cnt_REPLACE_WITH_CAROL_HANDLE"],
    "window":{"start":"2026-11-01T10:00:00Z","end":"2026-11-01T15:00:00Z"},
    "min_duration_minutes":60,"max_rounds":5}
   ```

   Choose a future window; those timestamps are examples. Review the printed body
   and type `yes` to send. Each student runs `student list`, then `student state NEGOTIATION`
   to discover their own `viewer.student_ref` and the other participants' agent IDs.

3. Each student grants the other two agents scoped access, using two private JSON
   files and `student grant /private/path/grant.json` for each:

   ```json
   {"negotiation_id":"neg_REPLACE_WITH_RETURNED_ID",
    "grantee_agent_id":"agt_REPLACE_WITH_OTHER_AGENT_ID",
    "max_disclosure_level":"free_busy","expires_at":"2026-11-01T15:00:00Z"}
   ```

   Expiry must not exceed the window end. The client prints the grant and requires `yes`.

4. The organizer requests channel consent with `student bind NEGOTIATION CHANNEL`.
   Every participant runs `student state NEGOTIATION`, then
   `student decide NEGOTIATION APPROVAL` for their `post_to_channel` approval.
   The client re-reads it, prints the exact disclosure preview and version, and requires
   `approve` or `decline`. A stale 409 requires another read and a new human decision;
   the client never silently retries an approval. `student bindings NEGOTIATION`
   shows counts privately. Only after everyone consents, run `/watch NEGOTIATION` in Discord.

5. Each student creates their own availability JSON and runs
   `student availability /private/path/availability.json`. For example:

   ```json
   {"schema_version":"1.0","student_ref":"stu_REPLACE_WITH_OWN_VIEWER_REF",
    "generated_at":"2026-11-01T09:00:00Z","timezone":"UTC",
    "window":{"start":"2026-11-01T10:00:00Z","end":"2026-11-01T15:00:00Z"},
    "disclosure_level":"free_busy",
    "slots":[{"start":"2026-11-01T10:00:00Z","end":"2026-11-01T15:00:00Z","state":"free"}]}
   ```

   Use the negotiated window, a current generated timestamp and each student's own ref.
   For the conflict demo, Alice is free 10–15, Bob 11–15, Carol 12–15; the common
   candidate starts at 12. Never include labels, categories or reasons. Missing intervals
   mean unknown, not free. Review the JSON and type `yes` before sending.

6. Each student reads their own state and decides their `commit_slot` approval.
   The terminal shows the proposed time and disclosure preview. Before all three approvals,
   the room says only “Waiting on everyone to confirm.” The frozen channel contract does
   not expose a proposed timestamp until convergence. After all three confirm, it says
   “Locked in” with the agreed interval. T2 creates local commitment rows, not external
   Google Calendar events. A busy-only Carol yields no overlap and an honest failure.

For commands abbreviated as `student ...` above, use
`groupchat/.venv/bin/python -m groupchat.student ...`.

## Consent, failure and lifecycle

- The bot never reads participant state or holds human credentials. Human linking,
  binding and decisions run in the student's separate process.
- T2 currently refuses bot calls to `GET channel-bindings` (participant-only), despite
  the assignment's polling instruction. The student client reads this endpoint. The bot
  instead asks the summary endpoint for a fresh authorization decision on every update.
- A summary 403, missing resource, outage, invalid JSON, unknown template or extra field
  stops that watcher without posting any negotiation information. Logs contain fixed
  messages only. No cached summary is replayed after an error. `/schedule` registration
  outages give a generic ephemeral error; background failures stay silent in the room.
- Any change to the verified audience -- a join, a departure, or one account replacing
  another -- makes T2 raise new human approvals. Approve privately, then issue
  `/watch` again. `student withdraw NEGOTIATION CHANNEL` revokes channel consent;
  the next summary request is denied. Already sent messages remain visible.
- One watcher per room, ten-second interval, maximum 90 checks. Terminal outcomes stop
  it. Restarting loses watchers; `/watch` explicitly resumes. Discord SDK handles its
  transport rate limits; application mutations are not automatically retried.
- Permission/consent checks and Discord delivery are separate network operations.
  Revocation cannot retract an in-flight post, and no arrangement of a distributed
  authorization check and an external send closes that window. What bounds it: every
  post is preceded by its own check, the check is serialized against withdrawal inside
  T2's transaction, a post that escapes the window is a frozen template the binding had
  already authorized, and a refused publisher is spent -- it neither posts nor polls
  again, whether or not its caller honours the result.

## Verification and live checklist

```sh
groupchat/.venv/bin/python -m pytest tests/groupchat/ -q
groupchat/.venv/bin/ruff check groupchat tests/groupchat
groupchat/.venv/bin/ruff format --check groupchat tests/groupchat
groupchat/.venv/bin/mypy groupchat
```

Tests run the real T2 app with mock inference, SQLite, fakeredis and fake Discord.
The local fixture is adapted from T2's fixture to keep this suite independently runnable.
Tests do not connect to a real server or prove production PostgreSQL behavior.

Live verification still requires operator-provided Discord installation and credentials:
confirm slash commands appear; execute the three-student flow; deny one channel approval;
grow the room and re-consent; withdraw; stop the backend; check that no private details
appear in messages or logs. Record actual results in the handoff. No live Discord test
is claimed by the automated suite.
