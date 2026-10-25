# Review waiver — T7d

| | |
|---|---|
| **Task ID** | `T7d` |
| **Branch** | `task/T7d-discord-readiness` |
| **Commit waived at** | `fdec5d5` |
| **Date (UTC)** | `2026-10-25` |
| **Waived by** | RishithMody (repository owner) |
| **Status** | `OWNER_AUTHORIZED_REVIEW_WAIVED` |

## This is not a PASS

**No independent review of T7d was ever performed — not even a first attempt.** This is the
weaker of the two waivers in this repository and the one to read carefully, because T7d changes
**production security code**:

- `backend/manage.py` — mints `kind=bot` credentials that did not previously exist.
- `backend/channels/discord.py` — the audience verifier that channel consent is computed from.

Both were written and tested by the same agent (Claude Code), with no independent party
checking either. The project's own rule, CLAUDE.md §6, exists precisely for changes like these.

## Reason given

Development is closing out and the owner is moving to the hackathon demo video. Authorised in
writing on 2026-10-25, in the same instruction that waived T7c.

## Risk accepted

The owner accepts the risk in unreviewed credential-issuance and audience-verification code.

Mitigating evidence, which is **not** a substitute for review: 28 tests, six mutations all
killed, and end-to-end verification against real PostgreSQL, real Redis and a real minted
credential. The two questions a reviewer would most usefully have attacked are recorded in
`docs/agents/handoffs/T7d-1.md` §8 and remain unasked.

## What this does not waive

- The tests. 276 pass, and the output is real.
- **Live Discord verification.** Every Discord behaviour in this task is `httpx.MockTransport`.
  If Discord's real permission semantics differ from `can_view`, the code and its tests are
  wrong together. Nothing in this repository has ever contacted Discord.
