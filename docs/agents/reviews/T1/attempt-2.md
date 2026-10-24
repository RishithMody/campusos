# Review — T1, attempt 2 of 3

| | |
|---|---|
| **Task ID** | `T1` |
| **Branch** | `task/T1-architecture` |
| **Reviewed HEAD** | `1278a0947e841566d801311af49de46f115016b4` |
| **Reviewer CLI** | Codex |
| **Date (UTC)** | 2026-10-24 |
| **Attempt** | 2 / 3 |

**Filed as attempt 2 by the Orchestrator.** The reviewer wrote this to `attempt-1.md`, which
overwrote the first review. The first review is restored at `attempt-1.md`; this is the second.
The reviewer's own note on the discrepancy follows, unedited.

**Record discrepancy:** This file was not an empty template: HEAD already contained a prior
attempt-1 review, repair commit `4b2185d`, and handoff `T1-2.md`. The task graph calls this
attempt 2, with one repair used. This report reviews the current full diff and uses the filename
explicitly requested by the user. It does not reset the actual repair budget or edit task state.
The earlier report remains available at `a8f07fb:docs/agents/reviews/T1/attempt-1.md`.

Read CLAUDE.md, reviewer role, task graph, T1 assignment, both handoffs, status board and review
template. Inspected the branch diff, contracts, fixtures and dependent assignments, independently
of the implementer's claims. No implementation changed, no GPU accessed, no merge or push.

Commands used to establish scope:

```text
$ git diff main...HEAD
(full diff inspected; also saved to /tmp/t1-review-diff.patch)
$ git log --oneline main..HEAD
1278a09 Merge branch 'main' into task/T1-architecture
2ee29df Merge branch 'main' into task/T1-architecture
555e8b6 T1: hand off attempt 2 with the review responses and real output
4b2185d T1: close the seven findings from the Codex review
a8f07fb T1: record the Codex review of attempt 1 (CHANGES_REQUESTED)
bd716ee Merge branch 'main' into task/T1-architecture
75e041e T1: hand off the contracts for review
73ce446 T1: publish the five shared contracts and the architecture
```

## 1. Correctness and acceptance criteria

| Acceptance criterion | Met? | Evidence |
|---|---|---|
| Architecture: components, request flow, model, boundaries and privacy enforcement | Yes, with workflow gaps below | architecture.md sections 1–6 explicitly describe these; server egress is the primary enforcement point |
| Nine modules and unique task ownership | Yes | Diagram plus module map; T2 owns inference adapter and T3 serving |
| Agent envelope with identity, authority, disclosure, intents, payload, trace | Yes | Required fields and intent conditions; independent 64-combination disclosure check below |
| REST frontend and HTTPS Cubbie surface | Partial | Valid OpenAPI 3.1, but channel confirmation cannot be completed from it (F2); chat framing underspecified (F5) |
| Negotiation state for frontend | No | F1 rejects normal intermediate state; F3 permits inconsistent disclosure |
| Mock/vLLM common inference interface | Partial | Protocol, types, errors and ownership exist; contradictory statements remain (F4) |
| Shared availability envelope | Yes | Schema exists, individual disclosure restrictions and fixtures validate |
| All schemas valid and parse | Yes | Strict validator passes with installed dependencies |
| Each JSON Schema has valid and rejected-invalid fixtures | Yes, coverage limited | Validator exercises all three; additional probes expose missing cases |
| Disclosure levels defined | Partial | Four levels explicitly defined, but transcript representation violates their structural enforcement (F3) |
| T2–T5 and T9 ownership disjoint | Yes | backend/tests/backend; infra/docker/tests/infra; ml/tests/ml; frontend/tests/frontend; groupchat/tests/groupchat |
| Dependent assignments written and tasks READY | Files yes; transition deferred | Files populated. Current task graph explicitly permits approval before human merge and defers READY until afterward; not a finding |

## 2. Security and privacy

These are contract checks, not claims about an implemented service. There is no backend or
integration suite in this checkout to attack at runtime.

