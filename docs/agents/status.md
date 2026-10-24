# Agent status board

**Maintained by the Orchestrator.** Agents read this to see what everyone else is doing;
they do not edit it. Authoritative task state is `docs/task-graph.md` — this is the
at-a-glance operational view.

Live view from the shell: `./scripts/agents.sh status`

Last updated: **2026-10-24** — T0 complete, scope expanded to all three Cubbie tracks.

---

## Headline

**All three submission windows are open right now, and no close time is set.** Checked live
2026-10-24T18:50:26Z against the organizers' database. There is no verified deadline anywhere —
see `docs/hackathon-requirements.md` §1.

**Track 1 is the gate.** Tracks 2 and 3 are refused until the team has a Track 1 entry. A Track 1
entry is a folder with a `SKILL.md` in a public GitHub repo — that is the whole bar. There is no
review gate, entries stay editable, and **edits keep accumulated votes**, so submitting a minimal
valid entry early is free and strictly better.

**Nothing has been submitted and nothing has been made public.** Four of the five decisions are
settled (2026-10-24): a **separate public Skill repo**, the **`squad-sync` pivot**, **Discord for
Track 3**, and **submit when polished, not early**. **D2 — the team roster and entry owner — is
still open and blocks every submission.**

Because Track 1 is submitted only when polished, Tracks 2 and 3 stay locked until then. No
deadline is published and a cutoff can appear at any time, so once the Skill exists it must be
kept **validated and submittable on short notice**.

## Right now

| Slot | Agent | Task | CLI | Worktree | State |
|---|---|---|---|---|---|
| — | Orchestrator | T0 | claude | `~/campusos` (primary) | **`DONE`** — signed off 2026-10-24 |
| — | Orchestrator | T0b | claude | `~/campusos-worktrees/T0b-cubbie-skill` | **`REVIEW`** — Skill + public package ready for owner acceptance |
| — | Orchestrator | T0c | claude | — | **blocked on D2** — publish + submit |
| — | Orchestrator | T1 | claude | `~/campusos-worktrees/T1-architecture` | **`REVIEW_WAIVED`** — merged to `main`. Not a `PASS` |
| 1 | Backend Engineer | T2 | codex | `~/campusos-worktrees/T2-backend` | **`READY`** — worktree created |
| 2 | GPU Infra Engineer | T3 | codex | `~/campusos-worktrees/T3-gpu` | `READY` — **deprioritised below Track 1**, not started |
| 3 | ML Engineer | T4 | claude | `~/campusos-worktrees/T4-ml-baseline` | `READY` — **deprioritised below Track 1**, not started |
| — | Frontend Engineer | T5 → T9 | codex | — | waiting on stable `contracts/` |
| — | QA / Security Reviewer | checkpoints | codex / claude | — | idle (no implementation slot) |

**Implementation slots in use: 1 / 3** — only T2 is running. T3 and T4 are provisioned but
deliberately not started: the owner put finishing Track 1 ahead of them on 2026-10-24.
T0b is Orchestrator work and consumes no slot.

## Immediate next action

**Agents, before you write anything:** read the two Codex reports and the waiver in
`docs/agents/reviews/T1/`. T1 was merged **without** its final independent review, and those
reports are the best account of what is sharp about these contracts. Short and specific.

**Human, two things:**

1. **Accept T0b, then unblock T0c.** The Skill is built, validated and packaged; the only
   acceptance criterion left is one nobody can meet locally — installing it on a real Cubbie
   account, which needs the public repo to exist.

   ```bash
   cd ~/campusos-worktrees/T0b-cubbie-skill
   CUBBIE_KIT=~/path/to/cubbie-hackathon-kit ./submission/track1/build_public_repo.sh /tmp/sq
   ```

   Then `submission/track1/SUBMISSION.md` has the ordered checklist.

2. **Supply D2** — the team roster (1–4 members, name + school email each) and which member
   **owns** the entry. It no longer blocks *building* Track 1 (that is done); it blocks
   **publishing and submitting** it, which is T0c, and every other submission after that.

T3 and T4 stay parked until Track 1 is in. T2 keeps running.

## Blocked and waiting

| Task | Waiting on | Who unblocks it |
|---|---|---|
| T0b | **D2** — team roster and entry owner | **Human** |
| T5, T9 | **a free implementation slot** — 3 / 3 in use | whichever of T2/T3/T4 finishes |
| T6 | T3, T4 **and** a human-signed GPU approval token | Human |
| T7 | T2, T3, T5 | the three implementation agents |
| T10 | T0b (eligibility), T7 | Orchestrator |
| T11 | T0b (eligibility), T9 | Orchestrator |
| T8 | T0b, T10, T11 | Orchestrator |

## Open questions for the human

