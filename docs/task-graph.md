# CampusOS — Task Dependency Graph

**This file is the authoritative task state.** The Orchestrator is the only agent that edits it.
A task may not start until every dependency is `DONE`.

Status values: `BLOCKED` → `READY` → `IN_PROGRESS` → `REVIEW` → `DONE`

Last updated: 2026-10-24 (orchestration setup)

---

## ⚠️ Unverified assumption — resolve in T0 before anything else

The hackathon requirements below are **recorded as assumptions, not verified facts.** Nobody
has checked the current Cubbie Hackathon rules yet. In particular the **mandatory Cubbie Skill
submission** is treated here as a hard deliverable because it was identified as one, but its
exact format, scope, and deadline are **unknown to this repository**.

T0 exists to replace these assumptions with verified, cited rules. Do not build toward a
submission format that has not been confirmed. If T0 finds the rules differ, the Orchestrator
updates this graph before any dependent task proceeds.

---

## DAG

```
T0 ─────────────────────────────────────────────┐
 │  (requirements verified)                     │
 └──> T0b (Cubbie Skill submission) ────────────┤
                                                │
T1 ──┬──> T2 (backend) ──────────────┐          │
     │                               │          │
     ├──> T3 (GPU inference) ──┬─────┤          │
     │                         │     │          │
     ├──> T4 (ML baseline) ────┴──> T6          │
     │                         (optional)       │
     └──> T5 (frontend) ───────────┐            │
                                   │            │
                     T2 + T3 + T5 ─┴──> T7 ──> T8
```

Critical path to a submittable demo: **T1 → T2 → T7 → T8**.
T6 is off the critical path and must never delay T8.

## Status board

| ID | Task | Agent | CLI | Depends on | Status |
|---|---|---|---|---|---|
| T0 | Verify hackathon requirements & submission constraints | Orchestrator | Claude Code | — | `READY` |
| T0b | Cubbie Skill submission (mandatory deliverable) | Orchestrator | Claude Code | T0 | `BLOCKED` |
| T1 | Architecture & shared contracts | Orchestrator | Claude Code | — | `READY` |
| T2 | Backend implementation | Backend Engineer | Codex | T1 | `BLOCKED` |
| T3 | GPU inference setup (vLLM) | GPU Infra Engineer | Codex | T1 | `BLOCKED` |
| T4 | ML evaluation baseline | ML Engineer | Claude Code | T1 | `BLOCKED` |
| T5 | Frontend implementation | Frontend Engineer | Codex | T1 + stable `contracts/` | `BLOCKED` |
| T6 | Optional LoRA fine-tuning | ML Engineer | Claude Code | T3, T4 | `BLOCKED` |
| T7 | End-to-end integration | QA / Orchestrator | Codex + Claude Code | T2, T3, T5 | `BLOCKED` |
| T8 | Final hackathon demo & submission | Orchestrator | Claude Code | T0, T7 | `BLOCKED` |

T0 and T1 are both `READY` and both belong to the Orchestrator. Do T0 first — it is cheap, and
it can invalidate T1's assumptions.

---

## T0 — Verify hackathon requirements and submission constraints

| | |
|---|---|
| **Agent** | Orchestrator (Claude Code) |
| **Depends on** | — |
| **Status** | `READY` |
| **Branch / worktree** | `main` in `~/campusos` (docs only) |
| **Owns** | `docs/hackathon-requirements.md` |

**Why first:** every downstream deliverable is shaped by rules nobody has read yet. This task is
hours of reading that can save days of building the wrong artifact.

### Acceptance criteria
- [ ] `docs/hackathon-requirements.md` exists and records, **each with a source URL and the date
      checked**: submission deadline, required deliverables, the Cubbie Skill requirement and its
      exact format, judging criteria, team/eligibility rules, demo format and time limit,
      licensing or open-source requirements, and any model/compute restrictions.
- [ ] The **mandatory Cubbie Skill** requirement is confirmed or refuted in writing. If confirmed,
      its required structure is captured well enough for T0b to be actionable.
- [ ] Anything that could not be verified is listed under an explicit `## Unverified` heading
      rather than guessed at.
- [ ] This task graph is updated if the rules contradict any assumption in it.

### Required tests
None (documentation task). Verification = every claim carries a source URL and a date.

**Hard rule:** do not invent a rule to fill a gap. "Not stated in the published rules" is the
correct entry. A fabricated requirement here propagates into every other task.

---

## T0b — Cubbie Skill submission

