# Review — T1, attempt 1 of 3

| | |
|---|---|
| Task ID | T1 |
| Branch | task/T1-architecture |
| Reviewed HEAD | 75e041ef4bc7b10410491fc584290b2eb5890ae0 |
| Reviewer CLI | Codex, independent of the Claude implementer |
| Date (UTC) | 2026-10-24 |
| Attempt | 1 / 3 |
| Verdict | CHANGES_REQUESTED |

Read the shared rules, reviewer role, task graph, assignment, status board, T1-1 handoff,
review template, and the changed contracts, fixtures, architecture and downstream assignments.
Reviewed `git diff main...HEAD` in file groups. The requested seeded review file did not exist;
this file follows `docs/reviews/TEMPLATE.md`. No implementation was modified.

```text
$ git log --oneline main..HEAD
75e041e T1: hand off the contracts for review
73ce446 T1: publish the five shared contracts and the architecture
```

## 1. Correctness and acceptance criteria

| Acceptance criterion | Met? | Evidence |
|---|---|---|
| Component diagram, request flow, data model, trust boundaries, privacy enforcement | Partial | Architecture §§1–6 describe these; creation and approval cannot be completed through the published API (F1–F2). |
| Nine modules placed and individually owned | Partial | All nine appear in the module table, though not all in the diagram. Inference implementation is attributed to T2 and T3 without an adapter file boundary (F7). |
| A2A identity, represented student, scope, disclosure, intent, payload, trace | Partial | Required top-level fields exist; disclosure ceiling is optional and inconsistent nested levels validate (F3). |
| REST surface for frontend and HTTPS Cubbie integration | Partial | HTTPS/443 documented; missing required client flows (F1, F2, F5) and group audience contract (F4). |
| Versioned negotiation state for visualization | Partial | Schema exists, with bounded configuration and outcome rules; no pending approvals or actual disclosed payloads (F1, F5). |
| Mock/vLLM inference interface | Partial | Protocol, inputs, outputs, exceptions and privacy requirements documented; configuration and ownership ambiguity remains (F7). |
| Shared availability envelope | Yes, with integration gaps | One schema referenced across all tracks; F3 concerns its embedding in the A2A envelope. |
| Schemas valid and parse through required validator | Yes within validator's scope | Primary-worktree Python run: 21 files, 3 schemas, zero errors/warnings. YAML parsing is not full OpenAPI validation. |
| Disclosure levels enumerated and defined | Yes, enforcement incomplete | Architecture §3 and availability schema define four levels; F3–F4 identify gaps. |
| Disjoint T2–T5/T9 file ownership | Declared paths yes; responsibility incomplete | Assignments own backend, infra/docker, ml, frontend, groupchat respectively, with distinct test subdirectories. F7 covers inference responsibility. |
| Downstream assignments written and tasks READY | Partial | All five assignments exist and contain context. Authoritative graph still has T1 READY and dependents BLOCKED. Do not prematurely unblock T9 (also depends on T2) or tasks before T1 approval/merge; Orchestrator must reconcile the acceptance wording and update state at the appropriate gate. |

## 2. Security and privacy

There is no backend implementation in this branch. Statements below distinguish contract review
from runtime security testing; no authorization or privacy integration suite is claimed green.

| Check | Result | Notes |
|---|---|---|
| Student A cannot read B directly | Specified, not runtime-tested | Explicit scoped grants and audits required. No running service to attack. |
| No IDOR on path/query params | Specified, not runtime-tested | Filtered state and 403/404 documented. Resource-to-caller checks need T2 tests. |
| Identity from token, not client ID | Partial | Bearer identity required, but human/agent credential distinction and Discord identity/audience mapping are not concretely defined (F4). Health explicitly disables auth (F6). |
| Negotiation messages respect disclosure | Incomplete | Existing negatives reject labels at their own declared low level; changing the nested level bypasses that schema check (F3). This is not evidence of an existing runtime leak. |
| Revoked/expired grants rejected | Incomplete specification | Expiry is documented; no grant revocation operation or semantics for already-open streams. Add a revocation contract before claiming this guarantee tested. |
| No secrets in code/config/errors | Scan passed; runtime untested | Tracked secret scan clean. Synthetic fixtures; errors are specified to omit secrets. |
| No private schedule detail in logs/traces | Specified, not runtime-tested | Inference contract prohibits prompt/completion logging. Runtime tests still required. |
| Inference private and authenticated | Specified, not runtime-tested | Architecture requires private inference; T3 assignment requires authentication/network controls. No GPU access performed. |

