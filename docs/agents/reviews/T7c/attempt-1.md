# Review — T7c, attempt 1 of 3

| | |
|---|---|
| Task | T7c |
| Branch | task/T7c-connector-boundary |
| Reviewed commit | 39769e5b1bff29f166f052124996c3568b1ca0d9 |
| Reviewer CLI | Codex (independent of Claude Code author) |
| Date | 2026-10-24 |
| Attempt | 1 / 3 |

Reviewed `git diff main...HEAD` (9 added files, 1228 lines), production authorization and Discord code, frozen API/protocol validation, renderer, integration specification, and handoff. `docs/agents/assignments/T7c.md` and the reportedly seeded review file did not exist; used the explicit task-graph T7c criteria and created this report from the review template. No production code or contracts changed. Review probes below mutate Python objects in memory only.

```
$ git log --oneline main..HEAD
39769e5 T7c handoff: C1-C9, one BLOCKED half and one surviving mutant
7c3963a T7c: connector boundary conformance C1-C9
```

## 1. Correctness and acceptance criteria

| Acceptance criterion | Met? | Evidence |
|---|---|---|
| C1–C8 implemented verbatim and passing | Partial | Tests pass, but the C2 request is already bound and the sweep includes a message that fails even for its authorized human. Findings 1–2. |
| C9 implemented to extent possible; remainder visibly blocked | Yes | Reference corpus passes; external results test explicitly skips with BLOCKED reason. No external conformance is verified. |
| Valid bodies and real IDs | Partial | Real resources and schema-compatible bodies; semantic validity is not established for every operation. Finding 1. |
| No production/contracts/protected files changed | Yes | Diff contains tests and handoff only. |
| Existing suites pass unchanged | Yes, offline | 186 passed, 9 skipped; live services and external connector remain unverified. |
| Mutation-tested: each case fails when protection breaks | No | M7 and removal of bot VIEW_CHANNEL enforcement both survive all 67 connector tests. Findings 3–4. |

The sweep correctly demands 403 rather than accepting arbitrary failures: 400, 404, 422 and 5xx will fail it. However, 403 alone does not establish which authorization layer refused a request. The subject `bot` has no Student row, and message scope/grant checks also return 403. The separate impersonation probes exercise only GET /me and GET negotiation. Human controls cover only four operations, omitting C2, approval decisions, and message submission. A pending channel-summary is intentionally denied; confirmed-summary success is correctly tested separately. The sweep's reachable set is therefore scenario-specific, not the bot's complete capability set.

## 2. Security and privacy

| Check | Result | Notes |
|---|---|---|
| Student A cannot directly read B's data | Existing regression passes | Backend IDOR/disclosure tests run; T7c is a bot-boundary suite, not a replacement for these. |
| No IDOR on path/query params | Existing checks retained | Registering bot subject and guild are checked on a confirmed summary with successful owner control. |
| Token-derived identity, not client ID | Code verified; partial new coverage | `Service.link` uses stored `Student.discord_id`; `backend/manage.py` obtains it from OAuth users/@me; bodyless member operation rejects a body. Fixture pre-seeds identities; this suite does not exercise the OAuth ceremony. |
| Disclosure level respected | Verified offline | C6 rejects category/full; C8 pins table/enum; confirmed summary excludes names/prose; disclosure matrix passes. |
| Revoked/expired grants rejected | Existing regression passes | Backend grant/stream tests ran; C5 separately verifies channel withdrawal. |
| No secrets in added code/config/errors | Inspected | Fake token only; exception-token assertions run. No live credentials used. |
| No private details in logs/stack traces | No added logging | This change adds tests only; it does not establish external connector logging behavior. |
| Inference endpoint protected | Unchanged | Mock inference used; live deployment exposure not tested here. |

C5 builds all five denied scenarios, compares actual response bytes, and includes a 200 before withdrawal and audience growth. C7 tests registration ownership, summary ownership, wrong guild, and wrong credential kind. These are substantive controls. C5 could additionally assert the durable state labels after decline/reconsent, but existing backend tests already check reconsent state and recovery.