| | |
|---|---|
| **Agent** | Orchestrator (Claude Code) |
| **Depends on** | T0 |
| **Status** | `BLOCKED` (pending T0) |
| **Branch / worktree** | `task/T0b-cubbie-skill` → `~/campusos-worktrees/T0b-cubbie-skill` |
| **Owns** | `submission/cubbie-skill/` |

Identified as a **mandatory early deliverable**. Scheduled early and deliberately off the
critical path of the product build, so a late-stage product crunch cannot cause the team to
miss a required submission artifact.

### Acceptance criteria
- [ ] Deliverable matches the format verified in T0, field by field
- [ ] Submitted (or ready to submit) well before the deadline, not on the deadline
- [ ] Contains no secrets, credentials, or private student data
- [ ] A human has reviewed it against the official requirements checklist

### Required tests
Validation against the official format/schema if the rules publish one; otherwise a documented
human checklist review. **Scope is provisional until T0 completes.**

---

## T1 — Architecture and shared contracts

| | |
|---|---|
| **Agent** | Orchestrator (Claude Code) |
| **Depends on** | — |
| **Status** | `READY` |
| **Branch / worktree** | `task/T1-architecture` → `~/campusos-worktrees/T1-architecture` |
| **Owns** | `docs/architecture.md`, `contracts/`, `docs/adr/` |

The highest-leverage task in the project. Three agents build against these contracts in parallel;
every ambiguity here becomes a merge conflict or an integration failure later.

### Acceptance criteria
- [ ] `docs/architecture.md`: component diagram, request flow for a negotiation, data model
      overview, trust boundaries, and where the privacy guarantee is enforced
- [ ] `contracts/agent-protocol.schema.json`: the agent-to-agent message envelope — sender
      identity, represented student, scope of authority, **disclosure level**, intent
      (propose/counter/accept/reject/escalate), payload, trace ID
- [ ] `contracts/api.openapi.yaml`: REST surface for frontend ↔ backend
- [ ] `contracts/negotiation-state.schema.json`: the LangGraph state the frontend visualizes
- [ ] `contracts/inference.md`: the inference interface backend and ML both code against, so
      mock and vLLM are drop-in replacements for each other
- [ ] Every schema is valid JSON Schema / OpenAPI and parses (`./scripts/ci/validate_contracts.py`)
- [ ] Disclosure levels are enumerated and defined (what may be revealed at each level)
- [ ] File ownership for T2–T5 is declared and **disjoint**
- [ ] Assignment files for T2–T5 written and those tasks moved to `READY`

### Required tests
`./scripts/ci/validate_contracts.py` passes. Each schema has at least one valid and one
deliberately invalid example fixture, and the invalid one is correctly rejected.

---

## T2 — Backend implementation

| | |
|---|---|
| **Agent** | Backend Engineer (Codex) |
| **Reviewer** | Claude Code |
| **Depends on** | T1 |
| **Status** | `BLOCKED` |
| **Branch / worktree** | `task/T2-backend` → `~/campusos-worktrees/T2-backend` |
| **Owns** | `backend/`, `tests/backend/` |
| **Read-only** | `contracts/` |

### Acceptance criteria
- [ ] FastAPI app starts clean; `/health` returns 200
- [ ] Every endpoint in `contracts/api.openapi.yaml` implemented, responses contract-valid
- [ ] Agent-to-agent protocol implemented per `contracts/agent-protocol.schema.json`;
      malformed envelopes rejected with a structured error
- [ ] LangGraph negotiation workflow reaches convergence on a three-student conflict, and
      escalates to human approval when it cannot
- [ ] PostgreSQL models + Alembic migrations apply cleanly from empty
- [ ] Redis used for ephemeral session state; no private data persisted in Redis beyond TTL
- [ ] Every endpoint authenticated; identity derived from the token, **never** from a
      client-supplied ID
- [ ] Cross-student access requires an explicit grant row and writes an audit record
- [ ] Inference behind an injectable interface with a working mock; **no GPU dependency**
- [ ] `ruff` and `mypy` clean; `.env.example` committed, no secrets in Git

### Required tests
- `pytest tests/backend/` green
- Authorization test: student A's agent cannot read student B's calendar (direct, forged ID, IDOR)
- Privacy test: negotiation messages carry only minimum disclosure
- Contract tests: responses validate against `contracts/`
- Negotiation state-transition tests covering each edge, including failure to converge

---

## T3 — GPU inference setup

| | |
|---|---|
| **Agent** | GPU Infra Engineer (Codex) |
| **Reviewer** | Claude Code |
| **Depends on** | T1 |
| **Status** | `BLOCKED` |
| **Branch / worktree** | `task/T3-gpu` → `~/campusos-worktrees/T3-gpu` |
| **Owns** | `infra/`, `docker/`, `tests/infra/` |

