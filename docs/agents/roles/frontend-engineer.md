# Agent 5 — Frontend Engineer

| | |
|---|---|
| **CLI** | Codex (`codex`) |
| **Owns** | `frontend/`, `tests/frontend/` |
| **Primary task** | T5 |
| **Reviewed by** | Claude Code (cross-tool review) |
| **Launch** | `./scripts/agents.sh start frontend` |

Shared rules: `CLAUDE.md`. This file covers only what is specific to this role.

## Scope

- **Next.js dashboard.** A student's home view: upcoming commitments, pending negotiations,
  items awaiting their approval, and what their agent has disclosed on their behalf. The last
  one matters — students must be able to see what was shared about them.
- **Student chat interface.** The student talks to *their own* agent in natural language
  ("find 90 minutes for the group project this week"). Stream responses.
- **Live negotiation visualization.** The differentiating screen. Show multiple agents
  negotiating in real time: who proposed what, which constraints collided, what each agent
  disclosed, and how consensus formed. Render the LangGraph negotiation state from the backend;
  do not invent a parallel state model in the client.
- **Approval and conflict resolution UI.** When agents cannot converge, or a commitment needs
  human sign-off, the student decides here — with enough context to decide well, and a clear
  record of what their agent will reveal if they accept.

## Hard limits

- **T5 starts only when `contracts/` is stable.** Generate TypeScript types from the schemas in
  `contracts/`; never hand-write a duplicate of a backend type that will silently drift.
- `contracts/` is **read-only** for you. Need a change? Write it in your handoff and stop.
- Do not touch `backend/`, `ml/`, or `infra/`. If an endpoint is missing, mock it behind a
  typed client and record the gap in your handoff.
- **Never display more private data than the disclosure level permits.** The UI is the last
  place privacy can leak. If the API hands you a field, that is not permission to render it —
  check the disclosure level.
- No secrets in client code. Anything in `NEXT_PUBLIC_*` is public; treat it as such.

## Required tests

- `npx tsc --noEmit` clean, `eslint` clean
- Component tests for the negotiation timeline and the approval flow
- A test asserting the UI does not render fields above the permitted disclosure level
- The app builds and runs against the mock API with the backend absent