Discord tests establish non-200 rejection with otherwise valid responses, missing bot membership, missing token, invalid JSON, connection failure, and basic pagination. They do **not** establish all unexpected API behavior: no stalled pagination/page-cap test, no malformed channel JSON shape test, and no existing-but-view-denied bot test. The pagination test has no duplicate IDs despite its name. A missing member (404) is not a member whose permissions prohibit viewing. Findings 3–4 identify concrete surviving regressions rather than merely requesting more cases.

## 3. API contract compatibility

All 19 current frozen operations are enumerated. Future GET/POST/PUT/DELETE additions will fail the coverage equality check, but PATCH/HEAD/OPTIONS/TRACE additions are ignored (finding 2). The test repeats production's restricted method filter, so it cannot independently detect that omission.

No frozen contract changed. C8 compares the actual frozen table, enum and renderer dictionary. Although SCHEMA is imported through the renderer, inspection confirms it is loaded from `contracts/api.openapi.yaml`; constant expectations are not generated by calling render(). The corpus's ordinary sentences agree with the table. Nine IDs are covered; `consent_withdrawn` is checked for refusal, consistent with the integration document's silence policy, rather than claimed as a rendered success.

**Known limitation — agreed_slot:** The frozen contract specifies channel-local timezone but not `%Y-%m-%d %H:%M %Z` or the en-dash separator. Consequently the two converged expected strings cannot be derived exclusively from that contract. They pin current reference-renderer behavior. The handoff correctly identifies this; corpus `about` and the test docstring overstate that *all* expectations come from the contract. Clarify that provenance in the corpus itself before giving it to connector authors (minor). The Orchestrator must decide any normative contract update; do not modify the frozen contract in this repair.

**Known limitation — external connector:** The visible skip is honest and permitted by T7c's acceptance criteria. A supplied JSON file would test declared output equality, not prove how it was generated, posted, or logged. Preserve the skip and require actual connector-produced output with provenance before claiming external conformance. C10–C12 and live Discord remain outside this completed offline review.

## 4. Test coverage

| Required test | Exists | Observed result | Actually asserts it? |
|---|---|---|---|
| C1–C4 | Yes | Passing | 403 enforced; incomplete successful controls, finding 1 |
| C5 | Yes | Passing | Five denial bodies compared byte-for-byte |
| C6 | Yes | Passing | Both permitted and forbidden disclosure levels |
| C7 | Yes | Passing | Owner success plus different subject/guild refusal |
| C8 | Yes | Passing | Exact table/enum/dictionary agreement |
| C9 reference | Yes | Passing | Twelve literal corpus cases, including refusal |
| C9 connector | Yes | Skipped | Unverified until external results arrive |
| Fail-closed/mutation coverage | Yes | Insufficient | Two non-equivalent regressions survive |

Tests actually run:

```
$ /Users/rishithmody/campusos/.venv/bin/python -m pytest tests/ -q -rs
/Users/rishithmody/campusos/.venv/bin/python: No module named pytest
```

Created `/private/tmp/t7c-review-venv` with Python 3.11.16 and installed the repository's backend development and groupchat requirements using uv after sandbox approval. No repository dependencies were changed.

```
$ /private/tmp/t7c-review-venv/bin/python -m pytest tests/integration/connector/ -q -rs
..................................................................s.     [100%]
=========================== short test summary info ============================
SKIPPED [1] tests/integration/connector/test_renderer_contract.py:74: BLOCKED: C9's connector half needs the connector. Set CAMPUSOS_CONNECTOR_RESULTS to a JSON file mapping each conformance.json case id to the string that connector rendered (or null if it refused). See task-graph T7c.
67 passed, 1 skipped in 1.04s

$ /private/tmp/t7c-review-venv/bin/ruff check tests/integration/connector
All checks passed!
$ /private/tmp/t7c-review-venv/bin/ruff format --check tests/integration/connector
7 files already formatted
$ /private/tmp/t7c-review-venv/bin/mypy backend
Success: no issues found in 24 source files
$ /Users/rishithmody/campusos/.venv/bin/python scripts/ci/validate_contracts.py
34 contract file(s) parsed, 3 schema(s) exercised against fixtures, 0 error(s), 0 warning(s)
$ /Users/rishithmody/campusos/.venv/bin/python scripts/ci/check_disclosure_matrix.py
104 disclosure check(s) run, 0 failure(s)
```