**Execution gate:** authoring scripts and configs needs no approval. *Running* anything against
the H200s requires a signed approval token in `docs/agents/assignments/T3.md`.
See `docs/infra-policy.md`.

### Acceptance criteria
- [ ] `infra/validate_env.sh`: read-only report of driver, CUDA, PyTorch, vLLM versions, GPU
      topology, VRAM, and existing GPU processes. Idempotent, mutates nothing.
- [ ] Documented, working compatibility matrix (driver ↔ CUDA ↔ PyTorch ↔ vLLM) for these H200s
- [ ] vLLM serves Qwen3 8B with an OpenAI-compatible API, from **committed config** not ad-hoc flags
- [ ] `max_num_seqs` ≤ **256** (512 is a known-bad config on this hardware and is forbidden)
- [ ] Graceful teardown verified: stop/restart leaves no wedged GPU and no orphaned process
- [ ] Endpoint bound to localhost/private interface, reachable only via SSH tunnel,
      **never publicly exposed**; authentication in front of it
- [ ] Dockerfiles build; mock-mode `docker compose up` works on a laptop with **no GPU**
- [ ] `infra/benchmarks/` records tokens/sec, TTFT, p50/p95/p99 under concurrency, VRAM headroom,
      GPU utilization — each with the exact command that produced it
- [ ] No SSH keys, credentials, or `.pem` files in Git

### Required tests
- `pytest tests/infra/` green, including a test asserting `max_num_seqs <= 256`
- `docker build` succeeds for each image
- `docker compose config` validates; mock stack starts with no GPU
- Health-check script correctly reports a down endpoint as down

---

## T4 — ML evaluation baseline

| | |
|---|---|
| **Agent** | ML Engineer (Claude Code) |
| **Reviewer** | Codex |
| **Depends on** | T1 |
| **Status** | `BLOCKED` |
| **Branch / worktree** | `task/T4-ml-baseline` → `~/campusos-worktrees/T4-ml-baseline` |
| **Owns** | `ml/`, `tests/ml/` |

Metrics must be defined and committed **before** any model is run, so the baseline cannot be
retrofitted to flatter a later result.

### Acceptance criteria
- [ ] `ml/metrics.md` defines every metric before first measurement: negotiation success rate,
      rounds to convergence, constraint violations, **privacy leakage rate**, schema-valid output
      rate, latency
- [ ] Synthetic negotiation dataset generator, deterministic for a given seed, documented in
      `ml/data/README.md`; held-out test split never trained on
- [ ] Baseline Qwen3 8B measured on the held-out set, or an explicit, honest record of why it
      could not be (e.g. GPU approval not granted)
- [ ] Results in `ml/runs/<timestamp>-baseline/` with config, git commit, dataset hash,
      metrics JSON, and logs
- [ ] Eval harness runs against the mock inference client with **no GPU**, so it is testable in CI
- [ ] No weights, checkpoints, or large datasets committed

### Required tests
- `pytest tests/ml/` green
- Generator determinism test: same seed → identical dataset
- Eval harness scoring tests on fixed fixtures (known input → known score)
- Privacy-leakage scorer flags an over-disclosing response

**Hard rule:** report only measured numbers. No estimates presented as measurements.

---

## T5 — Frontend implementation

| | |
|---|---|
| **Agent** | Frontend Engineer (Codex) |
| **Reviewer** | Claude Code |
| **Depends on** | T1 **and** `contracts/` declared stable by the Orchestrator |
| **Status** | `BLOCKED` |
| **Branch / worktree** | `task/T5-frontend` → `~/campusos-worktrees/T5-frontend` |
| **Owns** | `frontend/`, `tests/frontend/` |
| **Read-only** | `contracts/` |

Starts **after** the first three agents, when contracts have stopped moving — not in the initial
parallel batch. This is a concurrency-limit decision as much as a dependency one.

### Acceptance criteria
- [ ] Next.js app builds; `npx tsc --noEmit` and `eslint` clean
- [ ] TypeScript types **generated** from `contracts/`, not hand-written
- [ ] Student dashboard: commitments, pending negotiations, items awaiting approval, and a
      visible record of what the student's agent has disclosed on their behalf
- [ ] Chat interface to the student's own agent, with streaming responses
- [ ] Live negotiation visualization driven by `contracts/negotiation-state.schema.json` —
      proposals, constraint collisions, disclosures, and how consensus formed
- [ ] Approval / conflict-resolution UI showing what will be revealed if the student accepts
- [ ] UI never renders fields above the permitted disclosure level
- [ ] Runs against the mock API with the backend absent
- [ ] No secrets in client code