## 3. API contract compatibility

These are new contracts, not modifications to previously published schemas. Local JSON Schema
references resolve with the validator registry. OpenAPI references use public HTTPS IDs, but no
bundled/local resolution configuration or successful frontend type generation is supplied;
that integration remains unverified. No full OpenAPI semantic validator was run.

The main compatibility failure is that independently implemented clients cannot complete the
advertised workflows without inventing new interfaces. See F1, F2, F4 and F5. Contract examples
do not demonstrate creation → enrollment → availability → approval → convergence.

## 4. Test coverage

| Required test | Exists | Passes | Actually asserts it |
|---|---|---|---|
| Contract validator | Yes | Yes using primary venv | Checks JSON Schema legality, fixture instances and basic YAML shape; not all OpenAPI semantics. |
| Valid and invalid fixture for each JSON Schema | Yes | Yes | 7 positive and 10 negative fixtures across 3 schemas; each negative is rejected. |
| Privacy boundary cases beyond fixtures | Incomplete | Probe exposes gap | No nested-level/authority-ceiling mismatch negative. No API workflow fixtures. |

**Tests run by me, with real output:**

The literal required command failed because system Python lacks dependencies. Its output was:

```text
$ ./scripts/ci/validate_contracts.py
ERROR contracts/api.openapi.yaml: cannot validate -- PyYAML is not installed, so this OpenAPI document was NOT checked.
         install it with:  uv pip install --python .venv/bin/python pyyaml jsonschema
         then run: .venv/bin/python scripts/ci/validate_contracts.py
         from an agent worktree the venv lives in the primary worktree:
         ~/campusos/.venv/bin/python scripts/ci/validate_contracts.py
ERROR cannot resolve $refs between contracts -- the 'referencing' package is missing (it ships with jsonschema).
         install it with:  uv pip install --python .venv/bin/python pyyaml jsonschema
         then run: .venv/bin/python scripts/ci/validate_contracts.py
         from an agent worktree the venv lives in the primary worktree:
         ~/campusos/.venv/bin/python scripts/ci/validate_contracts.py
ERROR contracts/agent-protocol.schema.json: cannot validate -- jsonschema is not installed, so this schema and its fixtures were NOT checked.
         install it with:  uv pip install --python .venv/bin/python pyyaml jsonschema
         then run: .venv/bin/python scripts/ci/validate_contracts.py
         from an agent worktree the venv lives in the primary worktree:
         ~/campusos/.venv/bin/python scripts/ci/validate_contracts.py
ERROR contracts/availability.schema.json: cannot validate -- jsonschema is not installed, so this schema and its fixtures were NOT checked.
         install it with:  uv pip install --python .venv/bin/python pyyaml jsonschema
         then run: .venv/bin/python scripts/ci/validate_contracts.py
         from an agent worktree the venv lives in the primary worktree:
         ~/campusos/.venv/bin/python scripts/ci/validate_contracts.py
ERROR contracts/negotiation-state.schema.json: cannot validate -- jsonschema is not installed, so this schema and its fixtures were NOT checked.
         install it with:  uv pip install --python .venv/bin/python pyyaml jsonschema
         then run: .venv/bin/python scripts/ci/validate_contracts.py
         from an agent worktree the venv lives in the primary worktree:
         ~/campusos/.venv/bin/python scripts/ci/validate_contracts.py

3 contract file(s) parsed, 3 schema(s) exercised against fixtures, 5 error(s), 0 warning(s)
```

```text
$ .venv/bin/python scripts/ci/validate_contracts.py --strict
zsh:1: no such file or directory: .venv/bin/python
```

Using the existing primary environment resolved that environment issue without installing anything:

```text
$ /Users/rishithmody/campusos/.venv/bin/python scripts/ci/validate_contracts.py --strict

21 contract file(s) parsed, 3 schema(s) exercised against fixtures, 0 error(s), 0 warning(s)
```

Targeted schema probe (exit 0; diagnostic, not a passing privacy test):