Complementary `codex review --base main` completed with no actionable findings, but reported it could not run pytest in the pre-existing environment. Its conclusion is not a substitute for the concrete counterexamples below.

### Reproducible adversarial probes

The adjacent `reproduce.py` records exact probes and mutations. Execute from repository root. Every mode runs in its own process; no production files are modified.

```
$ PYTHONPATH=. /private/tmp/t7c-review-venv/bin/python docs/agents/reviews/T7c/reproduce.py controls
post /negotiations/{negotiation_id}/channel-bindings 409 {"type":"about:blank","title":"Binding already active","status":409}
post /approvals/{approval_id} 200 {"schema_version":"1.0","negotiation_id":"neg_df991e5b68bf8178a457c13e","trace_id":"trc_d744d269d098ec53eb2917dd","state_version":3,"status":"gathering","round"
post /negotiations/{negotiation_id}/messages 403 {"type":"about:blank","title":"Request not permitted","status":403}
PATCH addition detected: False

$ PYTHONPATH=. /private/tmp/t7c-review-venv/bin/python docs/agents/reviews/T7c/reproduce.py empty-page
baseline Problem 503
M7 Audience(guild='123', size=0, timezone='UTC')
```

The message fixture grants Alice → Bob but omits Alice → Carol. `Service.submit` checks disclosure authority for every other participant and rejects the missing grant. This is a distinct reason for refusal from bot-kind enforcement.

Both mutation commands below produced the same substantive result. Real output excerpts (warning detail omitted):

```
$ PYTHONPATH=. /private/tmp/t7c-review-venv/bin/python docs/agents/reviews/T7c/reproduce.py m7
..................................................................s.     [100%]
SKIPPED [1] tests/integration/connector/test_renderer_contract.py:74: BLOCKED: C9's connector half needs the connector. Set CAMPUSOS_CONNECTOR_RESULTS to a JSON file mapping each conformance.json case id to the string that connector rendered (or null if it refused). See task-graph T7c.
67 passed, 1 skipped, 2 warnings in 1.20s

$ PYTHONPATH=. /private/tmp/t7c-review-venv/bin/python docs/agents/reviews/T7c/reproduce.py bot-view
..................................................................s.     [100%]
SKIPPED [1] tests/integration/connector/test_renderer_contract.py:74: BLOCKED: C9's connector half needs the connector. Set CAMPUSOS_CONNECTOR_RESULTS to a JSON file mapping each conformance.json case id to the string that connector rendered (or null if it refused). See task-graph T7c.
67 passed, 1 skipped, 2 warnings in 1.20s
```

Both warnings are pytest assertion-rewrite warnings for already-imported langsmith/anyio, not test failures. M7 survival is reproduced, but its classification as equivalent is disproved. M1–M6/M8–M9 counts in the handoff were not independently reproduced; no exact mutation harness or invocation was committed with those counts. Retain reproducible patches/commands and outputs in the repair handoff instead of relying on scratchpad history.

## 5. Regressions

