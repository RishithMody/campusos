# AGENTS.md — Codex entry point

**Read `CLAUDE.md` in this repository root. It is the single source of truth for all agent
conventions, and it applies to you in full.** This file exists only because Codex looks for
`AGENTS.md`; the rules are deliberately not duplicated here, so they cannot drift.

Quick orientation, then go read `CLAUDE.md`:

1. `CLAUDE.md` — shared rules (stack, file ownership, Git discipline, definition of done,
   security requirements, GPU approval policy, concurrency limits)
2. `docs/agents/roles/<your-role>.md` — your role and hard limits
3. `docs/task-graph.md` — the dependency DAG and authoritative task state
4. `docs/agents/assignments/<TASK_ID>.md` — your task brief
5. `docs/agents/status.md` — what the other agents are doing

The five rules most often broken, repeated here because they are expensive:

- **Never merge or push to `main`.** Human decision. Git hooks will reject it.
- **Only edit files your task owns** (`docs/task-graph.md`). Protected shared files are
  Orchestrator-only and hooks will reject the commit.
- **Report what actually ran.** Paste real output. Never claim a test passed without running it.
- **Max 3 repair attempts**, then stop and write an escalation report. No infinite loops.
- **No GPU/cluster access without a written approval token** in your assignment file.

You and Claude Code do not share memory. Write everything another agent needs into a file.
