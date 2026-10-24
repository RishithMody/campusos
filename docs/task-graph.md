# CampusOS — Task Dependency Graph

**This file is the authoritative task state.** The Orchestrator is the only agent that edits it.
A task may not start until every dependency is `DONE`.

Status values: `BLOCKED` → `READY` → `IN_PROGRESS` → `REVIEW` → `DONE`

Last updated: 2026-10-24 (T0 complete — scope expanded to all three tracks)

---

## ✅ Requirements are now verified — read this before planning anything

`docs/hackathon-requirements.md` records the official rules with a source URL and date for every
claim. T0 replaced the old assumptions. The four findings that reshape this graph:

1. **All three submission windows are OPEN right now, and no close time is set.** Queried live
   2026-10-24T18:50:26Z. There is **no verified deadline** — the site's "first 10 hours" is not
   the authoritative cutoff, and the authoritative one is `null`. Re-check before any time-based
   decision.
2. **Track 1 is the gate.** Tracks 2 and 3 are refused by the organizers' database until the team
   has a Track 1 entry. Their window is already open; only our own Track 1 entry blocks us.
3. **A Track 1 Skill is a folder with a `SKILL.md` in a public GitHub repo.** That is the whole
   bar. No app, no backend, no manifest. There is no review gate, entries are editable while the
   window is open, and edits keep accumulated votes — so **submitting early is free and strictly
   better**, because Track 1 is scored largely on public votes over time.
4. **Cubbie cannot do group chat and cannot text anyone but its own student.** Track 3 therefore
   cannot be built on Cubbie, and Track 2's agent-to-agent traffic cannot flow through Cubbie.
   Both are explicitly allowed to use any messaging app and any open-source framework.

**Still unverified** (see the `## Unverified` section of the requirements doc): every deadline,
kickoff time, Track 2/3 judging criteria, the vote-vs-social weighting, and video length rules.
Ask the organizers: <https://discord.gg/7eJADTbQMT>.

## ⛔ Blocked on human decisions

`T0b` cannot ship until the human answers D1–D5 in `docs/hackathon-requirements.md`:
repo visibility, team roster and entry owner, the Track 1 pivot, Track 3 on Discord, and whether
to submit Track 1 early. Nothing is published without that sign-off.

---

## DAG

```
T0 (DONE) ──> T0b  Track 1 Skill ── submit early ──┐
                    │  unlocks Tracks 2 and 3      │
                    │                              │
T1 (contracts, all three tracks)                   │
 │                                                 │
 ├──> T2 (backend) ────────────┐                   │
 ├──> T3 (GPU inference) ──┬───┤                   │
 ├──> T4 (ML baseline) ────┴──> T6 (optional)      │
 ├──> T5 (frontend / viz) ─────┤                   │
 │                             │                   │
 │                   T2+T3+T5 ─┴──> T7 ──> T10 (Track 2 submission) ──┐
 │                                                                    │
 └──> T9 (Track 3 group chat) ─────────> T11 (Track 3 submission) ────┤
                                                                      │
                                                      T0b + T10 + T11 ┴──> T8 (final)
```

**Critical path to a *valid* submission: `T0b` alone.** It needs no other task and can ship today.
**Critical path to the full product: `T1 → T2 → T7 → T10`.**
T6 is off the critical path and must never delay T8.

One product, three entries: the availability envelope written in T1 is the Track 1 Skill's output,
the Track 2 agent-to-agent message, and the Track 3 group-chat payload. The backend is shared.

## Status board

| ID | Task | Track | Agent | CLI | Depends on | Status |
|---|---|---|---|---|---|---|
| T0 | Verify hackathon requirements | all | Orchestrator | Claude Code | — | `REVIEW` |
| T0b | **Track 1 Cubbie Skill + submission** | 1 | Orchestrator | Claude Code | T0 + D1–D5 | `BLOCKED` (human) |
| T1 | Architecture & shared contracts | all | Orchestrator | Claude Code | — | `READY` |
| T2 | Backend implementation | 1·2·3 | Backend Engineer | Codex | T1 | `BLOCKED` |
| T3 | GPU inference setup (vLLM) | 2·3 | GPU Infra Engineer | Codex | T1 | `BLOCKED` |
| T4 | ML evaluation baseline | 2 | ML Engineer | Claude Code | T1 | `BLOCKED` |
| T5 | Frontend: negotiation visualisation | 2 | Frontend Engineer | Codex | T1 + stable `contracts/` | `BLOCKED` |
| T6 | Optional LoRA fine-tuning | 2 | ML Engineer | Claude Code | T3, T4 | `BLOCKED` |
| T7 | End-to-end integration | 2 | QA / Orchestrator | Codex + Claude Code | T2, T3, T5 | `BLOCKED` |
| T8 | Final demo & all-track submission check | all | Orchestrator | Claude Code | T0b, T10, T11 | `BLOCKED` |
| T9 | **Track 3 group chat assistant (Discord)** | 3 | Frontend Engineer | Codex | T1, T2 | `BLOCKED` |
| T10 | **Track 2 submission package** | 2 | Orchestrator | Claude Code | T0b, T7 | `BLOCKED` |
| T11 | **Track 3 submission package** | 3 | Orchestrator | Claude Code | T0b, T9 | `BLOCKED` |