| Check | Result | Notes |
|---|---|---|
| Student A's agent cannot read B's data (direct call) | Specified; runtime untested | Explicit scoped grant and audit required; cannot certify implementation |
| No IDOR on path/query params | Specified; runtime untested | Caller-filtered negotiation views, authorization requirements and nondisclosing errors |
| Identity derived from token, never client-supplied ID | Specified; runtime untested | Global bearer security, human-only approval rule; server must bind all subject IDs to authenticated authority |
| Negotiation messages respect disclosure level | Partial | All 64 A2A ladder combinations correct; transcript bypass reproduced (F3) |
| Revoked / expired grants rejected | Specified; runtime untested | Expiry refusal and immediate revocation including open streams are explicit |
| No secrets in code/config/logs/errors | Static scan clean | Tracked-file scanner passed; no actual runtime logs to inspect |
| No private schedule detail in logs/stack traces | Specified; runtime untested | Inference text logging forbidden; Problem responses must omit private data |
| Inference endpoint not public, auth in front | Specified; deployment untested | Private inference network and authenticated API boundary; no cluster access performed |

F3 is a demonstrated schema acceptance defect, not a claim of a deployed data breach. The
server-side disclosure filter remains necessary even after schemas are repaired.

## 3. API contract compatibility

This publishes contracts before downstream implementation; there are no existing application
clients to regress here. Syntax and local reference resolution pass. Semantic compatibility
is not established by that result: T2 cannot return a valid caller-filtered state after the
first human approves (F1), and T9 cannot obtain channel confirmation using the published
mutations (F2). These need resolution before freezing the contracts. The previous A2A ladder
repair is independently verified; it does not cover the newly added transcript representation.

## 4. Test coverage

| Required test | Exists | Passes | Actually asserts it |
|---|---|---|---|
| scripts/ci/validate_contracts.py | Yes | Yes using primary venv | JSON Schema/OpenAPI validity and local references |
| Valid fixtures validate; invalid fixtures rejected | Yes | Yes | All current fixtures exercised; no partial-approval or transcript ladder negative case |
| Full existing regression suite | Yes | 35 passed, 1 skipped | Tooling suite; lifecycle intentionally skipped while this branch exists |

Some negative fixtures have unrelated missing required fields, weakening isolation. For example,
`invalid-converged-without-slot.json` also lacks `viewer` and `state_version`, and
`invalid-counter-without-slot.json` also lacks required scope fields and `in_reply_to`. They
would still fail if their named restriction disappeared. Repair these to fail for the intended
reason, or assert validation error paths (F6).

**Tests run by me, with real output:**

The literal script invocation initially failed because the shell's Python lacked dependencies:

```text
$ ./scripts/ci/validate_contracts.py --strict
ERROR contracts/api.openapi.yaml: cannot validate -- PyYAML is not installed, so this OpenAPI document was NOT checked.
         install it with:  uv pip install --python .venv/bin/python pyyaml jsonschema openapi-spec-validator
         then run: .venv/bin/python scripts/ci/validate_contracts.py
         from an agent worktree the venv lives in the primary worktree:
         ~/campusos/.venv/bin/python scripts/ci/validate_contracts.py
ERROR cannot resolve $refs between contracts -- the 'referencing' package is missing (it ships with jsonschema).
         install it with:  uv pip install --python .venv/bin/python pyyaml jsonschema openapi-spec-validator
         then run: .venv/bin/python scripts/ci/validate_contracts.py
         from an agent worktree the venv lives in the primary worktree:
         ~/campusos/.venv/bin/python scripts/ci/validate_contracts.py
ERROR contracts/agent-protocol.schema.json: cannot validate -- jsonschema is not installed, so this schema and its fixtures were NOT checked.
         install it with:  uv pip install --python .venv/bin/python pyyaml jsonschema openapi-spec-validator
         then run: .venv/bin/python scripts/ci/validate_contracts.py
         from an agent worktree the venv lives in the primary worktree:
         ~/campusos/.venv/bin/python scripts/ci/validate_contracts.py
ERROR contracts/availability.schema.json: cannot validate -- jsonschema is not installed, so this schema and its fixtures were NOT checked.
         install it with:  uv pip install --python .venv/bin/python pyyaml jsonschema openapi-spec-validator
         then run: .venv/bin/python scripts/ci/validate_contracts.py
         from an agent worktree the venv lives in the primary worktree:
         ~/campusos/.venv/bin/python scripts/ci/validate_contracts.py
ERROR contracts/negotiation-state.schema.json: cannot validate -- jsonschema is not installed, so this schema and its fixtures were NOT checked.
         install it with:  uv pip install --python .venv/bin/python pyyaml jsonschema openapi-spec-validator
         then run: .venv/bin/python scripts/ci/validate_contracts.py
         from an agent worktree the venv lives in the primary worktree:
         ~/campusos/.venv/bin/python scripts/ci/validate_contracts.py

3 contract file(s) parsed, 3 schema(s) exercised against fixtures, 5 error(s), 0 warning(s)
```

