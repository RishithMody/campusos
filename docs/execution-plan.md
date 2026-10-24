# CampusOS — execution plan

Five phases. The ordering principle: **keep the minimum viable submission ahead of optional
experiments at every point.** At the end of each phase there is something submittable.

**Three tracks, one product.** Track 1 is a Cubbie Skill and is mandatory; it gates Tracks 2 and
3, which are judged privately and share one submission window. All three are surfaces over one
backend — see `docs/adr/0001-three-track-unified-architecture.md`. Verified rules, with sources,
are in `docs/hackathon-requirements.md`.

If the schedule compresses, work is dropped from the bottom: T6 first, then the richer frontend,
then live inference — never the submission requirements or the working negotiation demo.

---

## Phase 0 — Foundation

**Goal:** know the rules, agree the architecture, and have the orchestration working.

| Work | Task | Agent | State |
|---|---|---|---|
| Orchestration infrastructure | — | — | ✅ **done** (2026-10-24) |
| Verify hackathon requirements & submission constraints | T0 | Orchestrator | ✅ **done** (2026-10-24) — `REVIEW` |
| Cubbie Skill deliverable (mandatory, Track 1) | T0b | Orchestrator | **blocked on the human** (D1–D3) |
| Architecture & shared contracts, all three tracks | T1 | Orchestrator | **next** |

**Exit criteria**
- ✅ Hackathon rules documented **with source URLs and dates** — `docs/hackathon-requirements.md`
- ✅ Cubbie Skill requirement confirmed: a folder with a `SKILL.md` in a public GitHub repo
- [ ] `contracts/` published and validated; ownership for T2–T5 and T9 declared and disjoint
- [ ] `./scripts/agents.sh doctor` green

**Why T0 went first:** it paid for itself immediately. It found that all three windows are open
with **no deadline set**, that Track 1 gates the other two tracks, that Cubbie cannot do group
chat, and that the originally briefed Track 1 product duplicates a Skill Cubbie already ships.
Each of those would have been discovered late and expensively. See
`docs/adr/0001-three-track-unified-architecture.md`.

**The new Phase 0 exit gate is a submitted Track 1 entry.** It is the only mandatory deliverable,
it unlocks Tracks 2 and 3, and it is scored on votes accumulated over time.

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
| Group chat assistant on Discord (Track 3) | T9 | Frontend (Codex) |
| End-to-end integration + full test suite | T7 | QA (Codex) + Orchestrator |
| Track 2 submission package | T10 | Orchestrator |
| Track 3 submission package | T11 | Orchestrator |
| Demo script, docs, all-track submission check | T8 | Orchestrator |

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
4. **Track 3** (T9, T11) — a whole track, but an optional one; dropping it costs one entry
   and nothing else, because it shares the backend rather than owning any of it
5. **Track 2** (T10) — drop only after Track 3
6. — nothing below this line is droppable —
7. Privacy/authorization tests (the product's core claim)
8. Working three-agent negotiation (the demo)
9. **Track 1 (T0b)** — mandatory. Missing it scores zero *and* forfeits eligibility for the
   other two tracks. It is also the cheapest thing in this list. Ship it first, not last.