| # | Question | Blocks | Raised |
|---|---|---|---|
| ~~1~~ | ~~What are the Cubbie Hackathon rules, deadline, and Skill format?~~ **Answered by T0** — see `docs/hackathon-requirements.md`. Residual unknowns are listed under its `## Unverified` heading and belong to the organizers, not to us. | — | closed 2026-10-24 |
| 2 | H200 cluster access details — host alias in `~/.ssh/config`, scheduling conventions, who else shares the GPUs. Must not be committed. | T3 | 2026-10-24 |
| 3 | GPU budget cap (GPU-hours) for T6 fine-tuning, if any. T6 is optional. | T6 | 2026-10-24 |
| D1 | ~~Repo visibility~~ **Decided:** a separate public Skill repo; `campusos` stays private. Tracks 2 and 3 need a public repo before T10/T11. | — | closed 2026-10-24 |
| **D2** | **Team roster** (1–4 members, name + school email) and **who owns the entry.** Only the owner can edit; one address is one account; school email enables voting. **Blocks every submission.** | T0b, T10, T11 | **OPEN** |
| D3 | ~~Track 1 direction~~ **Decided:** pivot to `squad-sync`, cross-student coordination with minimum disclosure. | — | closed 2026-10-24 |
| D4 | ~~Track 3 platform~~ **Decided:** Discord. | — | closed 2026-10-24 |
| D5 | ~~Submit Track 1 early?~~ **Decided:** no — submit when polished. Tracks 2 and 3 stay locked until Track 1 is in. | — | closed 2026-10-24 |

## Review loop state

| Task | Attempts used | Verdict | Escalated |
|---|---|---|---|
| T0 | 0 | approved by the human 2026-10-24 | no |
| T1 | 2 / 3 used | attempt 1 `CHANGES_REQUESTED` (7 findings); attempt 2 `CHANGES_REQUESTED` (6 findings); all 13 addressed. **Third review waived by the owner 2026-10-24, risk explicitly accepted.** `REVIEW_WAIVED`, never `PASS` — see `docs/agents/reviews/T1/WAIVER.md` | no |

The loop is bounded at **3** repair attempts per task; the fourth attempt is refused and
`docs/agents/reviews/<TASK>/ESCALATION.md` is written instead.

## What the two reviews changed

Worth knowing before reading the contracts, because several are materially different from the
versions reviewed:

- **The disclosure ladder is checked across the whole message**, not just inside the availability
  envelope. A `free_busy` message can no longer carry a `full` payload. The granted ceiling is
  now required; absent used to validate.
- **Approvals are discoverable before the decision.** `pending_approvals` carries the preview of
  what saying yes reveals, and decisions bind to `state_version`.
- **Two identifiers, not one.** A durable `cnt_` contact handle is what you share to be invited;
  the `stu_` pseudonym is minted per negotiation by the server.
- **A group chat is a disclosure audience the backend owns.** The Track 3 bot posts a separate
  `ChannelSummary` verbatim and never reads participant state.
- **`/health` is authenticated**, like every other path.
- **T2 owns the inference adapter; T3 owns serving.** T3 cannot edit `backend/`.
- **Transcript entries carry `summary_code`, not prose**, and their nested availability may not
  exceed the entry's level. The transcript was a second carrier of the ladder and bypassed it.
- **A partially-approved negotiation is now representable** — `viewer.awaiting_me` separates
  "this negotiation is awaiting approval" from "you still have to act".
- **Track 3 consent is a four-step flow**, per negotiation, with the Discord identity mapping
  submitted by the student rather than the bot.
- **The disclosure ladder has a committed sweep**, `scripts/ci/check_disclosure_matrix.py`,
  which also fails when a schema grows a carrier it does not know about.

## Contract stability

| Contract | Status |
|---|---|
| `contracts/agent-protocol.schema.json` | **FROZEN on `main`** |
| `contracts/api.openapi.yaml` | **FROZEN on `main`** |
| `contracts/negotiation-state.schema.json` | **FROZEN on `main`** |
| `contracts/availability.schema.json` | **FROZEN on `main`** |
| `contracts/inference.md` | **FROZEN on `main`** |

**Merged 2026-10-24 — they are frozen now.** To change one: write the proposal in your handoff,
set your task to `REVIEW`, and stop. Never edit a published schema: three agents are building
against it right now, from sessions that cannot see your change.

Once published, a contract is **frozen**. Changes go through the Orchestrator, who versions
the change and notifies every dependent agent.

## Verified platform constraints that bind every agent

From `docs/hackathon-requirements.md` §6, confirmed against the official kit:

- **No MCP.** Cubbie's sandbox supports no MCP servers, remote or local.
- **HTTPS only**, port 443, to a publicly reachable host. A Skill script cannot reach a server
  started inside the sandbox, and cannot reach an SSH-tunnelled H200 endpoint.
- **Cubbie texts only its own student.** No agent-to-agent traffic through Cubbie; no group chat.
- **Scripts cannot call Cubbie's abilities.** Cubbie fetches the data and passes it in.
- **The student's yes is always required** before sending, booking, submitting or paying.
- **Self-hosted models and external APIs are unrestricted** by the rules.