```python
# Executed with: /Users/rishithmody/campusos/.venv/bin/python - <<'PY'
import json
from pathlib import Path
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
p=Path('contracts')
schemas=[json.loads(f.read_text()) for f in p.glob('*.schema.json')]
r=Registry().with_resources((s['$id'],Resource.from_contents(s)) for s in schemas)
s=json.loads((p/'agent-protocol.schema.json').read_text())
v=Draft202012Validator(s,registry=r)
x=json.loads((p/'examples/agent-protocol/invalid-overdisclosing-payload.json').read_text())
print('Original negative fixture accepted:',v.is_valid(x))
x['payload']['availability']['disclosure_level']='full'
print('free_busy message with full nested therapy label accepted:',v.is_valid(x))
x=json.loads((p/'examples/agent-protocol/valid-propose.json').read_text())
x['scope']['max_disclosure_level']='none'
print('none scope with free_busy message accepted:',v.is_valid(x))
del x['scope']['max_disclosure_level']
print('Message missing disclosure ceiling accepted:',v.is_valid(x))
# PY
```

```text
Original negative fixture accepted: False
free_busy message with full nested therapy label accepted: True
none scope with free_busy message accepted: True
Message missing disclosure ceiling accepted: True
```

## 5. Regressions

Full existing tooling suite run; no application `tests/` directory exists yet. Python/TypeScript
application tests, lint and type checks were not run: this diff adds JSON/YAML/Markdown only.
The following is the complete suite output, assembled from successive process output chunks:

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
  PASS  deps missing is a hard failure                     (exit 1)
Secret scan actually catches secrets
  PASS  planted credentials are blocked                    (exit 1)
Worktree lifecycle
  SKIP  create / handoff / cleanup                         (task/T1-architecture already exists)

31 passed, 0 failed, 1 skipped

$ ./scripts/ci/secret_scan.sh --tracked
secret-scan: clean
```

Requested complementary review initially failed inside the sandbox:

```text
$ codex review --base main
WARNING: proceeding, even though we could not create PATH aliases: Operation not permitted (os error 1)
Error: failed to initialize in-process app-server client: Operation not permitted (os error 1)
```

Rerun with approved escalation completed with exit 0. Its final findings, independently checked
against the files here, were:

```text
Contract validation passes, but the published API cannot support negotiation creation and human approval end to end without additional, undocumented interfaces. These gaps block clients implementing the frozen contracts independently.

Full review comments:

- [P1] Expose pending approval IDs and previews before accepting decisions — /Users/rishithmody/campusos-worktrees/T1-architecture/contracts/api.openapi.yaml:181-192
  When a negotiation reaches `awaiting_approval`, neither `NegotiationState` nor any GET endpoint supplies an `approval_id` or disclosure preview. Consequently, the frontend and Discord client cannot construct this required request or show what accepting will reveal before submitting it; returning information after the decision cannot provide informed consent. Add a caller-scoped pending-approval representation containing the ID and preview to the read/stream contract.

- [P1] Define how participants are identified before negotiation creation — /Users/rishithmody/campusos-worktrees/T1-architecture/contracts/api.openapi.yaml:89-93
  Creating a negotiation requires participant `stu_` references, but the availability contract and data model define these as pseudonyms minted per negotiation, never reusable across negotiations. No endpoint allocates these references or resolves invitees before creation, so a client cannot start its first negotiation using the published API. Define an invitation/bootstrap mechanism or a separate creation-time participant identifier, then return server-minted negotiation-local references.
