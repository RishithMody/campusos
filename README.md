# CampusOS

**Four friends try to find two hours this week. CampusOS finds the time without anyone
publishing their calendar.**

Every student has a personal agent. The agents negotiate the time between themselves, and
each one is bound to what its student actually agreed to disclose. An agent says
*"busy 2–4pm"*. It cannot say *"therapy at 2pm"* — not because it is polite, but because the
protocol has nowhere to put that, the server strips it on the way out, and the schema refuses
it on the way in.

Built for the **Cubbie Hackathon**.

---

## The problem

Group scheduling fails for a social reason, not a technical one. "When is everyone free?"
asks people to hand over a calendar to answer a question about two hours. So someone says
"I'm free whenever", someone screenshots their week, two people never reply, and a week later
the group still has not met.

Every tool that solves this asks for the calendar. CampusOS asks for the answer:

| | What travels | What cannot travel |
|---|---|---|
| **Between agents** | free/busy intervals inside one agreed window | event titles, locations, categories, reasons, notes, raw chat |
| **Into a group chat** | one of nine fixed sentences | anything a human wrote, anyone's name, any interval |
| **To the model** | filtered envelopes and a closed intent | the student's text, their calendar, anyone else's anything |

Disclosure is a **ladder** — `none` → `free_busy` → `category` → `full` — and every account
starts at `free_busy`. A grant can lower what a specific agent may see, never raise it past
its owner's ceiling. There is no "share everything" setting to misclick.

## What is implemented

| | What runs | Verified against |
|---|---|---|
| **Scheduling backend** | FastAPI, the whole frozen `/v1` surface, JWT-only (including `/health`) | real PostgreSQL 15 + Redis 8, 291 tests |
| **Negotiation engine** | LangGraph, bounded rounds, proposals at interval boundaries, `failed` is a normal outcome with human escalation | mock inference |
| **Disclosure filter** | server-side egress filtering, live grant checks on every cross-student read, audit rows | privacy- and authz-marked tests |
| **Human approval** | every disclosure and every commitment needs its owner's explicit yes, with a preview and a state version | 409 on a stale decision |
| **Discord assistant** | two guild-only slash commands, nine frozen sentences, mentions disabled | **a real Discord server, 2026-10-25** — consent path end to end |
| **Channel consent** | per-participant approval, audience identity re-checked on every read, one withdrawal ends it for everyone | **live** — audience change stopped posting until everyone re-agreed |
| **Cubbie Skill** (`squad-sync`) | standard-library Python, a week of availability in one pasteable line | the organizers' own validator |
| **Contracts** | 3 JSON Schemas + OpenAPI 3.1, 30 fixtures including deliberately invalid ones | bundled offline, every fixture asserted |

Two things are **specified and not running**: the Next.js negotiation view (T5) and vLLM on
the H200s (T3). Neither is on the path to a demo; the backend runs on CPU with
`CAMPUSOS_INFERENCE_MODE=mock`.

## Privacy-first architecture

```
   Student A ──┐                              ┌── Student A's agent ──┐
   Student B ──┼── human approval required ───┼── Student B's agent ──┼── LangGraph
   Student C ──┘   for every disclosure       └── Student C's agent ──┘   (filtered only)
                            │
                   ┌────────┴────────┐
                   │  CampusOS /v1   │  egress filter · live grants · audit log
                   └────────┬────────┘
                            │  nine frozen sentences, no free text
                     ┌──────┴──────┐
                     │ Discord bot │  consent-gated per channel audience
                     └─────────────┘
```

Four properties worth naming, because each one is enforced somewhere a reader can check:

1. **No free text reaches a group chat.** The server picks a `template_id` from a closed list;
   the bot renders it from typed integers and a timestamp. Neither side can emit a sentence
   nobody wrote in advance, and no model is in that path. `groupchat/render.py`.
2. **Consent is to an audience, not a headcount.** The backend records a one-way,
   channel-scoped digest of exactly which Discord accounts can read the room, and re-derives
   it on every summary read. A join, a departure, or one member swapped for another all stop
   posting until every participant agrees again. `backend/channels/discord.py`.