Exit 1. No installation was needed: the documented primary-worktree environment works:

```text
$ /Users/rishithmody/campusos/.venv/bin/python scripts/ci/validate_contracts.py --strict

30 contract file(s) parsed, 3 schema(s) exercised against fixtures, 0 error(s), 0 warning(s)
```

Exit 0. Additional independent probe, exact command:

```sh
/Users/rishithmody/campusos/.venv/bin/python - <<'PY'
import copy, json
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
root = Path('contracts')
schemas = [json.loads(p.read_text()) for p in root.glob('*.schema.json')]
registry = Registry().with_resources((s['$id'], Resource.from_contents(s)) for s in schemas)
schema = next(s for s in schemas if s['title'] == 'Negotiation state (v1)')
v = Draft202012Validator(schema, registry=registry, format_checker=FormatChecker())
state = json.loads((root/'examples/negotiation-state/valid-awaiting-approval.json').read_text())
print('Baseline awaiting fixture:', 'valid' if v.is_valid(state) else 'INVALID')
approved = copy.deepcopy(state)
approved['pending_approvals'] = []
approved['participants'][0]['state'] = 'accepted'
print('Viewer approved; peers still pending:', [(list(e.path), e.message) for e in v.iter_errors(approved)])
leak = copy.deepcopy(state)
leak['transcript'][0]['disclosed']['availability']['disclosure_level'] = 'full'
leak['transcript'][0]['disclosed']['availability']['slots'][0]['label'] = 'therapy'
print('free_busy transcript with full therapy payload:', 'ACCEPTED' if v.is_valid(leak) else 'rejected')
leak = copy.deepcopy(state)
leak['transcript'][0]['disclosed']['summary'] = 'Ana has therapy at 2pm'
print('free_busy transcript with private prose:', 'ACCEPTED' if v.is_valid(leak) else 'rejected')
agent = next(s for s in schemas if s['title'] == 'Agent-to-agent message envelope (v1)')
a = Draft202012Validator(agent, registry=registry, format_checker=FormatChecker())
msg = json.loads((root/'examples/agent-protocol/valid-propose.json').read_text())
levels = ['none', 'free_busy', 'category', 'full']
checked = 0
for ceiling in levels:
 for outer in levels:
  for inner in levels:
   x = copy.deepcopy(msg)
   x['scope']['max_disclosure_level'] = ceiling
   x['disclosure_level'] = outer
   x['payload']['availability']['disclosure_level'] = inner
   x['payload']['availability']['slots'] = []
   expected = levels.index(ceiling) >= levels.index(outer) >= levels.index(inner)
   assert a.is_valid(x) == expected, (ceiling, outer, inner)
   checked += 1
print('Agent disclosure ladder:', checked, 'combinations matched expected ordering')
PY
```

Actual output (exit 0; this is a diagnostic probe, not an assertion that the defects are fixed):