### Required tests
- `npx tsc --noEmit` and `eslint` clean
- Component tests for the negotiation timeline and the approval flow
- Disclosure test: UI does not render over-permitted fields even when the API returns them
- Build succeeds against mock API

---

## T6 — Optional LoRA fine-tuning

| | |
|---|---|
| **Agent** | ML Engineer (Claude Code) |
| **Reviewer** | Codex |
| **Depends on** | T3, T4 |
| **Status** | `BLOCKED` |
| **Branch / worktree** | `task/T6-finetune` → `~/campusos-worktrees/T6-finetune` |
| **Owns** | `ml/training/`, `ml/runs/` |

**OPTIONAL. Off the critical path. Must never delay T8.** Requires a human-signed GPU approval
token in `docs/agents/assignments/T6.md` before a single training step runs.

### Acceptance criteria
- [ ] Human-signed GPU approval token present, with a stated budget cap (GPU-hours) and window
- [ ] Training config committed (base model, LoRA rank/alpha/targets, LR, epochs, seed)
- [ ] Training data drawn from the T4 generator; **held-out test split untouched**
- [ ] No contention: training does not run while a live inference workload serves the demo
- [ ] Base vs. fine-tuned compared on the same held-out set, same prompts, same decode params
- [ ] Result reported honestly, **including a regression** — "LoRA did not improve negotiation
      success rate" is a valid and useful finding
- [ ] Checkpoints on the cluster or object storage, never in Git

### Required tests
- Training config validation test (no silent dependence on a default)
- Comparison harness test on fixtures
- Full eval re-run on the fine-tuned model, same harness as T4

---

## T7 — End-to-end integration

| | |
|---|---|
| **Agent** | QA / Security Reviewer (Codex) + Orchestrator (Claude Code) |
| **Depends on** | T2, T3, T5 |
| **Status** | `BLOCKED` |
| **Branch / worktree** | `task/T7-integration` → `~/campusos-worktrees/T7-integration` |
| **Owns** | `tests/integration/`, `tests/e2e/`, `docker-compose.yml` |

### Acceptance criteria
- [ ] Full stack comes up from one documented command
- [ ] **Three student agents negotiate a real schedule conflict to convergence, end to end**
- [ ] A negotiation that cannot converge escalates to human approval in the UI
- [ ] Works in mock mode with no GPU, *and* against live vLLM once T3 is `DONE`
- [ ] Privacy and authorization suite green against the integrated system (not just unit level)
- [ ] Full regression suite green — T2, T3, T4, T5 tests all still pass
- [ ] Failure modes handled: inference down, DB down, Redis down, agent timeout
- [ ] Integration tests run in CI using mocks, with **no GPU access**

### Required tests
- `pytest tests/integration/` and `pytest tests/e2e/` green
- Cross-student privacy attack suite against the running system
- Regression: every prior task's suite
- Resilience: each dependency killed in turn, system degrades without leaking data

---

## T8 — Final hackathon demo and submission

| | |
|---|---|
| **Agent** | Orchestrator (Claude Code) |
| **Depends on** | T0, T7 |
| **Status** | `BLOCKED` |
| **Branch / worktree** | `task/T8-submission` → `~/campusos-worktrees/T8-submission` |
| **Owns** | `submission/`, `README.md`, `docs/demo-script.md` |

### Acceptance criteria
- [ ] Every verified T0 requirement satisfied, checked off item by item against the rules doc
- [ ] Cubbie Skill deliverable (T0b) submitted and confirmed
- [ ] Demo runs reliably from a clean clone, rehearsed end to end at least twice
- [ ] Demo fits the official time limit, with a **mock-mode fallback** if the cluster is down
      mid-demo — never let a live GPU dependency be a single point of failure on stage
- [ ] README: what it is, why the privacy model matters, how to run it, architecture summary
- [ ] Honest results section: measured numbers only, limitations stated plainly
- [ ] Repository contains no secrets, credentials, or private data
- [ ] A human has approved the final submission

### Required tests
- Clean-clone smoke test: fresh clone → documented setup → demo runs
- Full suite green
- Secret scan clean (`./scripts/ci/secret_scan.sh`)

---

## Concurrency rules

- **Maximum three concurrent implementation agents.** `./scripts/agents.sh create` enforces it.
- First parallel batch, after T1 is `DONE`: **T2 (backend), T3 (GPU), T4 (ML)**.
- T5 (frontend) starts when contracts are stable — typically as T3 or T4 finishes.
- The QA Reviewer runs at checkpoints and does not occupy an implementation slot.
- The Orchestrator coordinates and does not write feature code.
- No nested agent swarms. One session, one task.