3. **Approval is human, and provable.** An agent token cannot answer an approval; the token
   `kind` is checked, and a bot credential cannot read a negotiation at all. Every decision
   is pinned to the state version it was shown.
4. **Revocation is honoured mid-flight.** One withdrawal ends posting for everyone, because
   an audience cannot be partially un-told. The irreducible limit is stated rather than
   papered over: see *Known limitations*.

Design record: [`docs/architecture.md`](docs/architecture.md),
[`docs/adr/0001-three-track-unified-architecture.md`](docs/adr/0001-three-track-unified-architecture.md).

## Cubbie Skill — `squad-sync`

The Track 1 entry, and the one deliverable that needs no backend at all. Each person's week
becomes one line:

```
SQSY1 TZ:America/Phoenix W:2026-10-26 L:busy B:1-0900-1015,1-1400-1600,3-1800-1900 X:313e
```

Day numbers and times. No event names, no places, no people, no reasons. Paste the replies
back and it finds the overlap. Standard library only — nothing to install.

* Public repo: <https://github.com/RishithMody/campusos-squad-sync> (public since 2026-10-24)
* Install: `https://github.com/RishithMody/campusos-squad-sync/tree/main/squad-sync`
* Source in this repo: `skills/squad-sync/` on branch `task/T0b-cubbie-skill` — **built and
  validated, pending the owner's acceptance; not yet merged to `main`**

## Stack

FastAPI · Python 3.11 · LangGraph — PostgreSQL 15 · Redis 8 — discord.py — JSON Schema /
OpenAPI 3.1 — Docker Compose. Specified but not running: Next.js · TypeScript · Tailwind (T5),
vLLM · Qwen3 8B · LoRA/QLoRA on 2× NVIDIA H200 (T3, T6).

## Install and run locally

