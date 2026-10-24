# Agent 2 — Backend Engineer

| | |
|---|---|
| **CLI** | Codex (`codex`) |
| **Owns** | `backend/`, `tests/backend/` |
| **Primary task** | T2 |
| **Reviewed by** | Claude Code (cross-tool review) |
| **Launch** | `./scripts/agents.sh start backend` |

Shared rules: `CLAUDE.md`. This file covers only what is specific to this role.

## Scope

- **FastAPI backend.** Routes, dependency-injected auth, Pydantic request/response models
  generated from `contracts/`, structured error responses, health endpoints.
- **Agent-to-agent communication protocol.** Implement the message envelope defined in
  `contracts/agent-protocol.schema.json`: identity, scope of authority, disclosure level,
  negotiation intent, signature/trace fields. This is the heart of the product — a student's
  agent speaks for them, so every message must be attributable and scope-limited.
- **LangGraph negotiation workflows.** Model negotiation as an explicit state graph: propose →
  counter → concede → converge → require-human-approval. Make state inspectable and
  serializable; the frontend has to visualize it and QA has to assert on it.
- **PostgreSQL + Redis.** SQLAlchemy models + Alembic migrations for durable state (students,
  calendars, grants, negotiation transcripts). Redis for ephemeral negotiation sessions,
  locks, and pub/sub to the frontend.
- **Authorization.** Every endpoint authenticated. Never trust a client-supplied user ID —
  derive identity from the validated token. Cross-student data access requires an explicit,
  logged, scoped grant row.

## Hard limits

- `contracts/` is **read-only** for you. Need a change? Write it in your handoff, set your task
  to `REVIEW`, and stop. Do not edit a published schema.
- Do not touch `frontend/`, `ml/`, or `infra/`.
- Model inference is behind an interface. Depend on an injectable client with a working mock —
  **never** call the H200 cluster, and never hardcode an inference URL. Phase 1 must run fully
  on mocks so the demo is not hostage to the GPU.
- No secrets in code. Config from environment variables with a committed `.env.example`.

## Required tests

- `pytest tests/backend/` — unit tests for protocol validation, authorization, and each
  negotiation state transition
- An authorization test proving student A's agent **cannot** read student B's calendar
- A privacy test proving a negotiation message carries only minimum disclosure
  (e.g. "busy 2–4pm", never the underlying event detail)
- Contract tests asserting responses validate against `contracts/`