**T0b is the highest-priority task in the project.** It is small, it is the only mandatory
deliverable, and it unlocks the other two tracks. Do not let the product build delay it.

---
## T0 — Verify hackathon requirements and submission constraints

| | |
|---|---|
| **Agent** | Orchestrator (Claude Code) |
| **Depends on** | — |
| **Status** | `REVIEW` — findings complete, awaiting human sign-off on D1–D5 |
| **Branch / worktree** | `main` in `~/campusos` (docs only) |
| **Owns** | `docs/hackathon-requirements.md` |

**Output:** `docs/hackathon-requirements.md`, 10 sources, every claim dated and cited.

### Acceptance criteria
- [x] Deadline, deliverables, Cubbie Skill format, judging, team rules, repo visibility, and
      model/compute restrictions recorded with a source URL and date checked
- [x] The Cubbie Skill requirement **confirmed**: mandatory for every team, and it is a folder
      with a `SKILL.md` in a public GitHub repo. Format captured well enough for T0b to act on.
- [x] Everything unverifiable listed under an explicit `## Unverified` heading (10 items,
      led by: **no deadline is set**)
- [x] This task graph updated where the rules contradicted it (three contradictions, C1–C3)

### Required tests
None (documentation task). Verification = every claim carries a source URL and a date.

**Why it is `REVIEW`, not `DONE`:** the reviewer for T0 is the human, and five decisions
(D1–D5) are theirs to make. The Orchestrator does not self-certify a facts task.

---

## T0b — Track 1 Cubbie Skill (mandatory deliverable)

| | |
|---|---|
| **Agent** | Orchestrator (Claude Code) |
| **Depends on** | T0 **and** human decisions D1, D2, D3 |
| **Status** | `BLOCKED` — on the human, not on engineering |
| **Branch / worktree** | `task/T0b-cubbie-skill` → `~/campusos-worktrees/T0b-cubbie-skill` |
| **Owns** | `skills/squad-sync/`, `submission/track1/` |

**The highest-priority task in the project.** It is the only mandatory deliverable, it gates
Tracks 2 and 3, and it is scored on votes accumulated over time — so every day it is not live
is a day of scoring lost. It is also small: a `SKILL.md` in a public repo is the entire bar.

**Scope decision (phase 1): instructions only, no backend.** The Skill uses Cubbie's connected
abilities (Canvas, Google Calendar, reminders, documents) and has the student share the result
themselves. The hosted-API version is a later push to the same repo — Cubbie always installs the
newest commit, so the entry never needs resubmitting. This keeps Track 1 independent of whether
our backend is up.

### Acceptance criteria
- [ ] `SKILL.md` exists with valid frontmatter: `name` matching `^[a-z0-9]+(?:-[a-z0-9]+)*$`
      (≤64 chars), `description` ≤1024 chars whose **first sentence is ≤200 chars**
- [ ] Body ≤500 lines; only the spec frontmatter fields
      (`name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`)
- [ ] `python3 validate_cubbie_skill.py <folder>` reports no `FAIL` (warnings reviewed)
- [ ] Names Cubbie's abilities **in plain words** — never tool names, parameters or JSON
- [ ] States what to do when Canvas or Google is **not connected** (every connected ability
      needs a fallback)
- [ ] Every send/book/submit step waits for the student's explicit yes
- [ ] Description says what it adds over the built-in `study-plan-builder`, so Cubbie can tell
      the two apart
- [ ] Installed from its GitHub link on a **real Cubbie account** and the main flow works
- [ ] Contains no secrets, credentials, or private student data
- [ ] Submitted: repo link, team (1–4 members, name + email), project name ≤60, one-liner ≤140
- [ ] A human has reviewed it against `docs/hackathon-requirements.md` §3 and §8

### Required tests
- `validate_cubbie_skill.py` clean of `FAIL` — real output pasted in the handoff
- A manual install-and-run check on a real Cubbie account, recorded honestly. "Could not test,
  no Cubbie access" is a correct answer; a claimed pass that did not happen is not.