```text
Baseline awaiting fixture: valid
Viewer approved; peers still pending: [(['pending_approvals'], '[] should be non-empty')]
free_busy transcript with full therapy payload: ACCEPTED
free_busy transcript with private prose: ACCEPTED
Agent disclosure ladder: 64 combinations matched expected ordering
```

## 5. Regressions

```text
$ ./scripts/ci/test_agents_sh.sh
Read-only commands
  PASS  help                                               (exit 0)
  PASS  doctor: reports missing CLIs                       (exit 1)
  PASS  list                                               (exit 0)
  PASS  status                                             (exit 0)
  PASS  unknown command is rejected                        (exit 1)
Guards refuse what they must
  PASS  create: unknown role                               (exit 1)
  PASS  create: unknown task                               (exit 1)
  PASS  create: BLOCKED task                               (exit 1)
  PASS  start: missing worktree                            (exit 1)
  PASS  review: missing worktree                           (exit 1)
  PASS  cleanup: missing worktree                          (exit 1)
  PASS  cleanup: unknown argument                          (exit 1)
Three-track task IDs are known to the tooling
  PASS  create: T9 is a known task                         (exit 1)
  PASS  create: T10 is a known task                        (exit 1)
  PASS  create: T11 is a known task                        (exit 1)
  PASS  T9 is not reported unknown                         (exit 1)
  PASS  T10 is not reported unknown                        (exit 1)
  PASS  T11 is not reported unknown                        (exit 1)
  PASS  T99 is still reported unknown                      (exit 0)
CI helper scripts
  PASS  validate_contracts runs                            (exit 0)
  PASS  validate_contracts --strict                        (exit 0)
  PASS  secret_scan --tracked                              (exit 0)
  PASS  secret_scan rejects bad mode                       (exit 2)
Contract validator catches what it is for
  PASS  fixtures: a correct set passes                     (exit 0)
  PASS  fixtures: unrejected negative                      (exit 1)
  PASS  fixtures: broken positive                          (exit 1)
  PASS  fixtures: none at all                              (exit 1)
  PASS  unresolvable $ref is an error                      (exit 1)
  PASS  unresolvable $ref: no traceback                    (exit 1)
  PASS  openapi: a valid document passes                   (exit 0)
  PASS  openapi: invalid doc is rejected                   (exit 1)
  PASS  openapi: dangling $ref is an error                 (exit 1)
  PASS  openapi: dangling $ref: no traceback               (exit 1)
  PASS  deps missing is a hard failure                     (exit 1)
Secret scan actually catches secrets
  PASS  planted credentials are blocked                    (exit 1)
Worktree lifecycle
  SKIP  create / handoff / cleanup                         (task/T1-architecture already exists)

35 passed, 0 failed, 1 skipped
```

Exit 0. There is no `tests/` directory or application test suite yet. Runtime authorization,
concurrency, inference-down and end-to-end tests could not be run because their implementations
are downstream work. Lint/type checks were not run: this diff adds JSON, YAML and Markdown,
not Python or TypeScript implementation.

```text
$ ./scripts/ci/secret_scan.sh --tracked
secret-scan: clean
$ git diff main...HEAD --check
```

Both exit 0; diff check produced no output.

Complementary pass also ran to completion (exit 0):

```text
$ codex review --base main
Contract validation passes, but the contracts reject a normal partially approved negotiation state and leave channel confirmation without a usable API flow. Transcript validation also permits disclosure-level violations.
```

The quoted paragraph is the actual final-output opening; its three comments identify the same
F1–F3 below. Its exit code means the reviewer completed, not that it approved the contracts.

## 6. Unnecessary complexity

No new framework or speculative implementation abstraction in this diff. Separate durable
contact handles and negotiation pseudonyms have distinct purposes. The disclosure ladder is
explicit and testable. Repeated disclosure prose in five assignments is a maintenance burden,
but not a merge blocker by itself; residual conflicting prose is recorded in F4.

## Findings

