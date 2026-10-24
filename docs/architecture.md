# CampusOS architecture

**Produced by T1.** Companion to `docs/adr/0001-three-track-unified-architecture.md` (the
decisions) and `contracts/` (the frozen interfaces). This document explains the shape; the
contracts are authoritative on detail.

CampusOS is one backend with three faces. Students' personal agents negotiate schedules on their
behalf while revealing as little as possible about *why* anyone is busy.

---

## 1. Components

```
 ┌─ Track 1 ──────────┐   ┌─ Track 2 ───────────┐   ┌─ Track 3 ──────────┐
 │  Cubbie (iMessage) │   │  Next.js frontend   │   │  Discord bot       │
 │  Skill: squad-sync │   │  negotiation view   │   │  group coordination│
 └─────────┬──────────┘   └──────────┬──────────┘   └─────────┬──────────┘
           │ HTTPS/443               │ HTTPS + SSE             │ HTTPS
           │ (student-initiated)     │                         │
 ══════════╪═════════════════════════╪═════════════════════════╪═══════════
   TRUST BOUNDARY — everything above is a client and is never trusted
 ══════════╪═════════════════════════╪═════════════════════════╪═══════════
           └─────────────┬───────────┴─────────────┬───────────┘
                         ▼                         ▼
              ┌──────────────────────────────────────────┐
              │  FastAPI  —  authN, authZ, rate limits   │
              ├──────────────────────────────────────────┤
              │  Privacy & approval service              │ ◀── the ONE place
              │  disclosure filter · grants · audit      │     disclosure is applied
              ├──────────────────────────────────────────┤
              │  Personal agent runtime (LangGraph)      │
              │  bounded negotiation loop                │
              ├───────────────┬──────────────────────────┤
              │ Persistence   │  Inference abstraction   │
              │ Postgres·Redis│  mock │ vLLM             │
              └───────┬───────┴───────────┬──────────────┘
                      │                   │ private network only
                      ▼                   ▼
              ┌──────────────┐   ┌────────────────────┐
              │ Postgres     │   │ vLLM · Qwen3 8B    │
              │ Redis (TTL)  │   │ 2× H200            │
              └──────────────┘   └────────────────────┘
```

The vLLM endpoint is **never** reachable from the internet. If a Cubbie Skill ever calls the
platform it reaches the FastAPI layer, which holds the disclosure logic and talks to inference
privately (ADR 0001).

### Module map

| # | Module | Path | Task |
|---|---|---|---|
| 1 | Cubbie integration adapter | `skills/squad-sync/` | T0b |
| 2 | Skill execution layer | `backend/skill/` | T2 |
| 3 | Personal agent runtime | `backend/agents/` | T2 |
| 4 | Agent-to-agent protocol | `contracts/` → `backend/protocol/` | T1 → T2 |
| 5 | Group chat coordination | `groupchat/` | T9 |
| 6 | Privacy and approval service | `backend/privacy/` | T2 |
| 7 | Shared persistence | `backend/db/` | T2 |
| 8 | Inference abstraction | `contracts/inference.md` → `backend/inference/` | T1 → T2, T3 |
| 9 | Evaluation and observability | `ml/` | T4 |

---

## 2. Trust boundaries

There are four, and only the first is subtle.

**B1 — Client ↔ backend.** Every surface above the line is untrusted, *including our own
frontend and our own Discord bot*. Identity comes from the validated bearer token and from
nothing else; no endpoint accepts a client-supplied user id as proof of who the caller is. A
client that asks for more than it may see gets a filtered response or a 403, never a trusting one.

**B2 — Student ↔ student.** The boundary the product exists to defend. Two students in the same
negotiation are in different trust domains. Everything crossing B2 is an availability envelope at
an agreed disclosure level; nothing else crosses, ever.

**B3 — Backend ↔ inference.** Prompts carry already-filtered envelopes. Raw calendar text never
reaches the model, so a logged or leaked prompt cannot leak a student's reasons.

**B4 — Backend ↔ Cubbie.** Cubbie runs on the student's own device context and holds that
student's connected accounts. It is a client of ours for exactly one student, and it cannot
message anyone else — that limit is the platform's, and we build with it rather than around it.

### Where the privacy guarantee is enforced

**One place: the disclosure filter in the privacy service, on egress.**

Every payload leaving the backend toward another student passes through it. Not the agents — an
agent is an LLM-driven component and cannot be the last line of defence. Not the clients — a
rendering bug would become a data breach. Not the schemas alone, though
`availability.schema.json` rejects over-disclosure structurally as a second, independent net.

A single enforcement point is testable: T2's privacy suite asserts against the actual outbound
payload, and T7 re-asserts it against the running system.

---

## 3. Disclosure levels

The core product guarantee. Each level is a strict superset of the one above it.

| Level | May contain | May never contain |
|---|---|---|
| `none` | A yes/no answer to one specific proposed time | Any enumeration of busy times |
| `free_busy` | Intervals marked busy, free or tentative | Reason, category, label, location, participants |
| `category` | `free_busy` + one of `academic`, `work`, `social`, `personal` | Free text of any kind |
| `full` | `category` + a human-readable label | — requires an explicit, logged, scoped grant |

**"busy 2–4pm" is permitted at `free_busy`. "therapy at 2pm" is only ever possible at `full`,
and `full` requires a grant the student gave deliberately.**

Two design notes that are easy to get wrong later:

- **The category enum is deliberately blunt.** `personal` absorbs health, therapy, family and
  everything else private. Never add `medical`, `health` or similar: a category that reveals why
  someone is unavailable defeats the whole ladder.
