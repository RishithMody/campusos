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
| — | Orchestrator | T0b | claude | — | **blocked on D2** (roster + owner) |
| — | Orchestrator | T1 | claude | `~/campusos-worktrees/T1-architecture` | **`REVIEW`** — awaiting Codex + merge |
| 1 | Backend Engineer | T2 | codex | — | waiting on T1 |
| 2 | GPU Infra Engineer | T3 | codex | — | waiting on T1 |
| 3 | ML Engineer | T4 | claude | — | waiting on T1 |
| — | Frontend Engineer | T5 → T9 | codex | — | waiting on stable `contracts/` |
| — | QA / Security Reviewer | checkpoints | codex / claude | — | idle (no implementation slot) |

**Implementation slots in use: 0 / 3**

## Immediate next action

**Human, two things:**

1. **Review and merge T1.** The contracts are done and waiting on `task/T1-architecture`.
   Nothing else can start until they are on `main`.

   ```bash
   cd ~/campusos
   ./scripts/agents.sh review T1          # independent Codex review
   git merge --no-ff task/T1-architecture # your decision, not an agent's
   ```

2. **Supply D2** — the team roster (1–4 members, name + school email each) and which member
   **owns** the entry. It is the last thing blocking T0b, the only mandatory deliverable.

After the merge, the Orchestrator moves T2/T3/T4 to `READY` and the first parallel batch starts.
**Do not `create` T2/T3/T4 before merging** — they would branch from a `main` with no
`contracts/` in it.

## Blocked and waiting

| Task | Waiting on | Who unblocks it |
|---|---|---|
| T0b | **D2** — team roster and entry owner | **Human** |
| T2, T3, T4 | **T1 merged to `main`** — contracts exist only on the branch | **Human** (merge) |
| T5 | T1 + contracts declared **stable** | Orchestrator |
| T6 | T3, T4 **and** a human-signed GPU approval token | Human |
| T7 | T2, T3, T5 | the three implementation agents |
| T9 | T1, T2 | Orchestrator + Backend |
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
| T1 | 0 | awaiting Codex review | no |

The loop is bounded at **3** repair attempts per task; the fourth attempt is refused and
`docs/agents/reviews/<TASK>/ESCALATION.md` is written instead.

## Contract stability

| Contract | Status |
|---|---|
| `contracts/agent-protocol.schema.json` | **published on `task/T1-architecture`** — not yet on `main` |
| `contracts/api.openapi.yaml` | **published on `task/T1-architecture`** — not yet on `main` |
| `contracts/negotiation-state.schema.json` | **published on `task/T1-architecture`** — not yet on `main` |
| `contracts/availability.schema.json` | **published on `task/T1-architecture`** — shared by all three tracks |
| `contracts/inference.md` | **published on `task/T1-architecture`** — not yet on `main` |

They become frozen when the human merges. Until then they are reviewable and changeable.

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