Python 3.11, [`uv`](https://docs.astral.sh/uv/), and Docker. No GPU, no Discord account and no
API key are needed for everything except the live Discord step.

```sh
git clone https://github.com/RishithMody/campusos && cd campusos

# 1. PostgreSQL and Redis on loopback-only ports
docker compose up -d

# 2. Backend
uv venv --python 3.11 backend/.venv
uv pip install --python backend/.venv/bin/python -r backend/requirements-dev.txt

# 3. Discord assistant and the student terminal client
uv venv --python 3.11 groupchat/.venv
uv pip install --python groupchat/.venv/bin/python -r groupchat/requirements-dev.txt
```

### Environment

Copy the two `.env.example` files and fill them in your shell. **Nothing is loaded from a
file automatically, and no `.env` is ever committed** — `.gitignore` excludes it and a
pre-commit hook blocks it.

Backend (`backend/.env.example`):

| Variable | Required | Notes |
|---|---|---|
| `CAMPUSOS_INFERENCE_MODE` | yes | `mock` or `vllm`, explicitly — an unset value fails startup |
| `CAMPUSOS_DATABASE_URL` | yes | e.g. `postgresql+psycopg://campusos@127.0.0.1:55439/postgres` |
| `CAMPUSOS_REDIS_URL` | yes | e.g. `redis://127.0.0.1:56389/0` |
| `CAMPUSOS_JWT_KEY` | yes | HS256 signing key, **≥ 32 characters**, generated per environment |
| `CAMPUSOS_DISCORD_TOKEN` | for Discord | bot token, Guild Members intent — used only to verify a channel's audience |
| `CAMPUSOS_VLLM_URL` / `_KEY` / `_MODEL` | `vllm` mode | private `/v1` endpoint, never a public URL |

Bot and student client (`groupchat/.env.example`):

| Variable | Whose process | Notes |
|---|---|---|
| `CAMPUSOS_API_URL` | both | HTTPS/443, or `http://127.0.0.1:8000/v1` on loopback |
| `CAMPUSOS_BOT_TOKEN` | bot only | CampusOS `kind=bot` JWT, bound to one guild. Not the signing key |
| `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID` | bot only | from the Discord developer portal |
| `CAMPUSOS_HUMAN_TOKEN` | each student's own device | `kind=human` JWT. Never set this in the bot process |

`LANGSMITH_TRACING` / `LANGCHAIN_TRACING_V2` set to `true` **fail startup on purpose**:
external tracing would export student state to a third party.

### Start the backend

```sh
backend/.venv/bin/alembic -c backend/alembic.ini upgrade head
backend/.venv/bin/uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8000

# accounts and credentials (local, trusted, never an HTTP route)
backend/.venv/bin/python -m backend.manage provision <issuer-subject>
backend/.venv/bin/python -m backend.manage issue-bot <bot-subject> --guild <guild-id> --ttl 12
```

### Start the Discord assistant

Requires a bot application in a test server with `bot` + `applications.commands`, View
Channel / Send Messages, and **Server Members Intent** enabled. Guild text channels only —
threads, forums and DMs fail closed.

```sh
groupchat/.venv/bin/python -m groupchat.bot
```

### Slash commands

| Command | Who sees the reply | What it does |
|---|---|---|
| `/schedule` | only the caller (ephemeral) | registers the channel, returns its `chn_` reference and instructions. Creates no negotiation and authorizes no posting |
| `/watch <negotiation>` | only the caller (ephemeral) | starts one watcher for this room, up to 15 minutes. **The acknowledgement is identical whether consent is missing, pending, declined or confirmed** — a bot that could tell them apart could report a private no into the room it was about |

Nothing else is a command, and the bot reads no message content. Students act through their
own terminal: `me`, `list`, `state`, `link`, `bind`, `bindings`, `withdraw`, `decide`,
`create`, `availability`, `grant` — see
[`groupchat/README.md`](groupchat/README.md) for the three-student walkthrough.

## Testing

```sh
groupchat/.venv/bin/python -m pytest tests/ -q          # everything: 291 passed, 9 skipped
backend/.venv/bin/python -m pytest tests/backend/ -q    # backend only
backend/.venv/bin/ruff check . && backend/.venv/bin/ruff format --check .
backend/.venv/bin/mypy backend groupchat
scripts/ci/validate_contracts.py --strict               # frozen schemas + every fixture
scripts/ci/secret_scan.sh --tracked                     # no credential in any tracked file
```

The 9 skips are honest: they need a disposable PostgreSQL cluster
(`CAMPUSOS_TEST_POSTGRES_URL`) or a live Discord token. **A test that silently no-ops is
worse than no test**, so they skip loudly rather than passing.

Two extra harnesses:

```sh
# mutation testing -- each guard must have a test that fails when the guard is removed
PYTHONPATH=. groupchat/.venv/bin/python tests/integration/connector/mutations.py \
    --python "$PWD/groupchat/.venv/bin/python"

# the orchestration tooling itself
./scripts/ci/test_agents_sh.sh
```

Five GitHub Actions workflows run on every push. None needs a GPU, a Discord token, or any
credential.

## Implementation and verification status

**Verified against real infrastructure:** PostgreSQL 15 and Redis 8, including migrations,
row-level locking, optimistic versioning, SSE under grant revocation, and degradation when
either service is killed mid-negotiation.

**Verified live against a real Discord server, 2026-10-25.** The full consent path ran
end to end and posted into a real channel: registration, identity linking, per-participant
approval, `403` before consent and `200` after, the audience changing and posting stopping
until everyone re-agreed, convergence, and one withdrawal ending it for everyone. Both
sentences were read back from Discord and carried no mentions; the audit log held no Discord
account id. Evidence: [`docs/agents/handoffs/T7b-1.md`](docs/agents/handoffs/T7b-1.md).

> ⚠️ **Still unverified: guild member enumeration.** The Discord application has no
> privileged Server Members Intent, so `GET /guilds/{id}/members` is refused and production
> `audience()` cannot run against it — it fails closed, correctly, and the demo supplied the
> member list instead. `audience()`'s pagination and incomplete-page handling remain
> mock-tested only. `can_view()` now agrees with Discord for both real members of the test
> guild, but that guild has two members, no channel overwrites and no administrator, so the
> branches that worried us are still pinned by fixtures their own author wrote. One toggle in
> the developer portal clears this.

**Not started:** the browser UI (T5), vLLM on the H200s (T3), optional LoRA fine-tuning (T6).

Two merges went in under **owner-authorized review waivers rather than passes** — T7c and
T7d, the latter with no review at all. Both waivers are in `docs/agents/reviews/`. The
independent review that produced the current round of fixes is recorded in
[`docs/agents/reviews/T12/findings.md`](docs/agents/reviews/T12/findings.md).

## Known limitations

* **Discord audience enumeration is unverified live**, pending one developer-portal
  toggle. The consent path itself ran against a real server on 2026-10-25.
* **Linking a CampusOS account to a Discord identity was asserted, not proved**, in that
  demo: `manage link-discord` needs the student's OAuth access token, which we did not have,
  so the operator wrote the id directly. No check was weakened, but the ceremony did not
  happen.
* **The publish window cannot be closed.** Authorization lives in the backend; the post lives
  in Discord. Between a 200 and Discord accepting the message, consent can be withdrawn, and a
  distributed check plus an external send cannot be made atomic. What bounds it: every post is
  preceded by its own check, the check is serialized against withdrawal inside the backend's
  transaction, and anything that escapes is a frozen sentence the binding had already
  authorized. Documented in `groupchat/publisher.py`.
* **No self-service Discord OAuth.** An operator links each student's verified Discord
  identity with `backend.manage link-discord`; a Discord ID claimed by a bot is never trusted.
* **The identity issuer is outside the contract.** CampusOS verifies a `kind=human` claim; it
  cannot prove a human ceremony happened upstream. The consent model rests on that boundary.
* **No calendar is written and no message is sent** by the backend. A converged negotiation
  creates local commitment rows. Google Calendar integration does not exist.

## Hackathon tracks

| Track | Entry | Status |
|---|---|---|
| **1 · Cubbie Skills** | `squad-sync` — group scheduling with minimum disclosure | built, validated, public repo live. **Not submitted** |
| **2 · Agent-to-Agent** | this backend: agents negotiating under per-student disclosure ceilings, with human confirmation | prototype runs; submission package not assembled |
| **3 · Group Chat Assistant** | the Discord assistant, consent-gated and template-only | **ran live in a real server 2026-10-25**; audience enumeration still pending one intent toggle |

Track 1 gates the other two — the organizers' database refuses a Track 2 or 3 entry from a
team with no Track 1 entry. All three windows were open with **no close time set** when last
checked live (2026-10-24T18:50:26Z); re-check before any time-based decision. Every rule
behind this table carries a source and a date in
[`docs/hackathon-requirements.md`](docs/hackathon-requirements.md).

**One decision blocks all three submissions:** the team roster (1–4 members, name + school
email) and which member owns the entry. Only the owner can edit an entry afterwards.

## Demo

<!-- 30-second product video: add the public TikTok/Instagram link here once posted. -->
<!-- Screenshots: docs/demo/ -- the three-student flow and one consent-gated channel post. -->

> 📹 **Demo video and screenshots: not yet recorded.** Placeholders above; nothing here
> claims a recording exists. The live flow is reproducible for filming:
> [`scripts/demo/README.md`](scripts/demo/README.md).

## How this repository was built

Six specialised agents, each a plain `claude` or `codex` session in its own Git worktree on
its own branch, sharing **no** memory — the repository is the only channel between them — and
**no agent can merge**. Reviews always run on the opposite CLI from the one that wrote the
code, bounded at three repair attempts before the loop escalates to a human. Git hooks
enforce the rules rather than trusting a prompt to remember them.

| File | What it is |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | **Shared rules for every agent.** Single source of truth |
| [`AGENTS.md`](AGENTS.md) | Codex entry point — a pointer to `CLAUDE.md`, not a copy |
| [`docs/task-graph.md`](docs/task-graph.md) | **Authoritative task state** — the DAG, ownership, acceptance criteria |
| [`docs/orchestration.md`](docs/orchestration.md) | Operator runbook: every command, monitoring, merging |
| [`docs/agents/status.md`](docs/agents/status.md) | Live status board and the open questions for the human |
| [`docs/infra-policy.md`](docs/infra-policy.md) | H200 policy: approval tokens, scheduling, no public endpoints |
| [`backend/README.md`](backend/README.md) · [`groupchat/README.md`](groupchat/README.md) | Component setup and the three-student walkthrough |

## License

Not yet chosen. `squad-sync` ships Apache-2.0 in its public repo.
