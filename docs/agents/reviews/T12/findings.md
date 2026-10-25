# T12 — independent review findings, investigated and addressed

| | |
|---|---|
| **Source** | Independent code review supplied by the owner, 2026-10-25 |
| **Investigated by** | Orchestrator (Claude Code), at the owner's direction |
| **Review** | **Waived by the owner** — "I do not require another independent Codex review" |
| **Scope** | Three findings, scoped fixes only. No new features, no architectural change |

Three findings were reported. **Two were confirmed, one of them with a second exploit path
the review did not mention. One was partly disproven** — the mechanism it described is real
and irreducible, but it is not the vulnerability it was read as.

---

## HIGH — Discord audience changes bypass re-consent — **CONFIRMED**

### What the review said

`backend/service.py` compared the current Discord audience *size* against the size approved
at consent, so a room that lost one member and gained another kept its count and never
re-asked.

### Root cause

`DiscordREST.audience()` enumerated guild members, applied channel permission overwrites,
and accumulated the viewer IDs into a set — then returned `len(visible)` and **discarded the
identities**. Everything downstream could therefore only ever compare headcounts. The
comparison in `channel_summary` was also *one-directional* (`audience.size > binding["size"]`)
and the recorded size was only ever raised.

### Exploitable: yes, by two paths

**Path 1 — same-size substitution**, as reported. Two member sets of equal size that differ
by one account produce byte-identical `Audience` values:

```
consented audience : Audience(guild='123', size=4, timezone='UTC')
current audience   : Audience(guild='123', size=4, timezone='UTC')
identical to the backend?  True
```

Member `3` — who was in the audience every participant approved — has been replaced by `77`,
who never was. The summary endpoint serves `77` the coordination summary.

**Path 2 — shrink, then regrow.** Not in the review. Because the stored size was never
lowered, a confirmed binding at size 3 behaved like this:

```
after shrink to 1 : 200
after regrow to 3 : 200
```

Two people leave, two *different* people join, and consent is never re-asked. This is the
same root cause and is closed by the same fix.

### Fix

Consent is now recorded against audience **identity**:

* `backend/channels/discord.py` — `fingerprint(channel, guild, viewers)` returns a SHA-256
  digest over a domain-separated, guild- and channel-scoped, length-prefixed encoding of the
  sorted viewer IDs. `Audience` carries it; `audience()` is the only place the raw IDs exist.
* `backend/service.py` — `bind()` records the digest, `channel_summary()` re-derives and
  compares it on every read, and **any** difference moves the binding to `pending_reconsent`.
  `audience_identity()` refuses an audience with no digest, so an adapter that counts a room
  it cannot identify fails closed rather than degrading to the comparison this replaced.

Design notes, because each was a choice:

* **One-way.** The service must answer *"is this the same audience?"* and must not be able to
  answer *"who is in it?"*. The viewer IDs are consumed inside the adapter and never reach a
  binding, a summary, a response, or a log.
* **Scoped to the channel and guild**, so the same member set in two rooms digests differently
  and a digest recorded for one room means nothing in another.
* **Length-prefixed**, so no two different member sets can concatenate to the same input —
  without it, `{"1", "23"}` and `{"12", "3"}` would digest alike.
* **Shrinkage also re-consents.** Harmless in itself, but path 2 is exactly what a
  one-directional comparison buys.
* **A binding with no recorded digest fails closed**, which is the correct reading of any
  binding written before this change.

### No contract change was needed

`audience_size_at_consent` is still reported and still means what it said: how many accounts
could read the room at consent. The digest is server-side state and is deliberately **not** in
`ChannelBinding`, which is `additionalProperties: false` — so a leak into the binding view
would fail response validation as well as the test that pins it.

Two **description strings** in `contracts/api.openapi.yaml` were corrected, because they
asserted the old behaviour ("if the room has grown", "the channel's membership grew"). No
field, type, enum, or `required` list changed; no example fixture changed; the validator and
every contract test pass unchanged. Leaving them would have left the authoritative document
making a false privacy claim.

---

## MEDIUM — Consent revocation during Discord publishing — **PARTLY DISPROVEN**

### What is real

The window is real and irreducible. Authorization lives in the backend; the post lives in
Discord. Between `channel-summary` answering 200 and Discord accepting the message, a
participant can withdraw consent, and no arrangement of two systems closes that — a
distributed authorization check and an external send cannot be made atomic. This is now
stated in `groupchat/publisher.py` rather than left implicit.