```

## 6. Unnecessary complexity

No new runtime dependency or speculative framework introduced. Bounded rounds, closed reason
codes and strict object shapes are useful. The disclosure ladder and shared decisions are copied
into five assignments; linking the authoritative definition would reduce drift (optional).
Requiring mock and vLLM to be indistinguishable by timing is unnecessary and conflicts with
measured latency and distinct model names; behavioral substitutability is the useful requirement.

## Findings

| # | Severity | File:line | Finding | Required fix |
|---|---|---|---|---|
| F1 | major | contracts/api.openapi.yaml:181; contracts/negotiation-state.schema.json:9 | Approval is unreachable and cannot provide informed consent. The POST requires an `apr_` ID, but no read/stream response exposes one, or exposes the disclosure preview before deciding. State forbids adding undeclared fields. | Add caller-scoped pending approvals with ID, exact action/proposal, intended recipients/disclosure preview and expiry/version binding to state or a GET endpoint. Specify human-only authorization and stale-decision handling. Add an awaiting-approval fixture and a complete read → approve example. |
| F2 | major | contracts/api.openapi.yaml:89; contracts/availability.schema.json:15 | Creation requires per-negotiation student pseudonyms before the negotiation exists. There is no enrollment/invite/bootstrap interface to obtain or bind them. Reusing old refs violates the explicit unlinkability rule; inventing refs cannot bind authenticated students. | Specify invitation/enrollment or creation-time opaque references separate from negotiation-local pseudonyms. Have the server establish identity bindings and return fresh refs; document how each participant obtains their own ref for availability submission, including concurrent negotiations. Add a three-participant creation example. |
| F3 | major | contracts/agent-protocol.schema.json:40,63,76 | The claimed schema safety net accepts a low-disclosure message carrying a `full` availability envelope with a therapy label. It also accepts a message above its scope ceiling, or without any ceiling. The existing over-disclosure fixture tests only a label inconsistent with the nested level; changing that one level makes it pass. | Require the authority ceiling and add enum-based conditional constraints linking scope ceiling, message level and nested availability level. Add negative fixtures for each mismatch and retain runtime grant checks. Clearly distinguish structural validation from authenticated authority validation in the ML/inference instructions. |
| F4 | major | docs/agents/assignments/T9.md:104; contracts/api.openapi.yaml:218 | Track 3 must be filtered for the entire channel, including nonparticipants, but the API only describes a student bearer and grants to individual agents. No channel/audience identity, channel-scoped consent, or bot-to-student credential binding is specified. T9 is simultaneously told to render backend output and never implement filtering. A participant-filtered response is not authorization to broadcast it. | Define the backend-owned channel audience/consent contract and authenticated Discord identity mapping, or constrain channel output to an explicitly approved public summary. Specify how channel membership changes affect access, how approvals remain per-human, and include an unauthorized-channel-member case. |
| F5 | major | docs/agents/assignments/T5.md:34; contracts/api.openapi.yaml:38; contracts/negotiation-state.schema.json:80 | Frozen API cannot supply the required dashboard, own-agent streaming chat or actual disclosure history. There is no list-negotiations/commitments/chat surface. Transcript entries contain intent/level/message ID only; no disclosed payload or GET message route exists. T5 would need to invent APIs or ship permanently disconnected mocks. | Add the minimal authenticated read/chat/transcript contracts required by T5, or have the Orchestrator explicitly reduce its acceptance scope before freezing. Supply examples demonstrating how the UI obtains each required view from backend responses. |
| F6 | major | contracts/api.openapi.yaml:43 | `/health` sets `security: []`, contrary to CLAUDE.md §7 and T2's explicit requirement that every endpoint is authenticated. The document itself says its identity rules have no exceptions. | Inherit bearer authentication here, or obtain and document an explicit project-level health exception and align T2 criteria before freeze. |
| F7 | minor | contracts/inference.md:103; docs/architecture.md:61; docs/agents/assignments/T3.md:117 | Inference contract simultaneously defaults missing configuration to mock and calls missing configuration a startup error. CI already sets `CAMPUSOS_INFERENCE_MODE`, while this contract uses `CAMPUSOS_INFERENCE`. T3 must implement the Python protocol but cannot edit `backend/`, where the module map places the abstraction. | Choose one environment name and missing-value behavior; coordinate CI update. Name a single owner/path for protocol types, mock and vLLM adapter, plus the import boundary for T4; distinguish adapter implementation from T3 serving infrastructure. |

## Verdict

**CHANGES_REQUESTED**

The required fixture suite passes in the available primary environment, but the frozen interfaces
cannot yet support creation, informed approval and the required clients independently. Schema
privacy coverage also misses a demonstrated inconsistency. No merge recommended.

Return to the Orchestrator with this file:

```sh
./scripts/agents.sh start orchestrator T1
# Implement fixes, re-run checks, commit and refresh the handoff, then:
./scripts/agents.sh review T1
```

Next review is attempt 2 of at most 3. This review neither merges nor changes task state.
