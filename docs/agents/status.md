# Agent status board

**Maintained by the Orchestrator.** Agents read this to see what everyone else is doing;
they do not edit it. Authoritative task state is `docs/task-graph.md` — this is the
at-a-glance operational view.

Live view from the shell: `./scripts/agents.sh status`

Last updated: **2026-10-24** — orchestration setup complete, no agents started yet.

---

## Right now

| Slot | Agent | Task | CLI | Worktree | State |
|---|---|---|---|---|---|
| — | Orchestrator | T0 → T1 | claude | `~/campusos` (primary) | **next up** |
| 1 | Backend Engineer | T2 | codex | — | waiting on T1 |
| 2 | GPU Infra Engineer | T3 | codex | — | waiting on T1 |
| 3 | ML Engineer | T4 | claude | — | waiting on T1 |
| — | Frontend Engineer | T5 | codex | — | waiting on stable `contracts/` |
| — | QA / Security Reviewer | checkpoints | codex / claude | — | idle (no implementation slot) |

**Implementation slots in use: 0 / 3**

## Immediate next action

**Human:** start the Orchestrator and complete T0, then T1.

```bash
cd ~/campusos
./scripts/agents.sh doctor
./scripts/agents.sh start orchestrator
```

T0 (verify hackathon requirements) comes before T1 (architecture) because T0 is cheap and can
invalidate T1's assumptions. **No hackathon rule in this repository has been verified yet** —
see the warning at the top of `docs/task-graph.md`.

Nothing else may start until T1 is `DONE`: T2–T5 all depend on the shared contracts, and
starting them early produces three incompatible implementations.

## Blocked and waiting

| Task | Waiting on | Who unblocks it |
|---|---|---|
| T0b | T0 (verified Cubbie Skill format) | Orchestrator |
| T2, T3, T4 | T1 (`contracts/` published) | Orchestrator |
| T5 | T1 + contracts declared **stable** | Orchestrator |
| T6 | T3, T4 **and** a human-signed GPU approval token | Human |
| T7 | T2, T3, T5 | the three implementation agents |
| T8 | T0, T7 | Orchestrator |

## Open questions for the human

| # | Question | Blocks | Raised |
|---|---|---|---|
| 1 | What are the actual Cubbie Hackathon rules, deadline, and required Cubbie Skill format? Nothing in this repo has been verified. | T0, T0b, T8 | 2026-10-24 |
| 2 | H200 cluster access details — host alias in `~/.ssh/config`, scheduling conventions, who else shares the GPUs. Must not be committed. | T3 | 2026-10-24 |
| 3 | GPU budget cap (GPU-hours) you are willing to spend on T6 fine-tuning, if any. T6 is optional. | T6 | 2026-10-24 |

## Review loop state

| Task | Attempts used | Verdict | Escalated |
|---|---|---|---|
| — | — | — | — |

No reviews have run. The loop is bounded at **3** repair attempts per task; the fourth
attempt is refused and `docs/agents/reviews/<TASK>/ESCALATION.md` is written instead.

## Contract stability

| Contract | Status |
|---|---|
| `contracts/agent-protocol.schema.json` | not created (T1) |
| `contracts/api.openapi.yaml` | not created (T1) |
| `contracts/negotiation-state.schema.json` | not created (T1) |
| `contracts/inference.md` | not created (T1) |

Once published, a contract is **frozen**. Changes go through the Orchestrator, who versions
the change and notifies every dependent agent — three agents build against these in parallel.
