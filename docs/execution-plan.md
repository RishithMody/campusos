# CampusOS — execution plan

Five phases. The ordering principle: **keep the minimum viable submission ahead of optional
experiments at every point.** At the end of each phase there is something submittable.

If the schedule compresses, work is dropped from the bottom: T6 first, then the richer frontend,
then live inference — never the submission requirements or the working negotiation demo.

---

## Phase 0 — Foundation

**Goal:** know the rules, agree the architecture, and have the orchestration working.

| Work | Task | Agent | State |
|---|---|---|---|
| Orchestration infrastructure | — | — | ✅ **done** (2026-10-24) |
| Verify hackathon requirements & submission constraints | T0 | Orchestrator | **next** |
| Cubbie Skill deliverable (mandatory, Track 1) | T0b | Orchestrator | blocked on T0 |
| Architecture & shared contracts | T1 | Orchestrator | ready |

**Exit criteria**
- Hackathon rules documented **with source URLs and dates** — no unverified assumptions left
  masquerading as facts
- Cubbie Skill requirement confirmed and its format captured
- `contracts/` published and validated; file ownership for T2–T5 declared and disjoint
- `./scripts/agents.sh doctor` green

**Why T0 before T1:** T0 is a few hours of reading that can invalidate T1's assumptions. Doing
it second means discovering a format requirement after four agents have built toward the wrong
artifact.

---

## Phase 1 — Functional baseline

**Goal:** **three student agents negotiating a schedule conflict, end to end, on mocked
inference.** This is the real milestone of the project. Everything after it is improvement.

| Work | Task | Agent |
|---|---|---|
| FastAPI backend, agent protocol, LangGraph negotiation | T2 | Backend (Codex) |
| ML eval harness + synthetic dataset (mock-backed) | T4 | ML (Claude Code) |
| GPU env validation + Docker, written not executed | T3 | GPU Infra (Codex) |

First parallel batch: **T2, T3, T4** — exactly the three implementation slots.
T5 (frontend) waits until contracts stop moving.

**Exit criteria**
- Three agents negotiate to convergence with **no GPU involved**
- A negotiation that cannot converge escalates to human approval
- Privacy and authorization tests pass: A's agent cannot read B's data; messages carry minimum
  disclosure
- Reviewed by the opposite CLI; merged by the human

**This phase alone is a submittable demo.** Protect that property.

---

## Phase 2 — H200 inference

**Goal:** swap the mock for real inference without changing backend code.

| Work | Task | Agent |
|---|---|---|
| vLLM serving Qwen3 8B, benchmarked, private endpoint | T3 | GPU Infra (Codex) |
| Backend wired to the real inference client | T2 (follow-up) | Backend (Codex) |

**Requires a human-signed GPU approval token.** See `docs/infra-policy.md`.

**Exit criteria**
- vLLM endpoint serving from committed config, `max_num_seqs` ≤ 256, graceful teardown verified
- Endpoint private (localhost/SSH tunnel) and authenticated — never publicly exposed
- Benchmarks recorded with the commands that produced them
- **Mock mode still works.** The demo must survive the cluster being unavailable.

---

## Phase 3 — Evaluation and training

**Goal:** know whether the model is actually good at negotiating, and whether training helps.

| Work | Task | Agent |
|---|---|---|
| Baseline measured on held-out set | T4 | ML (Claude Code) |
| Synthetic training data generated | T4 | ML (Claude Code) |
| LoRA/QLoRA fine-tune — **optional** | T6 | ML (Claude Code) |
| Base vs. fine-tuned comparison | T6 | ML (Claude Code) |

**Exit criteria**
- Baseline reproducible: config, dataset hash, git commit, metrics all recorded
- If T6 ran: honest comparison on the same held-out set, same prompts, same decode params —
  **including a reported regression if that is the result**

**T6 is optional and strictly off the critical path.** It needs its own GPU approval with a
GPU-hour budget. If Phase 4 needs attention, T6 is cancelled without debate.

---

## Phase 4 — Product and demo

**Goal:** something a judge can watch, understand, and trust.

| Work | Task | Agent |
|---|---|---|
| Next.js dashboard, chat, live negotiation visualisation | T5 | Frontend (Codex) |
| End-to-end integration + full test suite | T7 | QA (Codex) + Orchestrator |
| Demo script, docs, submission | T8 | Orchestrator |

**Exit criteria**
- Full stack up from one documented command
- Negotiation visualisation shows *why* a schedule was agreed, and what each agent disclosed
- Full regression suite green; privacy suite green against the integrated system
- Demo rehearsed at least twice from a clean clone, inside the official time limit
- **Mock-mode fallback rehearsed**, in case the cluster dies mid-demo
- Honest results section: measured numbers only, limitations stated
- Human has approved the submission

---

## Dropping order, if time runs out

1. **T6** (fine-tuning) — optional by design
2. Frontend polish beyond the negotiation visualisation
3. Live inference (fall back to mock mode for the demo)
4. — nothing below this line is droppable —
5. Privacy/authorization tests (the product's core claim)
6. Working three-agent negotiation (the demo)
7. Mandatory submission deliverables, T0b included (missing one scores zero)
