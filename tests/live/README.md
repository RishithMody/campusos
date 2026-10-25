# T7a local integration verification

No GPU and no live Discord. Inference and Discord are injected fakes; PostgreSQL
and Redis are real. Use disposable, loopback-only services, never a shared database.

From the repository root:

```sh
uv venv --python 3.11 tests/live/.venv
uv pip install --python tests/live/.venv/bin/python -r groupchat/requirements-dev.txt
docker compose up -d --wait
export CAMPUSOS_LIVE=1
export CAMPUSOS_TEST_POSTGRES_URL=postgresql+psycopg://campusos@127.0.0.1:55439/postgres
export CAMPUSOS_TEST_REDIS_URL=redis://127.0.0.1:56389/0
# These MUST be separate pytest processes: the legacy suites import bare conftest.
tests/live/.venv/bin/python -m pytest -p tests.live.plugin tests/backend/ -q -rA
tests/live/.venv/bin/python -m pytest -p tests.live.plugin tests/groupchat/ -q -rA
CAMPUSOS_LIVE_DESTRUCTIVE=1 tests/live/.venv/bin/python -m pytest tests/live/ -q -rA
```

Run suites sequentially. The last command stops/restarts both services. It must not
run alongside another suite or app. `docker compose down -v` removes the disposable
stack afterward. Compose is only the PostgreSQL/Redis dependency stack, not an
application/frontend deployment. Local trust authentication is restricted to the
loopback port binding; do not expose this configuration on a network host.

Without `CAMPUSOS_LIVE=1`, tests/live visibly skips and does not contact services.
Explicit opt-in with missing URLs fails; unavailable services fail, never silently
pass. Destructive tests require the second opt-in and exactly the dedicated ports.
The plugin is opt-in and does not alter the original suite's default behavior.
No shared CI files are changed. CI can run the existing mock suites and collect
these live tests as visible skips.

## Why a separate fixture

The existing fixtures share a fake Redis client between TestClient's portal and
pytest-asyncio. A real pool cannot cross those loops. `LoopSafeRedis` opens and
closes real clients on the calling loop, keeping each pipeline or pub/sub client
alive for its context. It does not simulate responses or bypass the production
Ephemeral implementation. An additional test uses an ordinary pooled async Redis
client on one loop to check actual publish/subscribe and TTL behavior.

Every env fixture gets a randomly named PostgreSQL database and drops only that
database afterward. Both test and administrative pools use pre-ping to recover
from server restart. Fixture finalization is registered before setup continues.
Most suite fixtures create model metadata, as their original fixtures did; the
existing PostgreSQL test separately runs real Alembic upgrade/downgrade/re-upgrade
and 12 concurrent locked updates. Discord consent tests remain mocked Discord
checks even when all their durable state is stored in PostgreSQL.

## Native fallback used for this verification

Docker's daemon was unavailable on the verification host. PostgreSQL 15.19 and
Redis 8.10.2 were run as isolated native processes instead:

```sh
initdb -D /private/tmp/campusos-t7a-pg -A trust --no-locale -E UTF8
pg_ctl -D /private/tmp/campusos-t7a-pg -l /private/tmp/campusos-t7a-pg.log \
  -o '-h 127.0.0.1 -p 55439 -k /private/tmp' start
redis-server --bind 127.0.0.1 --port 56389 --save '' --appendonly no \
  --daemonize yes --pidfile /private/tmp/campusos-t7a-redis.pid \
  --logfile /private/tmp/campusos-t7a-redis.log
```

Use `postgresql+psycopg://127.0.0.1:55439/postgres` (current OS user), and set
`CAMPUSOS_LIVE_NATIVE=1` for the destructive tests. Native service control uses only
the fixed T7a data directory and ports. Stop with `pg_ctl -D
/private/tmp/campusos-t7a-pg stop` and `redis-cli -p 56389 shutdown nosave`.
Do not reinitialize an existing cluster. Use an existing compatible environment
via its Python path if desired; this run used the T9 worktree's environment.

## What this does not prove

No Discord connection, command registration, live permissions/intents, real
rate-limit behavior, or channel transcript. Those require owner approval and
credentials. No GPU, browser UI, or live vLLM verification. Inference failures are
injected at its supported interface. A trusted issuer's signed `kind=human`
assertion is still the human-consent boundary; this harness issues synthetic test
tokens and cannot establish a real human ceremony.

Redis stream recovery means the old stream emits a terminal 503 error and a fresh
subscription reads durable state after restart; it does not mean the old stream
resumes. Redis eviction pressure is not measured by these tests.
