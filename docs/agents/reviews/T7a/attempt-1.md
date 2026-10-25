# Review — T7a, attempt 1 of 3

| | |
|---|---|
| **Task ID** | `T7a` — Live verification: real PostgreSQL, Redis (Discord still pending) |
| **Branch** | `task/T7a-live-verify` |
| **Reviewed HEAD** | `f33504e` |
| **Reviewer** | Claude Code (Orchestrator session) |
| **Date (UTC)** | 2026-10-24 |
| **Verdict** | **PASS** — Docker startup unverified, live Discord not attempted |

## On independence

Codex implemented T7a; this review is Claude Code, satisfying CLAUDE.md §6. Same two caveats
as the T2 and T9 reviews: the reviewer wrote the contracts under test, and §9 forbids child
agents so this ran in the Orchestrator session. Every number below was re-derived by running
the suites on services this reviewer started.

## The three reported counts, re-run

Against a PostgreSQL 17 cluster and Redis 8.10.2 started for this review:

| Suite | Reported | Observed |
|---|---|---|
| `tests/backend/` | 88 | **88 passed** |
| `tests/groupchat/` | 32 | **32 passed** |
| `tests/live/` | 7 | **7 passed** |

The 7 needs `CAMPUSOS_LIVE_DESTRUCTIVE=1` and `CAMPUSOS_LIVE_NATIVE=1` in addition to the
three variables the handoff's command block shows. With only the documented three it is
**5 passed, 2 skipped**, with the skip reason printed. The claim is true; the quoted command
does not reproduce it. See F1.

Notably, 88 includes `test_actual_stream_closes_on_grant_revocation`, which failed against
real Redis before this task. `LoopSafeRedis` fixes it honestly — a fresh connection per call,
scoped to the calling loop — rather than by reaching for a mock.

## Does it actually use real services, or silently fall back?

This was the question worth answering, so it got experiments rather than a reading.

| Experiment | Result |
|---|---|
| `CAMPUSOS_LIVE=1`, URLs unset | **`INTERNALERROR … Live opt-in requires both …`, no tests ran** |
| `CAMPUSOS_LIVE=1`, URLs set, **services down** | **1 failed, 39 errors** — no fallback |
| Live run vs mock run | **127 passed / 0 skipped** vs **119 passed / 8 skipped** |
| PostgreSQL during a run | a `t7a_*` database observed present 17 times, created and dropped per test |
| PostgreSQL after a run | **0** leftover databases |
| Redis during a run | **817 commands processed** |

**A mock run cannot reach 127 passed**, and the skip count is the tell. Combined with the
`pytest.fail` on missing URLs and the loopback-only guard in `service_urls()`, there is no
path by which a mock run is mistaken for a live one.

One thing to keep in mind rather than fix: with services **down**, 48 tests still pass —
those are the ones that never touch a service. "Some passes" is not "live verified"; the
number to look for is 127 with no skips.

## Harness, fixtures, resilience, Compose

**Harness.** `pytest_collection_modifyitems` swaps the `env` fixture only when
`CAMPUSOS_LIVE=1`, leaving both owning suites untouched — the right call, since
`tests/backend/` and `tests/groupchat/` are not T7a's files. `isolated_database()` creates a
randomly named database per engine and drops it in a finalizer, which is what in-memory
SQLite gives and what a shared database would not.

**Resilience tests are real.** A backend PID is terminated mid-transaction and the commit is
asserted to raise; PostgreSQL is genuinely stopped and restarted and the negotiation survives
byte-identical; Redis is shut down under a live SSE stream and the stream terminates then
reconnects. The pub/sub test uses an ordinary pool on one loop "as production does",
asserting the published value, the session key, the TTL bounds and actual expiry after 1.1s.

**`test_human_consent_boundary_is_the_trusted_issuer_claim` documents the gap instead of
hiding it.** An agent token gets 403; a human-kind token from the trusted issuer gets 200
*with no human ceremony anywhere*, and the test says so in a comment. That is the right way
to handle a known limitation — pinned as an executable fact rather than described in prose
nobody re-reads. It was carried from the T2 review and has now been closed as far as it can
be without a real issuer.

**Compose.** `docker compose config --quiet` exits 0 without a daemon. Both services bind
`127.0.0.1` only, have healthchecks, declare **no volumes** so nothing persists on the host,
and expose exactly the ports the tests expect. `docker info` fails with
`dial unix /var/run/docker.sock: connect: no such file or directory` — the daemon is
genuinely unavailable, as the handoff states.

## Boundaries

No production code, no frozen contract, no protected file. The diff is `tests/live/`,
`docker-compose.yml` and the handoff — exactly T7a's ownership. `ruff check` and
`ruff format --check` clean on `tests/live/`. Repo contract validation, disclosure matrix,
tooling suite and secret scan all pass from this branch.

## Findings

| # | Severity | Finding |
|---|---|---|
| F1 | minor | The handoff's command block shows three environment variables, but the 7-pass result needs `CAMPUSOS_LIVE_DESTRUCTIVE=1` and `CAMPUSOS_LIVE_NATIVE=1` as well. Someone reproducing it from the handoff gets 5 passed / 2 skipped and reasonably concludes the claim was inflated. It was not — the variables are documented in `tests/live/README.md`, just not in the block that looks copy-pasteable. Add them there |
| N1 | nit | The destructive tests hardcode `/private/tmp/campusos-t7a-pg` and ports 55439/56389. Correct for a disposable local cluster and asserted loopback-only, but it means the data directory is a second, undocumented precondition |

Neither blocks the merge.

## What this PASS does **not** cover

- **Docker container startup is unverified.** Config validates; nothing was ever started. The
  native services prove the code works against real PostgreSQL and Redis — they do not prove
  the Compose file brings those services up.
- **Live Discord was not attempted and is not claimed.** `FakeDiscord` is still in the
  fixture. No account, server, channel, gateway connection, intent or permission bit has been
  exercised against real Discord. That remains entirely open.

## Verdict

**PASS.** Counts verified, fallback ruled out experimentally, boundaries clean, nothing above
a minor. **Recommend merge**, with Docker startup and live Discord carried forward explicitly.
The reviewer does not merge.
