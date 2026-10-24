# CampusOS — Shared Agent Conventions

**This file is the single source of truth for rules that apply to every agent, human or AI.**
`AGENTS.md` (read by Codex) is a pointer to this file. Do not duplicate rules between them.

CampusOS is an AI-powered student coordination platform: personal agents negotiate schedules,
resolve conflicts, manage group activities, and protect private information on behalf of students.
Built for the Cubbie Hackathon.

---

## 1. Read this before you touch anything

You are one of six agents working in parallel on isolated Git worktrees. **Claude Code and Codex
do not share conversation memory.** Every piece of context you need must come from repository
files. Likewise, anything you learn that another agent needs must be written to a file.

On session start, read in this order:

1. `CLAUDE.md` (this file) — shared rules
2. `docs/agents/roles/<your-role>.md` — your role, scope, and hard limits
3. `docs/task-graph.md` — the dependency DAG and authoritative task state
4. `docs/agents/assignments/<TASK_ID>.md` — your specific task brief
5. `docs/agents/status.md` — what everyone else is doing right now

Then state which task you are on and your plan **before** editing files.

## 2. Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js, TypeScript, Tailwind CSS |
| Backend | FastAPI, Python 3.11+ |
| Agent runtime | LangGraph |
| Inference | vLLM |
| Base model | Qwen3 8B |
| Training | LoRA / QLoRA |
| Hardware | 2× NVIDIA H200 (remote, see `docs/infra-policy.md`) |
| Storage | PostgreSQL + Redis |
| Deployment | Docker |

Do not introduce a new framework, language, or orchestration dependency without an
Architecture Decision Record in `docs/adr/` approved by the Orchestrator.

## 3. Repository layout and file ownership

```
backend/      FastAPI service, LangGraph workflows      owner: Backend Engineer
frontend/     Next.js app                               owner: Frontend Engineer
ml/           datasets, eval harness, training configs  owner: ML Engineer
infra/        Docker, vLLM, GPU validation scripts      owner: GPU Infra Engineer
contracts/    shared API + protocol schemas             owner: Orchestrator (T1)
tests/        cross-cutting integration tests           owner: QA / Security Reviewer
docs/         documentation and coordination            see below
scripts/      orchestration tooling                     owner: Orchestrator
```

**Only edit files inside your task's declared ownership** (see `docs/task-graph.md`).
If you need a change outside it, write the request into your handoff file and stop — do not
reach into another agent's directory.

### Protected shared files

These are **Orchestrator-only** and a Git hook will reject your commit if you change them
from an agent worktree:

- `CLAUDE.md`, `AGENTS.md`
- `docs/task-graph.md`
- `docs/agents/status.md`
- `docs/agents/roles/**`
- `scripts/agents.sh`, `scripts/lib/**`, `scripts/ci/**`
- `.github/**`, `.githooks/**`
- `pyproject.toml` (shared lint/type/test conventions)

You *are* expected to write to `docs/agents/handoffs/`, `docs/agents/reviews/`, and your own
`docs/agents/assignments/<TASK_ID>.md` status line.

### `contracts/` is frozen once published

`contracts/` holds the API and agent-to-agent protocol schemas produced by T1. Changing a
published contract breaks other agents mid-flight. To change one: write the proposal in your
handoff, mark your task `REVIEW`, and stop. The Orchestrator versions the contract and notifies
dependents.

## 4. Git discipline

- One branch and one worktree per task: `task/<TASK_ID>-<slug>`, e.g. `task/T2-backend`.
- Create them only with `./scripts/agents.sh create <role> [TASK_ID]`. Never `git worktree add`
  by hand — the script enforces the no-overwrite and concurrency rules.
- **Never merge into `main`. Never push to `main`. Never force-push. Never `git branch -D`.**
  Merging to `main` is a human decision. Git hooks enforce this from agent worktrees.
- Commit in small, working increments. Message format:

  ```
  <TASK_ID>: <imperative summary>

  <why, not what>
  ```

- Never commit secrets, `.env`, `*.pem`, private keys, tokens, or dataset dumps. A staged-file
  secret scan runs in `pre-commit`; do not bypass it with `--no-verify`.

## 5. Definition of done

A task is not done until **all** of these hold:

1. Every acceptance criterion in `docs/task-graph.md` is met.
2. The required tests for that task exist, run, and pass.
3. Lint and type checks pass (`ruff` + `mypy` for Python, `eslint` + `tsc --noEmit` for TS).
4. Work is committed on the task branch.
5. A handoff file exists at `docs/agents/handoffs/<TASK_ID>-<n>.md`, from the template.
6. Status in `docs/task-graph.md` is `REVIEW` (the Orchestrator moves it to `DONE`).

**Report what actually ran.** Paste real command output into your handoff. Never write that a
test passed without having run it. "I could not run X because Y" is a correct, useful answer;
a fabricated green check is a serious failure that will be caught in review.

## 6. Review loop — bounded at 3 repair attempts

See `docs/reviews/TEMPLATE.md` for the review checklist. The loop is:

implement → test → commit → independent review → (fix → re-test → re-review) × **max 3** → human merge

If three repair attempts are exhausted, **stop**. Do not keep trying. Write
`docs/agents/reviews/<TASK_ID>/ESCALATION.md` and hand the task back to the human.
There is no autonomous infinite repair loop in this project.

## 7. Security and privacy are acceptance criteria, not polish

CampusOS exists to *protect private student information* while agents negotiate on their behalf.
Therefore, in every task:

- An agent may only read data for the student it represents. Cross-student reads require an
  explicit, logged, scoped grant.
- Negotiation messages carry the **minimum** disclosure needed (e.g. "busy 2–4pm", not
  "therapy appointment at 2pm"). Privacy-preserving disclosure is a product requirement.
- Every endpoint is authenticated and authorized. No endpoint trusts a client-supplied user ID.
- Inference endpoints are never exposed publicly without authentication and network controls.
- No secrets in Git, logs, or error messages. Credentials come from the environment.

## 8. GPU work requires explicit human approval

All coding agents run locally on the operator's Mac. The 2× H200 cluster is remote and shared.
Read `docs/infra-policy.md` before any remote work. In short:

- **Never** start training, launch inference, or connect to the cluster without a written
  approval token in your assignment file. No agent self-approves GPU spend.
- Never store SSH keys or credentials in Git.
- Never run a training job that competes with a live inference workload.

## 9. Concurrency

Maximum **three** concurrent implementation agents. The QA Reviewer runs at review checkpoints
and does not hold an implementation slot. The Orchestrator coordinates and does not implement
feature code.

**Do not launch child agents or nested agent swarms.** You are a single session doing one task.
If the task is too big, say so in your handoff and let the Orchestrator decompose it.

## 10. Priority order

Keep the minimum viable hackathon submission ahead of optional experiments. If you must choose,
a working demo beats a better model. Fine-tuning (T6) is explicitly optional.
