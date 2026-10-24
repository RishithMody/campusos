# ADR 0001 — One platform, three track submissions

- **Status:** Accepted (pending human confirmation of D3 and D4)
- **Date:** 2026-10-24
- **Author:** Orchestrator
- **Supersedes:** the single-track assumption in the original `docs/execution-plan.md`

## Context

T0 verified the official rules (`docs/hackathon-requirements.md`). Three findings make the
obvious reading of "support all three tracks" impossible to build as stated:

1. **Cubbie has no group chat and cannot text anyone but its own student** (requirements §6).
2. **Cubbie's sandbox does not support MCP**, remote or local, and cannot reach a server started
   inside it. Outbound **HTTPS on port 443 to a public host** is the only network path.
3. **Cubbie already ships `study-plan-builder`**, which is the solo study-planning product the
   expanded brief described for Track 1.

The goal is three valid submissions from one cohesive product, not three applications.

## Decision

### D-1. The backend is the product. Cubbie is one client of it.
A single FastAPI + LangGraph service owns negotiation, disclosure control, approval and
persistence. Track 1's Skill, Track 2's personal agents and Track 3's group-chat bot are three
*surfaces* over that one service. Nothing is reimplemented per track.

### D-2. The Skill↔platform boundary is plain HTTPS. No MCP.
A Cubbie Skill script may call our API over HTTPS/443 to a publicly reachable host. MCP is ruled
out by the platform, not by preference. Cubbie fetches Canvas/Calendar data itself and passes it
to the script as arguments or a file — **scripts cannot call Cubbie's abilities**.

### D-3. Track 1 phase 1 ships with no backend dependency at all.
The first Track 1 entry is instructions-only: `SKILL.md` using Cubbie's connected abilities, with
the student sharing the result themselves. Reasons: the entry is the mandatory deliverable and the
gate for Tracks 2 and 3; it is scored on votes accumulated over time; and Cubbie installs the
newest commit, so the hosted version is a later push needing no resubmission. **A valid entry must
never be blocked on our infrastructure being up.**

### D-4. Track 2's agent-to-agent traffic never routes through Cubbie.
Personal agents exchange envelopes through our own service. Cubbie is where a student *talks to
their own agent* and *gives consent*, nothing more. This is what the platform permits and what the
Track 2 rules already assume ("doesn't need to be built on Cubbie").

### D-5. Track 3 is a Discord bot.
Discord has a free bot API, the organizers already run a Discord, and it screen-records well.
The rules allow any messaging app. **Pending D4 confirmation from the human.**

### D-6. One disclosure-controlled availability envelope, shared by all three tracks.
`contracts/availability.schema.json` is the single representation of "when a student is free and
what may be said about why". It is the Skill's output, the Track 2 agent message payload, and the
Track 3 group-chat payload. This schema is what makes the three submissions one product.

### D-7. The privacy guarantee is enforced server-side, in one place.
Disclosure levels are applied by the backend before a payload leaves it. Clients — Skill, bot,
frontend — never decide what may be revealed. A client bug must not become a privacy breach.

## Module ownership

The nine modules in the expanded brief, each owned by exactly one task:

| # | Module | Lives in | Task |
|---|---|---|---|
| 1 | Cubbie integration adapter | `skills/<name>/` | T0b |
| 2 | Skill execution layer | `backend/skill/` | T2 |
| 3 | Personal agent runtime | `backend/agents/` | T2 |
| 4 | Agent-to-agent protocol | `contracts/` + `backend/protocol/` | T1 → T2 |
| 5 | Group chat coordination | `groupchat/` | T9 |
| 6 | Privacy and approval service | `backend/privacy/` | T2 |
| 7 | Shared persistence (Postgres + Redis) | `backend/db/` | T2 |
| 8 | Model inference abstraction | `contracts/inference.md` + `backend/inference/` | T1 → T2, T3 |
| 9 | Evaluation and observability | `ml/` | T4 |

Ownership is disjoint by construction; T1 verifies it before moving T2–T5 and T9 to `READY`.

## H200 strategy, and a conflict it creates

The two H200s serve **Tracks 2 and 3 only**:

- **Inference** for personal-agent reasoning and negotiation, behind `contracts/inference.md` so
  the mock and vLLM are drop-in replacements.
- **Evaluation** sweeps for T4.
- **Optional LoRA** (T6), which must never delay a submission.

**Conflict to resolve before any Track 1 Skill calls our inference.** `docs/infra-policy.md`
requires the inference endpoint to be bound to localhost/private and reachable only via SSH
tunnel, never publicly exposed. Cubbie's sandbox cannot reach an SSH-tunnelled endpoint — it needs
a public HTTPS host (§6). These cannot both hold.

**Resolution: do not let Track 1 depend on our inference.** D-3 already removes that dependency.
If a later Skill version must call the platform, it calls an authenticated public **API gateway**
that runs on CPU and holds the disclosure logic; that gateway — never the vLLM endpoint — is what
faces the internet, and it reaches inference privately. Exposing the vLLM endpoint directly stays
forbidden and would need its own ADR plus human approval.

No GPU workload starts without a human-signed approval token, unchanged by this ADR.

## Consequences

**Good.** One backend, one privacy model, one schema family. Track 1 ships independently and
early. Each track's deliverable is separable, so a track can be dropped without breaking others.

**Costs.** A Discord bot is a messaging dependency the original plan did not have (T9). The public
API gateway is extra deployment surface, needed only if Track 1 goes beyond instructions-only.
Three submissions mean three sets of submission mechanics (T0b, T10, T11).

**Risks.** Tracks 2 and 3 judging criteria are still unannounced, so their scope may need to move.
No deadline is published, so "early and editable" is the only defensible scheduling strategy.