Severity uses the repository's categories. These are contract defects; no runtime exploit is claimed.

| # | Severity | File:line | Finding | Required fix |
|---|---|---|---|---|
| F1 | major | contracts/negotiation-state.schema.json:215 | Every `awaiting_approval` response requires a nonempty `pending_approvals`, but line 45 restricts this array to the viewer's own pending decisions. After Ana approves while Ben is still deciding, Ana has an empty array and the global status is still awaiting approval. The response from POST approval and subsequent GET/SSE cannot satisfy the schema without exposing another person's approvals or fabricating a pending decision. Probe reproduces rejection. | Permit empty viewer-private approvals while waiting on peers; distinguish global status from whether this viewer needs to act. Replace the blanket negative fixture with cases for both a pending viewer and an already-approved viewer. Test each participant's view through sequential approvals. |
| F2 | major | contracts/api.openapi.yaml:427 | Channel registration returns `confirmed: false` until participating members confirm, but takes no negotiation or participants. No mutation binds the registered channel to a negotiation or triggers discoverable `post_to_channel` approvals. The only channel/negotiation pairing is a read-only summary GET, which returns 403 until confirmed. T9 is also forbidden to read NegotiationState. Independent clients cannot complete this consent flow without inventing an API. | Specify an authorized channel/negotiation binding mutation, how channel membership and bot binding are verified, how the affected humans discover the preview/approval IDs and decide with human credentials, and how confirmation becomes observable. Update T2/T9 instructions and add a concrete registration → binding → consent → summary example, including missing-consent rejection. |
| F3 | major | contracts/negotiation-state.schema.json:165 | `transcript[].disclosed.availability` validates independently of the transcript entry's disclosure level. A `free_busy` entry accepts `full` availability with a `therapy` label; unrestricted `disclosed.summary` can carry the same private reason. This reintroduces the equivalent of the A2A mismatch on the frontend-facing representation. Both cases reproduced above. | Enforce nested availability level <= transcript entry level. Remove arbitrary lower-level prose or replace it with structured fields/template codes rendered from allowed data. Keep own-student private explanations on a separately scoped surface. Add negative fixtures for mismatched levels and private prose and positive fixtures for permitted transcripts. |
| F4 | minor | contracts/inference.md:7 | Still says callers must not distinguish implementations by timing, while reporting model and measured latency, and the T3 assignment explicitly permits those differences. Lines 84–85 still call mock the default although lines 120–127 specify no default. The repair handoff claims these contradictions were removed, but they remain in the contract. | Remove the stale timing-indistinguishability statement and describe mock as explicitly selected in development/CI, retaining the startup-error rule. |
| F5 | minor | contracts/api.openapi.yaml:134 | Chat streaming is only `type: string`, described as token deltas then a terminal event; neither event names nor data encoding, terminal payload, or stream-error shape is defined. T2 and T5 can choose incompatible framings despite both following this document. | Define the SSE wire format with exact delta/completion/error events and at least one complete example; align the mock client/server to it. |
| F6 | minor | contracts/examples/negotiation-state/invalid-converged-without-slot.json:1 | Several older negative fixtures fail for newly missing required fields as well as the defect named by the fixture; see coverage section. A regression removing the intended restriction can remain green. | Base each negative fixture on a currently valid document and mutate only the targeted constraint, or assert the targeted error path explicitly. |

## Verdict

**Rationale:** Required schema checks and the available regression suite pass, but F1–F3 prevent
contract freeze: a normal approval state is unrepresentable, channel consent cannot be completed,
and transcript validation accepts over-disclosure. Return to the implementing Orchestrator;
retain the actual repair count recorded in the task graph rather than resetting it from this filename.

Hand back with:

```sh
./scripts/agents.sh start orchestrator T1
```

Use this file as the repair brief. Re-run validation and regression checks, commit the repairs,
and request the next review with `./scripts/agents.sh review T1`. Human merge is not recommended.

**Verdict: CHANGES_REQUESTED**
