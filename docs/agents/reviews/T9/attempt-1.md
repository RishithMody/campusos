# Review — T9, attempt 1 of 3

| | |
|---|---|
| **Task ID** | `T9` — Discord group chat assistant |
| **Branch** | `task/T9-groupchat` |
| **Reviewed HEAD** | `5f17cda` |
| **Reviewer** | Claude Code (Orchestrator session) |
| **Date (UTC)** | 2026-10-24 |
| **Verdict** | **PASS** — with one live-acceptance gap carried, not waived |

## On independence

Codex implemented T9; this review is Claude Code, satisfying CLAUDE.md §6. Same two caveats
as the T2 review: this reviewer wrote the contracts T9 renders against, and CLAUDE.md §9
forbids child agents so it ran in the Orchestrator session rather than a cold one. Everything
below was executed.

## Verified claims

```text
$ groupchat/.venv/bin/python -m pytest tests/groupchat/ -q     32 passed
$ groupchat/.venv/bin/ruff check groupchat tests/groupchat     All checks passed!
$ groupchat/.venv/bin/ruff format --check …                    10 files already formatted
$ groupchat/.venv/bin/mypy groupchat                           no issues, 6 source files
$ ./scripts/ci/secret_scan.sh --tracked                        secret-scan: clean
```

Repo contract validation, the disclosure matrix and the tooling suite all pass from this
branch. No protected file, no `contracts/` file, nothing outside `groupchat/`,
`tests/groupchat/`, its handoff and its own assignment status line.

**The tests have teeth**, checked by mutation rather than by reading:

| Mutation | Result |
|---|---|
| `render()` stops validating against the frozen `ChannelSummary` | **8 tests fail** |
| `Publisher.update()` keeps watching after an `APIError` denial | **10 tests fail** |

## Focus areas

**Absence of sensitive data in channel messages.** This is the one that matters, so it got an
independent probe rather than a reading. 792 hostile payloads were pushed through `render()` —
every template against every status, with `therapy`, a clinician name, an email, `@here`,
`<@everyone>`, format-string injection (`{0.__class__}`) and an RTL override smuggled into
extra fields and the timezone. **All 792 were refused.** The 8 that rendered were the
legitimate templates. The complete set of sentences this bot can ever post:

```
Collecting availability from 3 people.
There's a time on the table -- round 2 of 8.
Waiting on everyone to confirm.
Locked in: 2026-10-28 11:00 MST – 2026-10-28 12:00 MST.
No time works for everyone in this window.
No time found in 8 rounds -- over to you.
This one timed out.
Someone withdrew, so this is off.
```

Integers and one formatted timestamp are the only variable content. `allowed_mentions` is set
to `none()` at both client construction and every `send`, so no payload can ping a room.

**Discord permissions.** The bot is guild-locked and text-channel-only; `room()` returns
`None` otherwise. `/schedule` registers **the actual invoking channel's id**, so a caller
cannot register a channel they are not in. Replies are ephemeral. Permission computation
itself is T2's and was reviewed there.

**Student identity binding.** `POST channels/{id}/members` is in the student CLI only, behind
a human token. The bot has no human credential and no path to assert a mapping — the property
the whole consent chain rests on. `/schedule` explicitly tells students that no credentials or
availability belong in the chat.

**Private approvals.** Decisions happen in the terminal, showing the current disclosure
preview, the proposed slot and the version, then requiring the student to type `approve` or
`decline` — anything else cancels. Stale versions are not retried.

**Consent withdrawal.** `test_consent_denial_posts_nothing` is parameterised over `decline`,
`withdraw` and `growth`; pending is covered by the summary 403 path. `consent_withdrawn`
exists in the template map but is deliberately **unreachable** (absent from `STATUS`), because
withdrawal must be indistinguishable from any other denial. Correct, and better than the
contract asked for.

**Fail-closed behaviour.** `Publisher.update()` returns `False` on any `APIError` or malformed
payload and logs without the exception detail, so an API error body cannot reach a log. It
catches `KeyError` too, which matters: `ZoneInfo` raises a `KeyError` subclass, so a bad
timezone stops the watcher rather than escaping as an unhandled error.

**Transport hardening**, unprompted and worth noting: HTTPS/443 only with HTTP on loopback,
credentials refused in the URL, `follow_redirects=False` with a test that credentials are not
forwarded on redirect, and `trust_env=False` so a proxy environment variable cannot intercept.

## Findings

| # | Severity | Finding |
|---|---|---|
| N1 | nit | `consent_withdrawn` is in `TEMPLATES` but unreachable via `STATUS`. Deliberate and defensive, but it reads as dead code; a one-line comment already explains it. Same contract enum value flagged as N1 in the T2 review — remove from the contract at the next version bump |

No `critical`, `major` or `minor` findings.

## The gap this PASS does not close

**No real Discord account, server or channel was contacted.** Gateway connection, slash
command registration against live Discord, the Guild Members intent, permission bits and rate
limits are all unexercised. T9 says so plainly and does not claim otherwise.

That is a *live-acceptance* gap, not a defect, and it is T7's to close. The checklist is in
`groupchat/README.md`. **Track 3 must not be described as live-verified until it runs.**

## Verdict

**PASS.** Criteria met within what can be verified offline, tests assert what they claim,
nothing above a nit. **Recommend merge**, with the live Discord check carried to T7. The
reviewer does not merge.