- **Reasons are a closed vocabulary.** Agents decline with `reason_code: conflict`, never with
  prose. Free-text explanation is the most common way a careful system leaks.

Default for a new negotiation is `free_busy`. `redactions` tells the recipient *how many* items
were withheld but never what, so "minimum disclosure" is visibly different from "nothing to hide".

---

## 4. Agent authority, and its limits

A student's agent acts under a `scope` carried in every message
(`agent-protocol.schema.json`): a negotiation id, an explicit list of permitted actions, an
expiry, and a disclosure ceiling.

**The agent may, within scope:** read its own student's data; propose, counter, accept or reject
a time; escalate.

**The agent may never:** exceed `max_disclosure_level`; read another student's data without a
grant row; act after `expires_at`; perform an action not in `actions`; or give the approval that
only a human can give.

**Anything that books, sends, commits or pays requires `granted_by: per_negotiation` and an
explicit human approval**, through `POST /approvals/{id}`. The approval response states exactly
what will be revealed if the student accepts — consent is informed or it is not consent. This
also mirrors Cubbie's own rule that the student's yes is always required.

Authority is explicit, bounded and expiring. It is never implied by possession of a token.

---

## 5. One negotiation, end to end

Three students want an hour together this week. Ana's calendar has a 2pm appointment she has told
no one about.

1. **Initiate.** Ana's client calls `POST /negotiations` with the participants, the window and
   `max_rounds`. State: `gathering`.
2. **Gather.** Each student's agent builds an availability envelope from their own data — via
   Cubbie's connected Canvas and Calendar for a Skill user — reduces it to that student's
   disclosure level, and `PUT /me/availability`. **Ana's 2pm becomes `busy 14:00–16:00` with no
   label, and her `redactions` counter increments.** The backend re-applies her ceiling and
   rejects anything above it.
3. **Negotiate.** The LangGraph runtime runs a bounded loop. Agents exchange `propose` and
   `counter` messages; each is validated against the protocol schema, checked against its scope,
   and passed through the disclosure filter on egress. State: `negotiating`, `round` increments.
4. **Converge, or do not.** On overlap, the proposal collects votes. With no overlap inside
   `max_rounds`, the state becomes `failed` with `outcome.kind: max_rounds_exceeded` and
   `requires_human_approval: true`. **Failure to converge is a product outcome, not a bug** — it
   surfaces to the humans who can actually resolve it.
5. **Approve.** State `awaiting_approval`. Each student sees the proposed time *and what
   accepting will reveal*, and answers for themselves. No agent can answer for them.
6. **Confirm.** All approvals in → `converged`, with `outcome.agreed_slot`. Calendar writes happen
   only now, and on each student's own account.
7. **Throughout:** every participant can see the transcript — what their agent said and at what
   disclosure level. Nobody learns about Ana's appointment. They learn she was busy.

The same flow serves all three tracks. Only the surface differs: Cubbie texts Ana, the frontend
draws the timeline, the Discord bot posts the proposal to the group.

---

## 6. Data model

| Entity | Holds | Notes |
|---|---|---|
| `student` | internal id, auth subject, display preferences | Email and name live here and **never** leave it |
| `student_ref` | per-negotiation pseudonym | Minted per negotiation. A stable cross-negotiation id would let a recipient join two negotiations and rebuild a calendar nobody agreed to share |
| `calendar_source` | connected account metadata | Tokens in the environment / a secret store, never in Git or the database in plaintext |
| `commitment` | the student's real events: time, title, location | **Never crosses B2.** The source for envelopes, never itself transmitted |
| `availability_envelope` | a filtered, levelled view of commitments | What actually crosses B2 |
| `grant` | grantor, grantee agent, negotiation, max level, expiry | Required for any cross-student read; creating one writes an audit record |
| `negotiation` | participants, window, status, round, max_rounds | Serialises to `negotiation-state.schema.json` |
| `message` | one protocol envelope, as sent | The audit trail |
| `approval` | who approved what, when, and what was disclosed | Immutable |
| `audit_log` | every cross-student read and every disclosure | Append-only. The privacy claim is only as good as this record |

**Postgres** holds everything durable. **Redis** holds ephemeral session and negotiation
scratch state with a TTL, and no private data outlives its TTL. Raw `commitment` rows are never
written to Redis.

---

## 7. What this means for each track

**Track 1 (T0b)** — the Skill is instructions-only and depends on nothing we run. Cubbie reads
Canvas and Calendar, builds the envelope at `free_busy`, and the *student* shares it. Cubbie
cannot message anyone else, so the student is the transport, by design.

**Track 2 (T2, T5, T7)** — personal agents negotiate through the backend. The judging prompt
asks how agents handle conflicting constraints, what they share, and when they ask their
students to confirm: that is §3, §4 and §5 of this document respectively.

**Track 3 (T9)** — the Discord bot is the group-side view of the same negotiation. It posts
proposals and collects confirmations; it holds no disclosure logic of its own, because B1 says it
is just another untrusted client.

---

## 8. Known limitations

- `student_ref` is per-negotiation, but a participant in *two* negotiations with the same person
  can still correlate them by timing. Not solved; out of scope for the hackathon.
- The disclosure ladder is coarse. There is no per-recipient level within one negotiation.
- No encryption at rest beyond what Postgres provides by default.
- `category` leaks more than it looks: knowing someone is `personal`-busy every Tuesday at 2 is
  itself a signal. `free_busy` is the default for that reason.
