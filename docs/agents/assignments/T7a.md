# Assignment — T7a

| | |
|---|---|
| **Task** | `T7a` — Live verification: real Discord, PostgreSQL, Redis |
| **Agent** | QA / Security Reviewer |
| **CLI** | `codex` |
| **Reviewer** | Claude Code, then the owner |
| **Depends on** | T2 ✅, T9 ✅ |
| **Status** | `READY` — **blocked in practice** on a Discord token and the owner's go-ahead |
| **Branch** | `task/T7a-live-verify` |
| **Worktree** | `~/campusos-worktrees/T7a-live-verify` |
| **Repair attempts** | 0 / 3 |
| **GPU approval** | `NONE` — and none is needed. No vLLM, no cluster, no model |

## Objective

Everything in this project has been verified against a mock. Find out what breaks when it
is not.

T2 and T9 both passed review and both were honest that the riskiest surfaces were simulated.
This task makes them real. It is deliberately **not** waiting for T3 or T5: the vLLM endpoint
and the browser UI have nothing to do with whether the bot can actually connect to Discord.

## What is genuinely unverified

| Claim | Verified as | Still unknown |
|---|---|---|
| Discord permissions, intents, registration | unit tests against **mocked** responses | **no real account, server or channel has ever been contacted** |
| Redis TTLs, pub/sub, fail-closed on outage | **fakeredis** | real semantics, eviction, reconnect |
| PostgreSQL migration + concurrency | **real cluster**, 12 locked threads ✅ | server restart, connection loss mid-transaction |
| Channel summary safety | 792 hostile payloads refused ✅ | **nothing — do not re-do this** |

The last row matters as much as the others: `docs/agents/reviews/T9/attempt-1.md` already
proves the renderer cannot emit anything but eight fixed sentences. Spend your time on what is
actually unknown.

## File ownership

**You own:** `tests/live/`, `docker-compose.yml`
**Read-only:** `backend/`, `groupchat/`, `contracts/`, everything else.

If a live run exposes a real bug in `backend/` or `groupchat/`, **do not fix it here.** Write
it in your handoff with the reproduction, set `REVIEW`, and stop. That is a change to another
agent's files and it goes through the Orchestrator.

## Acceptance criteria

See `docs/task-graph.md` → T7a for the full list. The ones that carry the most risk:

- [ ] The bot connects to a **real Discord server** and `/schedule` and `/watch` work in a
      real text channel
- [ ] Guild Members intent confirmed enabled; permission calculation checked against what
      Discord actually reports, not against the mock
- [ ] A full consent cycle live: bind → all approve → summary posted → one withdraws →
      **posting stops**
- [ ] Declined and pending remain **indistinguishable** to the bot in the live system
- [ ] Rate limiting observed and survived — no crash, no double-post
- [ ] Backend suite green against **real Redis**; record any test that needed changing
- [ ] PostgreSQL and Redis each killed mid-negotiation: degrade without leaking or corrupting
- [ ] **The real channel transcript pasted into the handoff**, every line one of the eight
      frozen sentences

## Required tests

`tests/live/`, marked to **skip by default**, exactly as `tests/backend/test_postgres.py`
already does — a visible skip with a reason, never a silent pass. A live test that no-ops
when the service is absent is worse than no test, because it reports success.

## Context the agent cannot infer

- The live checklist already exists: `groupchat/README.md`. Start there.
- **T9's integration deviation is not a bug.** The bot does not poll `channel-bindings`:
  T2's GET requires participant authorization and refuses bot credentials, so the bot relies
  on the `channel-summary` 403 gate. Confirm the live system behaves the same way.
- **Same-size audience substitution is a known, documented gap** in the frozen contract — a
  room that swaps one member for another keeps its count and does not re-trigger consent. Do
  not fix it here; it needs a contract change and the Orchestrator.
- **A signed human-kind token claim is not proof of a human ceremony** unless the issuer
  enforces it. The entire consent model rests on that. Probe the boundary and report.
- Setup commands: `backend/README.md` and `groupchat/README.md`. Both venvs are gitignored.

## Blocked on, before anything touches Discord

| | Needed | Why |
|---|---|---|
| **Discord bot token and a test server** | from the owner | Nothing live runs without one. **Never commit it** — environment only |
| **Owner's explicit go-ahead** | yes | Connecting to Discord is outward-facing. Ask first |

Everything involving PostgreSQL and Redis is local and needs neither. **Start there** while
the Discord side waits.

## Out of scope

- Fixing bugs in `backend/` or `groupchat/` — report them instead
- vLLM, the GPU cluster, any model (that is T3)
- The browser UI (T5)
- Publishing or submitting anything

## Definition of done

1. Acceptance criteria met, or honestly marked unmet with the reason
2. Real output pasted — including the Discord transcript
3. Committed on `task/T7a-live-verify`
4. `./scripts/agents.sh handoff T7a` completed and filled in
5. Status `REVIEW`. **Do not merge.**