### What it is not

It is not an unauthorized disclosure. Traced end to end:

1. **The check is not racy inside the backend.** `channel_summary` loads the negotiation with
   `SELECT ... FOR UPDATE` inside the request transaction, so a concurrent withdrawal either
   lands first and refuses the read, or waits behind it. There is no interval in which both
   succeed against the same state.
2. **Every post is preceded by its own check.** There is no cached or queued summary;
   `Publisher.update` re-authorizes before every send and never re-sends after a refusal.
3. **What escapes the window is already consented content** — one of the frozen
   `ChannelSummary` templates, over fields the binding had already authorized. The late
   arrival of an authorized sentence discloses nothing new.

So the finding describes a timing limitation, not a privacy failure. It is documented as
such; it is not claimed to be closed.

### The one real gap, and the fix

`update` returning `False` was **advice**. The bot honours it, but nothing enforced it: a
caller that ignored the result — or any future caller — would keep polling a withdrawn
binding and keep it one authorization away from the room.

`Publisher` now latches. After any refusal it is spent: further calls send nothing and
**make no request at all**. A resumption after re-consent is a new `Publisher`, which also
cannot re-send a sentence authorized under the old audience, because `last` starts empty.

`tests/groupchat/test_flow.py` was updated at one call site to match: the flow test reused a
publisher across its first refusal, which the bot never does — its watcher breaks out of the
loop on the first `False`.

---

## MEDIUM — Outdated README — **CONFIRMED**

`README.md` said "Status: orchestration only. No product code exists yet." against the 172
tracked files it was reviewing — a complete backend, a Discord assistant, frozen contracts and
291 tests. Rewritten from what is in the repository, with the verification status stated as it
actually is: no CampusOS process has ever contacted Discord, and T7b remains blocked.

---

## Not in the review: CI had been red on `main`

Found while running the validation the owner asked for. Three workflows had been failing since
2026-10-25 — the same push whose commit message was "green the lint". None of it was a product
defect; all three were configuration left over from before the code landed.

| Workflow | Why it failed | Fix |
|---|---|---|
| Contracts & orchestration | installed only PyYAML. The validator treats a missing dependency as a hard FAIL rather than a silent skip, so it correctly reported that it had checked nothing — and failed | install `jsonschema` and `openapi-spec-validator` too, and run it `--strict` now that contracts exist |
| Integration (mocks) | set `DATABASE_URL`; the app and `alembic/env.py` read `CAMPUSOS_DATABASE_URL`. `KeyError` in the migration step. The driver prefix was also psycopg2's, not psycopg 3's | corrected both names and the prefix; install the dev requirements the privacy suite needs to collect |
| Python | `ruff format --check .` wanted to reformat `docs/agents/reviews/T7c/reproduce.py` — which `pyproject.toml` says must not be reformatted, because it is evidence of what was run | excluded `docs/agents/reviews` from ruff outright instead of only from its lint rules; formatted the four `scripts/ci` and `tests` files that genuinely needed it |

**Every command these workflows run was verified locally**, including `alembic upgrade head`
against a real PostgreSQL 15 with the corrected variable. **The workflow files themselves
were not executed** — that needs a push, and pushing is not authorized. Treat "CI should be
green" as reasoning, not as evidence.

## Reproducing all of this

The pre-fix behaviour is reproducible as mutations, which is how it is kept reproducible:

```sh
PYTHONPATH=. groupchat/.venv/bin/python tests/integration/connector/mutations.py \
    --python "$PWD/groupchat/.venv/bin/python" --only M12   # restores the headcount comparison
```

`M12`–`M16` cover the new guards. All are killed. `M7` **survives and is an equivalent
mutant**, demonstrated rather than assumed — see the note above it in `mutations.py`.

## What this did not fix

* **Nothing here has touched Discord.** `can_view` and the fixtures that pin it were written
  by the same agent; if Discord's real overwrite semantics differ, the code and its tests are
  wrong together. T12 does not change that, and `fingerprint` inherits it exactly —
  a digest over a wrongly computed viewer set is a confidently wrong digest. T7b is still the
  work that would find out.
* **The publish window is not closed**, only bounded and documented.
* **No review.** The owner waived it. This document is the implementer's own account.
