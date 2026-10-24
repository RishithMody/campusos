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
| 8 | Inference abstraction | `contracts/inference.md` → `backend/inference/` | T1 → **T2** |
| 8b | Inference serving | `infra/vllm/` | **T3** |
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

### The ladder is checked in three places at once

A single message carries three disclosure levels, and they are only safe together:

```
scope.max_disclosure_level     what the student granted this agent   (the ceiling)
  >= disclosure_level          what this message claims to reveal
    >= payload.availability.disclosure_level   what the payload actually carries
```

Each must be at or below the one above it, and `agent-protocol.schema.json` enforces the whole
chain. Checking them individually is not enough and we learned it the direct way: review of the
first version of these contracts showed a `free_busy` message happily carrying a `full`
availability envelope with a `therapy` label. Every part was internally consistent. The message
was a disclosure breach.

The ladder travels with the payload, not with one of its carriers. There are two carriers today
— the agent envelope and `transcript[].disclosed` — and each enforces it independently. That
redundancy is deliberate: the transcript was added later and reintroduced the exact bypass the
envelope had just been fixed for, so `scripts/ci/check_disclosure_matrix.py` now sweeps every
carrier and fails when a schema grows one it does not know about.

Free prose is not permitted alongside a disclosure level anywhere. Transcript entries carry a
`summary_code` from a closed vocabulary and the UI renders a sentence from it; "Ana has therapy
at 2pm" is 22 characters and validates against `type: string` at every level in the ladder. The
student's own private explanations are not in the transcript at all — they ask their own agent
on `/me/chat`.

### Two identifiers, opposite lifetimes

| | `contact_handle` (`cnt_`) | `student_ref` (`stu_`) |
|---|---|---|
| Lifetime | Durable until rotated | One negotiation |
| Shared with | Whoever you want to be invitable by | The other participants of that negotiation |
| Purpose | Being found | Being referred to without being correlated |

This split is forced. A `stu_` cannot be the thing you hand someone to start a negotiation,
because it is minted *by* that negotiation; and a durable handle cannot be the thing agents
exchange, because two of them could be joined to rebuild a calendar nobody shared. So there are
two, `GET /me` returns the first, and the server mints the second.

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

0. **Find each other.** Ben and Cal each call `GET /me` and send Ana their `cnt_` contact
   handle, out of band. Ana never learns a `stu_` for either of them; those do not exist yet.
1. **Initiate.** Ana's client calls `POST /negotiations` with those handles as `invitees`, the
   window and `max_rounds`. The server resolves them, mints a **fresh `stu_` for all three**,
   and returns the state with `viewer.student_ref` set to Ana's. State: `gathering`.
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
5. **Approve.** State `awaiting_approval`, and `pending_approvals` now carries Ana's
   `approval_id`, the action, the expiry, and `discloses` — the preview of exactly what saying
   yes would reveal and to whom. Her client renders that *before* the approve control, then
   `POST /approvals/{id}` with the `state_version` she was shown. If the negotiation moved on in
   between, that is a `409` and she is asked again against the new state; she is never recorded
   as approving something she was not shown. No agent token can answer here at all.
6. **Confirm.** All approvals in → `converged`, with `outcome.agreed_slot`. Calendar writes happen
   only now, and on each student's own account.
7. **Throughout:** every participant can see the transcript — what their agent said, at what
   level, and in `disclosed`, the payload it actually sent. Nobody learns about Ana's
   appointment. They learn she was busy.

The same flow serves all three tracks. Only the surface differs: Cubbie texts Ana, the frontend
draws the timeline, and the Discord bot posts `channel-summary.text` to the group — a separate,
smaller document, because the room is a wider audience than any participant.

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
| `contact_handle` | durable, rotatable, shareable handle for one student | What you give someone so they can invite you. Never a `stu_`, never an email |
| `approval` | who approved what, when, what was disclosed, and the `state_version` it was decided against | Immutable. The version binding is what makes it consent to a specific state rather than to whatever was current on arrival |
| `channel` | platform, channel id, ceiling, per-participant confirmation | A group chat is a disclosure audience in its own right: its ceiling applies to everyone in the room, not to the member who asked |
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

**Track 3 (T9)** — the Discord bot is the group-side view of the same negotiation. It holds no
disclosure logic of its own, because B1 says it is just another untrusted client. It reads
`GET /negotiations/{id}/channel-summary` and posts the `text` verbatim; it never reads
`NegotiationState`. The distinction is the whole of Track 3's privacy story: that document is
filtered for *one participant*, and being allowed to see something is not permission to
broadcast it to a room that includes people who are not in the negotiation at all.

Consent to post runs in four steps, and each answers a different question:

| Step | Call | Question | Authenticated as |
|---|---|---|---|
| 1 | `POST /channels` | Is this a real channel with our bot in it? | the bot |
| 2 | `POST /channels/{id}/members` | Which student is which Discord user? | **the student** |
| 3 | `POST /negotiations/{id}/channel-bindings` | May *this* negotiation be discussed in *that* room? | a participant |
| 4 | `GET .../channel-summary` | — serves only once the binding is `confirmed` | the bot |

Three properties are load-bearing. Step 2 is the student's call and never the bot's: if the bot
could assert the identity mapping, every consent decision after it would be worthless. Step 3
raises an ordinary `post_to_channel` approval per participant, so Track 3 adds no second consent
mechanism — one surface, one place to get it wrong. And step 3 is per negotiation: agreeing once
to discuss a study session in a room is not agreeing to the next one.

Every participant approves, including one who is not in the channel, because posting reveals
that they are in the negotiation whether or not they can read the room. If the room later gains
members the binding flips to `pending_reconsent`, since consent was to an audience and the
audience changed. Any participant can withdraw afterwards, and one withdrawal ends it for
everyone: an audience cannot be partially un-told.

---

## 8. Known limitations

- `student_ref` is per-negotiation, but a participant in *two* negotiations with the same person
  can still correlate them by timing. Not solved; out of scope for the hackathon.
- The disclosure ladder is coarse. There is no per-recipient level within one negotiation.
- No encryption at rest beyond what Postgres provides by default.
- `category` leaks more than it looks: knowing someone is `personal`-busy every Tuesday at 2 is
  itself a signal. `free_busy` is the default for that reason.
- **Everything here is specified, not yet running.** The schemas structurally reject a set of
  over-disclosures, and that is a real second net, but the primary guarantee is the server-side
  filter on egress and it does not exist until T2. No runtime privacy claim in this document has
  been tested against a running service; T2 and T7 own that evidence.
- Channel consent is to an audience *size*, not to a membership list. A room that swaps one
  member for another keeps the same count and does not trigger re-consent. Growth is caught;
  substitution is not.
- `channel-summary.text` is free prose composed server-side, and no schema can check it. It is
  the one place where a careless sentence reaches a group chat, and it rests entirely on T2's
  implementation being careful. The `free_busy` ceiling bounds what it has to work with.