**Blocked on:** D1 (repo public, and which repo), D2 (roster + entry owner), D3 (confirm the
pivot away from solo study planning, which collides with Cubbie's built-in `study-plan-builder`).

---

## T1 — Architecture and shared contracts

| | |
|---|---|
| **Agent** | Orchestrator (Claude Code) |
| **Depends on** | — |
| **Status** | `READY` |
| **Branch / worktree** | `task/T1-architecture` → `~/campusos-worktrees/T1-architecture` |
| **Owns** | `docs/architecture.md`, `contracts/`, `docs/adr/` |

The highest-leverage engineering task. Four agents build against these contracts in parallel;
every ambiguity here becomes a merge conflict or an integration failure in T7.

**Now scoped to all three tracks.** The same disclosure-controlled availability envelope must
serve the Track 1 Skill's output, the Track 2 agent-to-agent message, and the Track 3 group-chat
payload. One schema, three surfaces — that is what makes this one product rather than three.

### Acceptance criteria
- [ ] `docs/architecture.md`: component diagram, request flow for a negotiation, data model
      overview, trust boundaries, and where the privacy guarantee is enforced
- [ ] The nine modules named in the expanded brief are placed in the diagram, each owned by
      exactly one task: Cubbie adapter, Skill execution layer, personal agent runtime,
      A2A protocol, group-chat layer, privacy/approval service, persistence, inference
      abstraction, evaluation/observability
- [ ] `contracts/agent-protocol.schema.json`: the agent-to-agent message envelope — sender
      identity, represented student, scope of authority, **disclosure level**, intent
      (propose/counter/accept/reject/escalate), payload, trace ID
- [ ] `contracts/api.openapi.yaml`: REST surface for frontend ↔ backend **and** the HTTPS surface
      a Cubbie Skill script may call (the only integration path Cubbie's sandbox allows)
- [ ] `contracts/negotiation-state.schema.json`: the LangGraph state the frontend visualizes
- [ ] `contracts/inference.md`: the inference interface backend and ML both code against, so
      mock and vLLM are drop-in replacements for each other
- [ ] `contracts/availability.schema.json`: the minimum-disclosure availability envelope shared
      by all three tracks
- [ ] Every schema is valid JSON Schema / OpenAPI and parses (`./scripts/ci/validate_contracts.py`)
- [ ] Disclosure levels are enumerated and defined (what may be revealed at each level)
- [ ] File ownership for T2–T5 and T9 is declared and **disjoint**
- [ ] Assignment files for T2–T5 and T9 written and those tasks moved to `READY`

### Required tests
`./scripts/ci/validate_contracts.py` passes. Each schema has at least one valid and one
deliberately invalid example fixture, and the invalid one is correctly rejected.

**Constraint from T0:** no MCP. Cubbie's sandbox does not support MCP servers, remote or local.
The Skill↔platform boundary is plain HTTPS on port 443 to a publicly reachable host.

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

## T8 — Final demo and all-track submission check

| | |
|---|---|
| **Agent** | Orchestrator (Claude Code) |
| **Depends on** | T0b, T10, T11 |
| **Status** | `BLOCKED` |
| **Branch / worktree** | `task/T8-submission` → `~/campusos-worktrees/T8-submission` |
| **Owns** | `submission/`, `README.md`, `docs/demo-script.md` |

### Acceptance criteria
- [ ] Every verified T0 requirement satisfied, checked item by item against
      `docs/hackathon-requirements.md` — including the field limits in §8
- [ ] **All three entries live in the gallery** and owned by the correct account
- [ ] Track 1 entry confirmed installable from its public GitHub link on a real Cubbie account
- [ ] Demo runs reliably from a clean clone, rehearsed end to end at least twice
- [ ] Demo has a **mock-mode fallback** if the cluster is down mid-demo — never let a live GPU
      dependency be a single point of failure on stage
- [ ] README: what it is, why the privacy model matters, how to run it, architecture summary
- [ ] Honest results section: measured numbers only, limitations stated plainly
- [ ] Repository contains no secrets, credentials, or private data
- [ ] A human has approved the final submission

### Required tests
- Clean-clone smoke test: fresh clone → documented setup → demo runs
- Full suite green
- Secret scan clean (`./scripts/ci/secret_scan.sh`)

---

## T9 — Track 3 group chat assistant (Discord)

| | |
|---|---|
| **Agent** | Frontend Engineer (Codex) |
| **Reviewer** | Claude Code |
| **Depends on** | T1, T2 |
| **Status** | `BLOCKED` |
| **Branch / worktree** | `task/T9-groupchat` → `~/campusos-worktrees/T9-groupchat` |
| **Owns** | `groupchat/`, `tests/groupchat/` |
| **Read-only** | `contracts/` |

**Why not Cubbie:** Cubbie has no group chat and cannot text anyone but its own student
(`docs/hackathon-requirements.md` §6, C1). The rules explicitly allow any messaging app. Discord
is the recommendation — free bot API, the organizers already run a Discord, and it screen-records
well for the demo. **Confirm D4 before starting.**

The group chat is the *group-side surface of the same negotiation* the personal agents run. It
must reuse `contracts/availability.schema.json` and the backend from T2, not reimplement them.

### Acceptance criteria
- [ ] Bot joins a server channel and responds to a scheduling request in that channel
- [ ] Shared study planning: collects each member's availability **without revealing why**
      anyone is busy — disclosure level enforced server-side, not in the bot
- [ ] Group scheduling produces a concrete proposed time from conflicting constraints
- [ ] Collective decision flow: members confirm or decline; the decision is recorded
- [ ] Approval and confirmation flow: nothing is booked until the required confirmations land
- [ ] Visibility into agent decisions **where permitted** — shows what was shared, never more
- [ ] Degrades honestly when the backend is down; never leaks private data in an error
- [ ] Runs against the mock backend with no GPU
- [ ] No bot token, secret, or credential in Git; token comes from the environment

### Required tests
- `pytest tests/groupchat/` green
- Disclosure test: the bot never posts a field above the permitted level, even when the API
  returns one
- Group negotiation test: three members with conflicting constraints converge, or escalate

---

## T10 — Track 2 submission package

| | |
|---|---|
| **Agent** | Orchestrator (Claude Code) |
| **Depends on** | T0b (eligibility), T7 |
| **Status** | `BLOCKED` |
| **Owns** | `submission/track2/` |

Track 2 is judged privately on what we show. Full criteria are **not yet announced** — recheck
before finalising.

### Acceptance criteria
- [ ] Working prototype tied to a real campus scenario, runnable from one documented command
- [ ] Demonstrates, explicitly and on screen: **how agents handle conflicting constraints, what
      they share, and when they ask their students to confirm** (the rules' own wording)
- [ ] A clear stated reason students would say "we need this"
- [ ] Public GitHub repo link ready; website and demo video optional
- [ ] Submitted from the **same account** that owns the Track 1 entry
- [ ] Field limits respected: project name ≤60, one-liner ≤140, 1–4 members, `https://` links

---

## T11 — Track 3 submission package

| | |
|---|---|
| **Agent** | Orchestrator (Claude Code) |
| **Depends on** | T0b (eligibility), T9 |
| **Status** | `BLOCKED` |
| **Owns** | `submission/track3/` |

### Acceptance criteria
- [ ] Working group-chat prototype tied to a real campus scenario
- [ ] Shows what the assistant shares and when it asks for confirmation
- [ ] Public GitHub repo link ready; website and demo video optional
- [ ] Submitted from the same account that owns the Track 1 entry
- [ ] Field limits respected, as T10

---

## Submission checklists

One per track. Tick these against `docs/hackathon-requirements.md` §8 before sending anything.
**An entry is public the moment it is sent.**

### Track 1 · Cubbie Skills
- [ ] Public GitHub repo; link is `https://github.com/<owner>/<repo>` or a folder inside it
- [ ] Folder contains a readable `SKILL.md`; validator reports no `FAIL`
- [ ] Installed from that link on a real Cubbie account; main flow works
- [ ] Team name ≤60 · project name ≤60 · one-liner ≤140 · 1–4 members with distinct emails
- [ ] Signed in as the intended **owner**, with the school email
- [ ] Demo video (optional) on TikTok or Instagram, public
- [ ] Previewed the entry and got an explicit human yes before sending

### Track 2 · Agent-to-Agent Coordination
- [ ] Track 1 entry already submitted (the database refuses otherwise)
- [ ] Public GitHub repo (preview card requires public)
- [ ] Conflicting constraints, what is shared, and the confirmation step are all visible
- [ ] Same owner account as Track 1
- [ ] Website and demo video optional — include if they strengthen a private judging round

### Track 3 · Group Chat Assistant
- [ ] Track 1 entry already submitted
- [ ] Public GitHub repo
- [ ] Runs in a real group chat on a supported messaging app
- [ ] Same owner account as Track 1
- [ ] Website and demo video optional

---

## Concurrency rules

- **Maximum three concurrent implementation agents.** `./scripts/agents.sh create` enforces it.
- **T0b comes before the product build.** It is an Orchestrator task, small, and it unlocks the
  other two tracks. Do not spend an implementation slot before it is submitted.
- First parallel batch, after T1 is `DONE`: **T2 (backend), T3 (GPU), T4 (ML)**.
- Second batch: **T5 (frontend)** when contracts are stable, then **T9 (group chat)** once T2
  exposes a working mock backend. T5 and T9 are both the Frontend Engineer — they run in
  sequence, not together.
- The QA Reviewer runs at checkpoints and does not occupy an implementation slot.
- The Orchestrator coordinates and does not write feature code.
- No nested agent swarms. One session, one task.
