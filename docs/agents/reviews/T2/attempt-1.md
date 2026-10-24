# Review — T2, attempt 1 of 3

| | |
|---|---|
| **Task ID** | `T2` — Backend implementation |
| **Branch** | `task/T2-backend` |
| **Reviewed HEAD** | `dd0897e`, re-verified after merging `main` |
| **Reviewer** | Claude Code (Orchestrator session) |
| **Date (UTC)** | 2026-10-24 |
| **Verdict** | **PASS** |

## On independence

Codex implemented T2; this review is Claude Code, which satisfies CLAUDE.md §6's
opposite-CLI rule. Two things it is honest to state rather than leave implied:

- This reviewer **wrote the contracts T2 implements** (T1). Checking T2 against them is a
  check of someone else's code against this reviewer's own spec. A contract that is wrong in
  a way T2 faithfully reproduced would not be caught here.
- This is **not a separate session**. CLAUDE.md §9 forbids launching child agents, so the
  review ran in the Orchestrator session rather than a fresh one. No shared memory with the
  implementer, but not a cold read either.

Owner asked for one focused review and got one. Everything below was executed, not read.

## What was verified, and how

**The 88 tests are real, and the PostgreSQL test is not a no-op.** A disposable cluster was
started for this review:

```text
$ CAMPUSOS_TEST_POSTGRES_URL=postgresql+psycopg://…@127.0.0.1:55432/postgres \
    backend/.venv/bin/python -m pytest tests/backend/ -q
88 passed in 2.83s
```

Without the variable it reports `1 skipped` with a visible reason, so the count cannot
silently drop. The PostgreSQL test creates a real database, runs `alembic upgrade` from
empty, performs 12 threaded `SELECT … FOR UPDATE` increments, asserts the counter reached
12, then downgrades to base and re-upgrades.

**The row lock is load-bearing.** Removing `.with_for_update()` fails the test with
`StaleDataError` — it asserts serialization rather than merely exercising it.

**The test suite has teeth**, checked by mutation rather than by reading:

| Mutation | Result |
|---|---|
| `outbound()` no longer requires a live cross-student grant | **2 tests fail** |
| `summary()` adds a free-text `"Ana has therapy at 2pm"` field | **9 tests fail** |

**Boundaries.** No protected file, no `contracts/` file, and nothing outside `backend/`,
`tests/backend/`, its own handoff and its own assignment status line.

**Contract compliance.** All 19 published operations have handlers. `ruff check`, `ruff
format --check` and `mypy` (24 files) pass, as claimed. Repo suite, contract validation and
the disclosure matrix all pass from this branch.

## Focus areas

**Privacy.** `backend/privacy/service.py` is the single egress filter, 95 lines, and it is
the right 95 lines. `own_calendar()` refuses a cross-student raw calendar read *even under a
full grant*. `envelope()` caps at the ceiling, strips `label`/`category` per level, counts
redactions and re-validates against the frozen schema. `outbound()` strips
`note_for_own_student` and audits every cross-student disclosure.

One control here was not in the contract and should have been: `envelope(prompt=True)` caps
at `free_busy`, so an explicitly granted `full` label never enters a model prompt. Good
instinct, and `test_private_notes_only_in_own_chat_and_never_in_model_prompt` holds it.

**Consent.** Approvals bind to `state_version`; stale decisions are 409. Agent accepts
require a recorded human approval. Channel bindings require every participant, growth forces
re-consent, withdrawal ends posting, and a superseded approval cannot confirm a replacement
audience. `test_declined_and_pending_are_indistinguishable_to_bot` holds the 403 opacity rule.

**Authorization.** `test_every_endpoint_requires_auth`, forged identity, IDOR and expired
token tests all present and passing. Identity comes from the token; no endpoint takes a
client-supplied subject.

**Concurrency.** Covered above. Per-worker async serialization is disclosed as favouring
prototype correctness over throughput — the right trade here, and stated plainly.

**Deterministic Discord templates.** `backend/channels/summary.py` is a closed `status →
template_id` map with no free text, no interpolation and no inference import, validated
against the frozen `ChannelSummary` before return. An unmapped status raises 403 rather than
inventing a template. This is exactly what the owner required.

## Findings

| # | Severity | Finding |
|---|---|---|
| N1 | nit | The contract lists `consent_withdrawn` as a `template_id`, but `TEMPLATES` has no entry for it — withdrawal 403s at the endpoint, so the bot never receives that summary. The enum value is unreachable. Harmless; worth removing from the contract at the next version bump rather than adding a code path |

No `critical`, `major` or `minor` findings.

## Carried forward, not blocking

From T2's own limitations, the two that later tasks must not forget:

- **A signed human-kind claim is not proof of a human ceremony unless the issuer enforces
  it.** The whole consent model rests on the token issuer. T7 should test this boundary.
- **No live Redis, no real Discord, no live vLLM.** fakeredis, unit-tested permission
  calculations, mock HTTP transports. T9 makes the Discord half real; T3 the vLLM half.

## Verdict

**PASS.** Criteria met, tests pass and assert what they claim, nothing above a nit.
**Recommend merge.** The reviewer does not merge.
