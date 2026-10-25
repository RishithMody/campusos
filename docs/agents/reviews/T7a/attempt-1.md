# Review — T7a, attempt 1 of 3

| | |
|---|---|
| **Task ID** | `T7a` |
| **Branch** | `task/T7a-live-verify` |
| **Reviewer CLI** | `codex` |
| **Date (UTC)** | `2026-10-25T01:07:01Z` |
| **Attempt** | `1` / 3 |
| **Verdict** | <!-- PASS | CHANGES_REQUESTED | BLOCKED | ESCALATE --> |

> Review the **diff**, not the author's description of it. You did not write this code and
> share no memory with the agent that did — that independence is the point.
>
> This is attempt `1` of 3. After the third, the loop stops and escalates to the human.
> There is no infinite autonomous repair loop.

```
git diff main...HEAD
git log --oneline main..HEAD
```

---

## 1. Correctness and acceptance criteria

<!-- Go through docs/task-graph.md for this task, criterion by criterion.
     Verified = you ran something or read the code that implements it. -->

| Acceptance criterion | Met? | Evidence |
|---|---|---|
| | | |

## 2. Security and privacy

CampusOS exists to protect private student information. **Try to break the guarantees** — do not
just read for style.

| Check | Result | Notes |
|---|---|---|
| Student A's agent cannot read B's data (direct call) | | |
| No IDOR on path/query params | | |
| Identity derived from token, never a client-supplied ID | | |
| Negotiation messages respect the disclosure level | | |
| Revoked / expired grants are actually rejected | | |
| No secrets in code, config, logs, or error messages | | |
| No private schedule detail in logs or stack traces | | |
| Inference endpoint not publicly exposed, auth in front | | |

## 3. API contract compatibility

<!-- Does the change still satisfy contracts/? Is any published schema modified (not allowed
     outside T1 without Orchestrator approval)? Would this break the frontend or another agent
     already building against it? -->

## 4. Test coverage

<!-- Do the task's required tests exist and actually assert the thing they claim?
     A test that passes against a broken implementation is worse than no test.
     Name the untested paths — especially error and partial-failure paths. -->

| Required test (from task graph) | Exists | Passes | Actually asserts it |
|---|---|---|---|
| | | | |

**Tests run by me, with real output:**

```
<!-- paste the actual command and actual output; never a pass you did not observe -->
```

## 5. Regressions

<!-- Full suite, not just the new tests. A fix that breaks another task is not a fix. -->

```
<!-- paste real output -->
```

## 6. Unnecessary complexity

<!-- Abstractions with one caller, speculative generality, duplicated logic, a dependency
     that earns nothing. Flag it, but do not block a PASS on taste alone — separate
     "must fix" from "would be nicer". -->

---

## Findings

Severity: `critical` (data leak, auth bypass, data loss) · `major` (acceptance criterion
unmet, broken contract) · `minor` (quality, naming, clarity) · `nit` (optional)

| # | Severity | File:line | Finding | Required fix |
|---|---|---|---|---|
| 1 | | | | |

## Verdict

**Verdict:** <!-- PASS | CHANGES_REQUESTED | BLOCKED | ESCALATE -->

- `PASS` — criteria met, tests pass, nothing above `minor`. **Recommend human merge.**
  (You never merge. Human approval is required.)
- `CHANGES_REQUESTED` — findings above. Returns to the implementing agent for attempt `1`+1.
  Every finding must be specific enough to fix without guessing.
- `BLOCKED` — cannot review. State exactly what is missing.
- `ESCALATE` — three attempts exhausted. Write `ESCALATION.md` and stop.

**Rationale:**

**If CHANGES_REQUESTED — hand back with:**
```
./scripts/agents.sh start <role> T7a
```
Point the agent at this file. It fixes, re-runs tests, re-commits, and then:
```
./scripts/agents.sh review T7a
```