```
$ /private/tmp/t7c-review-venv/bin/python -m pytest tests/ -q -rs
.......................................................s................ [ 36%]
........................................................................ [ 73%]
..........................................s.sssssss                      [100%]
=============================== warnings summary ===============================
../../../../private/tmp/t7c-review-venv/lib/python3.11/site-packages/discord/player.py:30
  /private/tmp/t7c-review-venv/lib/python3.11/site-packages/discord/player.py:30: DeprecationWarning: 'audioop' is deprecated and slated for removal in Python 3.13
    import audioop

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
SKIPPED [1] tests/backend/test_postgres.py:16: Set CAMPUSOS_TEST_POSTGRES_URL to an isolated local PostgreSQL cluster
SKIPPED [1] tests/integration/connector/test_renderer_contract.py:74: BLOCKED: C9's connector half needs the connector. Set CAMPUSOS_CONNECTOR_RESULTS to a JSON file mapping each conformance.json case id to the string that connector rendered (or null if it refused). See task-graph T7c.
SKIPPED [2] tests/live/test_resilience.py:98: Set CAMPUSOS_LIVE=1 for disposable local services
SKIPPED [2] tests/live/test_resilience.py: Set CAMPUSOS_LIVE=1 for disposable local services
SKIPPED [1] tests/live/test_resilience.py:129: Set CAMPUSOS_LIVE_DESTRUCTIVE=1 for dedicated service restarts
SKIPPED [1] tests/live/test_resilience.py:149: Set CAMPUSOS_LIVE_DESTRUCTIVE=1 for dedicated service restarts
SKIPPED [1] tests/live/test_resilience.py:186: Set CAMPUSOS_LIVE=1 for disposable local services
186 passed, 9 skipped, 1 warning in 12.25s
```

## 6. Unnecessary complexity

No blocking complexity concerns. The copied harness is documented and consistent with existing integration practice, though it creates maintenance drift risk. No new production abstraction or dependency was introduced.

## Findings

| # | Severity | File:line | Finding | Required fix |
|---|---|---|---|---|
| 1 | major | tests/integration/connector/test_bot_surface.py:205 (also scenario at :38 and requests at :119) | The “same requests succeed” claim covers only four operations. C2's human request returns 409; message submission returns 403 from a missing participant grant. Thus the sweep does not establish that each request is otherwise permitted. | Build isolated, operation-specific valid scenarios: an unbound channel for C2; grants to every recipient for messages; fresh approval/version for decisions. Assert exact successful status for each authorized control, including safe bounded stream controls. Probe bot tokens naming existing students on sensitive writes as well, so missing Student rows cannot substitute for credential-kind enforcement. Keep pending-summary denial separate from confirmed-summary success. |
| 2 | major | tests/integration/connector/test_bot_surface.py:156–161 | Coverage silently ignores PATCH/HEAD/OPTIONS/TRACE. Injecting a PATCH operation leaves operations() unchanged. | Enumerate all OpenAPI HTTP operation keys independently of production registration; ignore only path metadata. Demonstrate a newly added operation of each supported HTTP method fails until classified. |
| 3 | major | tests/integration/connector/test_discord_failclosed.py:151–155; docs/agents/handoffs/T7c-1.md:122–126 | M7 is not equivalent. A nonempty dict triggers a later TypeError, masking removal of the guard. With `{}`, baseline rejects with 503 but the mutant returns an audience of zero; all connector tests still pass. An underestimated audience invalidates consent assumptions. | Add empty-object and empty-string malformed member pages with otherwise valid context, assert rejection, and rerun M7 to demonstrate failure. Correct the equivalence claim and retain exact reproducible mutation commands/output. |
| 4 | major | tests/integration/connector/test_discord_failclosed.py:122–127 | “Bot cannot see channel” supplies no bot membership, so 404 refuses before can_view is evaluated. Removing the actual bot view-permission check leaves the full connector suite green. | Add a bot that is a valid guild member, is not owner/admin, and lacks VIEW_CHANNEL, with all REST responses 200. Assert refusal for audience/member and verify the guard-removal mutation fails. Keep missing-membership as a separate test; add a known user denied channel visibility for member(). |
| 5 | minor | tests/integration/connector/conformance.json:3–6; test_renderer_contract.py:64 | Corpus provenance says expectations come solely from the frozen table, but agreed_slot formatting is not specified there. | Label converged formatting as reference-implementation compatibility pending Orchestrator specification; preserve the handoff's limitation in the artifact delivered to connector authors. |

## Verdict

Return to the implementing agent for attempt 2 with this report. Fix tests and evidence, not production or frozen contracts. Preserve the explicit external-connector skip. The green offline run is real, but findings 1–4 prevent acceptance of the claimed authorization and fail-closed regression coverage.

**CHANGES_REQUESTED**
