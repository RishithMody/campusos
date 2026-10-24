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

**Nothing has been submitted and nothing has been made public.** Five decisions are waiting on
the human before anything ships.

## Right now

| Slot | Agent | Task | CLI | Worktree | State |
|---|---|---|---|---|---|
| — | Orchestrator | T0 | claude | `~/campusos` (primary) | **`REVIEW`** — findings delivered |
| — | Orchestrator | T0b | claude | — | **blocked on human** (D1–D3) |
| — | Orchestrator | T1 | claude | — | **ready to start** |
| 1 | Backend Engineer | T2 | codex | — | waiting on T1 |
| 2 | GPU Infra Engineer | T3 | codex | — | waiting on T1 |
| 3 | ML Engineer | T4 | claude | — | waiting on T1 |
| — | Frontend Engineer | T5 → T9 | codex | — | waiting on stable `contracts/` |
| — | QA / Security Reviewer | checkpoints | codex / claude | — | idle (no implementation slot) |

**Implementation slots in use: 0 / 3**

## Immediate next action

**Human:** answer D1–D5 in `docs/hackathon-requirements.md`. D1–D3 unblock T0b, which is the only
mandatory deliverable and the gate for the other two tracks.

In parallel, T1 (architecture and contracts) is `READY` and depends on nothing:

```bash
cd ~/campusos
./scripts/agents.sh create orchestrator T1
```

T0b and T1 are both Orchestrator tasks and do not consume implementation slots. T0b should go
first if the human's decisions land — it is small and it is the one thing that must ship.

## Blocked and waiting

| Task | Waiting on | Who unblocks it |
|---|---|---|
| T0b | D1 (public repo), D2 (roster + owner), D3 (Track 1 pivot) | **Human** |
| T2, T3, T4 | T1 (`contracts/` published and merged) | Orchestrator |
| T5 | T1 + contracts declared **stable** | Orchestrator |
| T6 | T3, T4 **and** a human-signed GPU approval token | Human |
| T7 | T2, T3, T5 | the three implementation agents |
| T9 | T1, T2, and D4 (Track 3 on Discord) | Human + Backend |
| T10 | T0b (eligibility), T7 | Orchestrator |
| T11 | T0b (eligibility), T9 | Orchestrator |
| T8 | T0b, T10, T11 | Orchestrator |

## Open questions for the human

| # | Question | Blocks | Raised |
|---|---|---|---|
| ~~1~~ | ~~What are the Cubbie Hackathon rules, deadline, and Skill format?~~ **Answered by T0** — see `docs/hackathon-requirements.md`. Residual unknowns are listed under its `## Unverified` heading and belong to the organizers, not to us. | — | closed 2026-10-24 |
| 2 | H200 cluster access details — host alias in `~/.ssh/config`, scheduling conventions, who else shares the GPUs. Must not be committed. | T3 | 2026-10-24 |
| 3 | GPU budget cap (GPU-hours) for T6 fine-tuning, if any. T6 is optional. | T6 | 2026-10-24 |
| D1 | **Make the repository public — and which repo holds the Skill?** Required by all three tracks. The Skill may live in a folder of this repo, or in a separate public repo. | T0b, all submissions | 2026-10-24 |
| D2 | **Team roster** (1–4 members, name + school email) and **who owns the entry.** Only the owner can edit it; one address is one account. | T0b | 2026-10-24 |
| D3 | **Confirm the Track 1 pivot** away from solo study planning, which collides with Cubbie's built-in `study-plan-builder`, toward cross-student coordination with minimum disclosure. | T0b, T1 | 2026-10-24 |
| D4 | **Confirm Track 3 on Discord.** Cubbie has no group chat and cannot text anyone but its own student. | T9 | 2026-10-24 |
| D5 | **Submit Track 1 early?** A minimal valid entry now, improved by pushing commits. Gains voting days and unlocks Tracks 2 and 3. | Track 2/3 eligibility | 2026-10-24 |

## Review loop state

| Task | Attempts used | Verdict | Escalated |
|---|---|---|---|
| T0 | 0 | awaiting human review | no |

The loop is bounded at **3** repair attempts per task; the fourth attempt is refused and
`docs/agents/reviews/<TASK>/ESCALATION.md` is written instead.

## Contract stability

| Contract | Status |
|---|---|
| `contracts/agent-protocol.schema.json` | not created (T1) |
| `contracts/api.openapi.yaml` | not created (T1) |
| `contracts/negotiation-state.schema.json` | not created (T1) |
| `contracts/availability.schema.json` | not created (T1) — **new**, shared by all three tracks |
| `contracts/inference.md` | not created (T1) |

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
