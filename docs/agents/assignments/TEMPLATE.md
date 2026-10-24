# Assignment — <TASK_ID>

| | |
|---|---|
| **Task** | `<TASK_ID>` — <short title> |
| **Agent** | <role> |
| **CLI** | <claude | codex> |
| **Reviewer** | <the opposite CLI> |
| **Depends on** | <task IDs, all must be DONE> |
| **Status** | <BLOCKED | READY | IN_PROGRESS | REVIEW | DONE> |
| **Branch** | `task/<TASK_ID>-<slug>` |
| **Worktree** | `~/campusos-worktrees/<TASK_ID>-<slug>` |
| **Repair attempts** | 0 / 3 |
| **GPU approval** | `NONE` <!-- or the signed token; see docs/infra-policy.md --> |

Written by the Orchestrator before the agent starts. The agent reads it, works, and reports
back through a handoff — it does not edit this file except for the status line.

## Objective

<!-- One paragraph: what this task delivers and why it matters to the product. -->

## File ownership

**You own (edit freely):**
- `<path>/`

**Read-only (never edit):**
- `contracts/`
- everything outside your ownership

## Acceptance criteria

<!-- Copied verbatim from docs/task-graph.md so the agent has one place to look.
     Must be verifiable by a command, not by opinion. -->

- [ ]

## Required tests

- [ ]

## Context the agent cannot infer

<!-- Decisions already made, contracts to read, gotchas, prior findings, links to the
     handoffs of dependency tasks. Agents share no memory: if it is not written here or
     in a linked file, it does not exist. -->

## Out of scope

<!-- Explicit non-goals, so the agent does not expand the work. -->

## Definition of done

1. All acceptance criteria met
2. Required tests written and passing — real output pasted in the handoff
3. Lint and type checks clean
4. Committed on the task branch
5. `./scripts/agents.sh handoff <TASK_ID>` completed and filled in
6. Status set to `REVIEW`. **Do not merge.**
