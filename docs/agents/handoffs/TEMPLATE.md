# Handoff — <TASK_ID> (#<N>)

| | |
|---|---|
| **Task ID** | `<TASK_ID>` |
| **Branch** | `<BRANCH>` |
| **Commit** | `<COMMIT>` |
| **Date (UTC)** | `<DATE>` |
| **From agent** | <!-- role + CLI, e.g. Backend Engineer (Codex) --> |
| **To** | <!-- Reviewer / Orchestrator / Human --> |
| **Task status now** | <!-- IN_PROGRESS | REVIEW | BLOCKED --> |

> Claude Code and Codex share no memory. This file is the **only** thing the next agent will
> know about your work. Write it for someone with zero context who must act on it today.
> Fill in every section. "N/A" is an acceptable answer; a blank is not.

---

## 1. Completed work

<!-- What now exists and works that did not before. Behaviour, not a file list. -->

## 2. Files modified

<!-- Group by area. Say WHY each changed, not just that it did.
     backend/app/protocol.py   - validates the agent envelope against contracts/
     backend/tests/test_authz.py - new cross-student access tests
-->

## 3. Tests executed and results

<!-- Paste the REAL command and the REAL output. Trimmed is fine; invented is not.
     A failure recorded honestly is useful. A fabricated pass is a serious failure
     that will be caught in review and will cost more time than the bug.

```
$ pytest tests/backend/ -q
.........................                                        [100%]
25 passed in 3.41s
```

If something could not run, say so and why:
     "docker build not run: Docker Desktop was not running on this machine."
-->

| Check | Command | Result |
|---|---|---|
| Unit tests | | |
| Lint | | |
| Type check | | |
| Task-specific required tests | | |

## 4. Acceptance criteria

<!-- Copy the checklist from docs/task-graph.md and tick only what you verified.
     An unticked box with a one-line reason is the correct output for incomplete work. -->

- [ ]
- [ ]

## 5. Known limitations

<!-- What is incomplete, fragile, mocked, hardcoded, or untested. Be specific and
     unflattering. This section is what stops the next agent wasting an hour
     rediscovering something you already knew. -->

## 6. Decisions and assumptions

<!-- Anything you decided that another agent could reasonably have decided differently,
     and any assumption you made because the information was not available. -->

## 7. Impact on other agents

<!-- Did you need something outside your ownership? Does another agent need to change?
     Contract changes go here and MUST be approved by the Orchestrator — never edit a
     published schema yourself. -->

| Who | What they need to know / do |
|---|---|
| | |

## 8. Next required action

<!-- Exactly one clear next step, and who owns it.
     e.g. "Orchestrator: review this handoff, then run ./scripts/agents.sh review backend" -->

**Owner:**
**Action:**
