# CampusOS

AI-powered student coordination. Each student has a personal agent that negotiates schedules,
resolves conflicts, and coordinates group activities on their behalf — **while protecting what
the student has not chosen to share.** An agent says "busy 2–4pm", never why.

Built for the Cubbie Hackathon.

> **Status: orchestration only.** No product code exists yet. This repository currently contains
> the multi-agent development workflow used to build CampusOS. Phase 0 (T0: verify hackathon
> requirements, T1: architecture and contracts) is the next work.
>
> T8 replaces this README with the submission README.

---

## Stack

Next.js · TypeScript · Tailwind — FastAPI · Python · LangGraph — vLLM · Qwen3 8B · LoRA/QLoRA
— PostgreSQL · Redis — Docker — 2× NVIDIA H200 (remote)

## How this repository is built

Six specialised agents work in parallel, each a plain `claude` or `codex` session in its own Git
worktree on its own branch. They share **no** memory — the repository is the only channel between
them — and **no agent can merge.** A human reviews and merges everything.

| Agent | CLI | Owns | Task |
|---|---|---|---|
| Orchestrator | Claude Code | `docs/`, `contracts/`, `scripts/` | T0, T1, T7, T8 |
| Backend Engineer | Codex | `backend/` | T2 |
| ML Engineer | Claude Code | `ml/` | T4, T6 |
| GPU Infra Engineer | Codex | `infra/`, `docker/` | T3 |
| Frontend Engineer | Codex | `frontend/` | T5 |
| QA / Security Reviewer | Codex ↔ Claude Code | `tests/` | T7, every review |

Reviews always run on the **opposite** CLI from the one that wrote the code, bounded at three
repair attempts before the loop stops and escalates to the human.

## Quick start

```bash
cd ~/campusos
./scripts/agents.sh doctor            # verify CLIs, git identity, hooks
./scripts/agents.sh start orchestrator  # Phase 0 begins here: T0, then T1
```

Then, once T1 is merged, the first three parallel agents:

```bash
./scripts/agents.sh create backend && ./scripts/agents.sh create gpu && ./scripts/agents.sh create ml
./scripts/agents.sh start backend     # one per Warp tab
./scripts/agents.sh status            # monitor from anywhere
./scripts/agents.sh review backend    # independent review when it reports REVIEW
```

Full runbook: **[`docs/orchestration.md`](docs/orchestration.md)**

## Documentation

| File | What it is |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | **Shared rules for every agent.** Single source of truth. |
| [`AGENTS.md`](AGENTS.md) | Codex entry point — a pointer to `CLAUDE.md`, not a copy |
| [`docs/orchestration.md`](docs/orchestration.md) | Operator runbook: every command, monitoring, merging, troubleshooting |
| [`docs/task-graph.md`](docs/task-graph.md) | **Authoritative task state** — the T0–T8 DAG, ownership, acceptance criteria |
| [`docs/execution-plan.md`](docs/execution-plan.md) | Phases 0–4, exit criteria, and what gets dropped first |
| [`docs/infra-policy.md`](docs/infra-policy.md) | H200 policy: GPU approval, access, scheduling, no public endpoints |
| [`docs/agents/status.md`](docs/agents/status.md) | Live status board and open questions for the human |
| [`docs/agents/roles/`](docs/agents/roles/) | The six agent role definitions |
| [`docs/reviews/TEMPLATE.md`](docs/reviews/TEMPLATE.md) | The review checklist |

## Guard rails

These are enforced by Git hooks and the orchestration script, not by convention — a rule that
lives only in a prompt is a rule that eventually gets forgotten.

- Agents cannot commit to `main`, merge, or push `main`
- Agents cannot edit protected shared files (`CLAUDE.md`, the task graph, `scripts/`, `.github/`)
- Staged secrets are blocked before they reach a commit
- No worktree or branch is ever overwritten; no branch is ever force-deleted
- `cleanup` refuses to discard uncommitted work
- Maximum three concurrent implementation agents
- No GPU or cluster access without a human-signed, scoped, budgeted, expiring approval token
- The review loop stops after three repair attempts and escalates

## ⚠️ Nothing about the hackathon rules is verified yet

No submission requirement, deadline, or Cubbie Skill format in this repository has been checked
against an official source. **T0 exists to fix that, and it runs first.** See the warning at the
top of [`docs/task-graph.md`](docs/task-graph.md).
