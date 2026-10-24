# CampusOS backend (T2)

FastAPI exposes the frozen API at `/v1`. All routes, including `/v1/health`, require
JWT bearer authentication. Swagger and unversioned routes are not public surfaces.

## Local setup

From the repository root (Python 3.11+):

```sh
uv venv --python 3.11 backend/.venv
uv pip install --python backend/.venv/bin/python -r backend/requirements-dev.txt
# Set the variables documented in backend/.env.example in your environment.
backend/.venv/bin/alembic -c backend/alembic.ini upgrade head
backend/.venv/bin/uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8000
```

PostgreSQL and Redis must be running. `CAMPUSOS_INFERENCE_MODE=mock` is explicit;
missing or invalid selection fails startup. No GPU is needed. Live inference uses
an injected adapter with a private `/v1` base URL, API key, and model name supplied
by T3. No cluster connection was used to implement or verify this backend.

The external HTTPS/443 gateway and Redis/PostgreSQL service deployment belong to
infra/integration. A Cubbie script reaches this API through that gateway; it never
calls inference or Cubbie's abilities directly. Nothing is sent through Cubbie to
another student.

## Identity bootstrap

The trusted identity issuer is outside the frozen REST surface. Provision its
subjects locally with `python -m backend.manage provision <issuer-subject>`.
JWTs are HS256 with the environment signing key (at least 32 characters), issuer
`campusos`, audience `campusos-api`, and required `sub`, `kind`, `iat`, `exp` claims.
Kinds are `human`, `agent`, `bot`. Agent tokens additionally bind `agent_id` to the
provisioned student's agent. Bot tokens bind `guild` to one Discord guild. Never
put the signing key in a client or issue human tokens to agents/bots.

Discord identities are linked by a trusted operator after the student's OAuth
ceremony: set that student's OAuth access token in
`CAMPUSOS_DISCORD_OAUTH_ACCESS_TOKEN`, then run
`python -m backend.manage link-discord <issuer-subject>`. The command verifies the
identity with Discord's `/users/@me` rather than accepting a claimed Discord ID.
The operator is responsible for binding the ceremony to the authenticated CampusOS
subject. An internet-facing login/OAuth callback is not part of this contract.

## Three-student flow

1. Each student gets their contact handle from `GET /v1/me`.
2. A human creates a negotiation with the other handles. Each participant reads
   their own state to obtain their negotiation-local `student_ref`.
3. Each human creates explicit, expiring grants to the other participants' agents.
   Invitation alone grants no calendar access. Grant expiry cannot exceed the
   negotiation window. Accounts start with a `free_busy` ceiling.
4. Each participant PUTs availability. The service requires the envelope to match
   the negotiation window and **explicit free slots**; an omitted interval is not
   treated as permission to schedule. Busy/tentative intervals override free ones.
5. Once every availability and mutual grant exists, LangGraph proposes bounded
   candidates at interval boundaries. The model sees filtered envelopes, never
   titles, labels, locations, private notes, or raw user chat. Failure/no overlap
   is a normal terminal `failed` outcome with human escalation.
6. Each human reads their own approval preview and posts its current state version
   to `/approvals/{id}`. Every mutation advances the version; a stale decision is
   rejected with 409. Re-read and ask again. Partial approval remains representable.
7. Only unanimous human confirmation creates durable local commitment rows.
   **No Google Calendar write or external message is performed by this service.**

The chat stream offers coordination guidance and negotiation status through the
inference interface using a closed intent and structured context. It does not
forward arbitrary user text or raw calendar details to a model. Asking why also
returns the caller’s own private notes directly, without putting them in a prompt.
Private message notes never appear in shared transcripts.

## Privacy, persistence, and concurrency

- `privacy/service.py` applies outbound disclosure filtering. Inbound over-disclosure
  is rejected (422), malformed messages are 400, authority violations are 403.
- All cross-student payload reads require live scoped grant rows and append audit
  records. Raw calendar rows have an owner-only service function.
- PostgreSQL holds durable student, negotiation, grant, commitment, approval,
  channel, and audit records. Negotiations use row locks plus optimistic versions.
  A per-worker async gate prevents blocking the event loop on its own synchronous
  database transaction while inference is awaited; separate workers coordinate
  through PostgreSQL. This favors correctness over throughput for the demo.
- Redis contains only negotiation IDs and versions with TTL, and pub/sub version
  notifications. SSE reads fresh, filtered PostgreSQL state and checks grant
  revocation/expiry and token expiry each iteration. Revocation sends a terminal
  error; the connection cannot keep receiving under its old authority.
- Redis is checked before mutation. A publish failure after a database commit
  returns 503; clients must re-read before retrying. Streams also poll durable state
  so a lost notification cannot permanently hide a committed state change.
- Default logs contain no prompt/completion or calendar content. External LangSmith
  tracing is refused at environment startup.

## Discord consent

Register with the guild-bound bot token; link members with their human tokens;
request a negotiation/channel binding; every participant confirms via the ordinary
approval endpoint. The backend checks Discord permissions and paginates guild
members to count the actual text-channel audience, requiring Guild Members intent.
Unsupported thread/DM channels fail closed. Audience growth requires re-consent;
one withdrawal ends posting. Substitution at the same audience size remains the
explicit frozen-contract limitation.

`channels/summary.py` has no inference dependency. It emits only the contract's
closed template IDs, integers, opaque negotiation ID, timestamps and timezone.
It never emits a name, private reason, availability enumeration or model prose.
Pending, declined and withdrawn bindings give the bot the same 403 body.

## Verification

```sh
backend/.venv/bin/python -m pytest tests/backend/ -q
backend/.venv/bin/ruff check backend tests/backend
backend/.venv/bin/ruff format --check backend tests/backend
backend/.venv/bin/mypy backend
```

For the real PostgreSQL migration/persistence/concurrency test, set
`CAMPUSOS_TEST_POSTGRES_URL` to a **disposable local test cluster** whose user may
create databases. The test creates and drops its own random database. Without
this variable it explicitly skips; SQLite tests are not claimed as PostgreSQL
migration evidence. Redis tests use fakeredis, Discord/vLLM use injected fakes or
HTTP mock transports; no live Discord account or GPU is needed by CI.

`python -m backend.protocol.generate` regenerates the committed Pydantic DTOs from
local frozen schemas, with HTTP references inlined locally. DTO generation excludes
conditional `allOf` constraints because those are not faithfully represented by
Pydantic generation. Runtime validation always checks the **complete original JSON
Schema, including every conditional**, before checking DTO shape. The frozen
positive/negative fixtures are exercised by the backend tests.
