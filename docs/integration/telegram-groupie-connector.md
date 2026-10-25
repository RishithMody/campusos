# Integration assessment — is the Groupie Telegram bot connected to CampusOS?

| | |
|---|---|
| **Verdict** | **NOT CONNECTED** |
| **Status** | Read-only assessment. No code changed, no external service contacted. |
| **Date** | 2026-10-24 |
| **Author** | Orchestrator (Claude Code) |
| **One sub-question** | **UNVERIFIED** — what `@CubbieGroupieBot` actually talks to. See §3. |

---

## 0. Verdict

**NOT CONNECTED**, and not connectable today without a change to a frozen contract.

This is not "we haven't wired it up yet." The CampusOS backend cannot accept a Telegram chat
as a disclosure audience at all: the `platform` field in the frozen API is a closed enum
containing exactly `discord`, and the request object is `additionalProperties: false`. A
Telegram registration is rejected at the schema before any code runs.

Evidence, run just now against the real application:

```
platform="telegram"            -> 400 Invalid request
platform="Telegram"            -> 400 Invalid request
platform="discord"             -> 201 {"channel_id":"chn_…","confirmed":false}
platform="discord" + telegram_chat_id  -> 400 Invalid request
```

The last line matters: there is no smuggling a Telegram id through as an extra field either.

---

## 1. What was inspected

| Question | Method | Result |
|---|---|---|
| Any Telegram code? | `grep -rinE 'telegram\|groupie\|t\.me/\|api\.telegram'` over the working tree | **0 matches** |
| Any in tracked files? | `git grep -inE 'telegram\|groupie'` | **0 matches** |
| Any ever, on any branch? | `git log --all -S'elegram'` | **0 commits** — the string has never existed in this repository |
| Any Telegram dependency? | `backend/requirements*.txt`, `groupchat/requirements*.txt` | None. `discord.py` is the only chat library. |
| Where can the backend send traffic? | `grep -rnoE 'https?://…'` over `backend/` and `groupchat/` | `discord.com/api/v10/` (×2) and `campusos.dev/contracts/v1/` (a `$ref` namespace, never fetched). **No other outbound host exists in production code.** |
| Can a Telegram chat be registered? | Live probe against the app | **400** (above) |

The codebase has exactly one channel-platform seam: `create_app(..., discord=None)` at
`backend/app.py:41`, defaulting to `DiscordREST(config.discord_token)` at `app.py:56`. One
seam, one implementation, one platform.

---

## 2. Does a Telegram integration or adapter exist?

**No.** Not in the working tree, not in any branch, not anywhere in the project's history.

For contrast, the Discord integration is 4 production modules, 9 contract operations, a
database table, a CLI identity ceremony and two test suites. Nothing comparable exists for
Telegram, in whole or in part.

---

## 3. Is `@CubbieGroupieBot` connected to CampusOS?

**From our side: definitively not.** Three independent facts, any one of which is sufficient:

1. **No credential has been issued.** A CampusOS bot caller needs a JWT with `kind=bot` and a
   `guild` claim, signed with our key. No such token has been minted for anyone — in fact
   *nothing in this repository mints one at all*, which is a separate open gap (§8).
2. **No channel has been registered.** The `channels` table is created by migration and
   populated only through `POST /v1/channels`, which has never been called outside tests.
3. **The schema refuses.** Even with a valid credential, `platform: "telegram"` is a 400.

**Whether it uses Groupie's own backend is UNVERIFIED and will stay that way from here.**
I have no access to that bot's source, its hosting, or its configuration, and you asked me not
to connect to external services — which is the right call: messaging a third-party bot to see
what it does is both an outward-facing action and a poor experiment.

What I can say precisely: *if* `@CubbieGroupieBot` is doing anything, it is not doing it through
CampusOS. Any scheduling it appears to perform is its own, backed by its own store, under its
own privacy rules — **not** the consent and disclosure model this project enforces.

That distinction is worth being blunt about before a demo: a Telegram bot that schedules things
is not evidence that CampusOS scheduled them.

---

## 4. What Telegram would actually require

The two API calls are the same two a Discord connector needs — the boundary is platform-neutral
in shape. The work is not in the calls. It is in four couplings underneath them.

### 4.1 The calls, if the blockers below were removed

```http
POST /v1/channels                                   -> {"channel_id": "chn_…"}
Authorization: Bearer <CampusOS bot JWT, kind=bot>
{"platform": "telegram", "platform_chat_id": "-100…", "max_disclosure_level": "free_busy"}

GET  /v1/negotiations/{neg}/channel-summary?channel_id=chn_…   -> ChannelSummary | 403
```

Everything else — creating the negotiation, submitting availability, granting disclosure,
answering approvals — stays human-token-only on the student's own device, exactly as with
Discord. A Telegram bot could not reach those endpoints and should not want to.

### 4.2 Four blockers, in increasing order of difficulty

**B1 — the frozen contract (small, but not mine to change alone).** `platform` is
`enum: [discord]`. Widening it is a contract version bump, which under CLAUDE.md §3 is an
Orchestrator decision with notification to dependents. Mechanically small; procedurally real.

**B2 — `Channel.guild` is NOT NULL** (`backend/db/models.py:61`). Telegram has no guild. A
supergroup id is not an analogue — the Discord model is *guild contains channel*, and Telegram's
is flat. This needs a migration and a decision about what the column means, both T2's.

**B3 — identity binding is Discord-shaped end to end.** `Student.discord_id` is a single
column (`models.py:17`). `Service.link` reads it and asks `self.discord.member(...)`.
`backend/manage.py link-discord` verifies it against Discord's `users/@me`. Supporting a second
platform means a `platform_identities` table, not a second column — otherwise the third platform
repeats the whole exercise.

**B4 — the audience model does not carry over, and this is the real problem.**

Discord consent rests on a number CampusOS computes itself: *how many people can read this
channel*, derived by enumerating guild members and applying channel overwrites. Growth past
that number revokes posting until everyone re-consents.

Telegram does not support that computation:

- `getChatMemberCount` returns a count, not an enumeration, and not who can *read*.
- Administrators are listable; ordinary members of a large group are **not**.
- A **public** group or channel is readable by anyone with the link, including non-members and
  people not logged in. The audience is not merely large — it is **unbounded and unknowable**.

So the question channel consent exists to answer — *who will see this?* — has no reliable answer
on Telegram for exactly the kind of room a study group would use. Options are to restrict
support to private groups where the bot is an admin and the count is meaningful, or to treat the
audience as unbounded and refuse `free_busy` entirely, posting only `none`-level summaries.
**Both are product decisions about weakening or reshaping a privacy guarantee, not engineering
tasks.** This is the finding I would want you to carry into the decision.

---

## 5. Can a Telegram bot credential impersonate a student or approve on their behalf?

**No, and this is already tested** — the protection is platform-agnostic, because it keys on the
credential's `kind`, not on where the caller came from.

`Service.student()` (`backend/service.py:29-35`) raises 403 for **any** `kind=bot` token, and
every human action routes through it. T7c proves this across the whole API surface:

- 16 human-only operations × 2 subjects = **32 parametrized refusals**, all 403.
- One of those subjects is `alice`, a **real provisioned student**, so the refusal cannot be
  explained by a missing database row. It is the credential kind being refused.
- `POST /approvals/{id}` is among them, with a real approval id and a current `state_version`.
- A bot token claiming `kind=human` is also refused — no student row exists for a bot subject.
- Mutation M1 (removing the bot check) kills 8 tests.

A Telegram-issued bot credential would be refused by the same code on the same line. There is
no platform-specific path around it, because identity comes from our JWT and from nothing else
(boundary **B1**, `docs/architecture.md:71`).

**One caveat worth stating:** this holds for credentials *we* issue. It says nothing about what
a third-party bot does with data after we hand it a summary, or about what it tells its own
users. That is a trust question, not an authorization one, and no test of ours can answer it.

---

## 6. How Telegram identities would bind securely

The rule must not change: **the platform identity is verified by the student's own
authenticated ceremony and never asserted by a bot.** Our Discord flow does this correctly —
the operator supplies the student's own OAuth token and the backend asks Discord `users/@me`.

The Telegram analogue is the **Login Widget / `login_url`** flow: Telegram returns a signed
payload whose hash is an HMAC-SHA256 over the sorted field string, keyed by SHA-256 of the bot
token. The backend verifies that signature itself and checks `auth_date` for freshness.

Three properties must survive the port:

1. The payload is verified **server-side, by us**, against a key we hold. A connector forwarding
   "this is user 12345" is worthless, for precisely the reason the Discord contract gives: it
   could bind a student's data to an account they do not control.
2. The binding is to **the authenticated CampusOS subject**, performed by an operator, exactly
   as `link-discord` is today.
3. Membership is re-checked at link time against the actual chat, not trusted from the payload.

Property 3 is where Telegram is weaker: `getChatMember` works, but for a public group
"is a member" does not mean "is the set of people who can read", so the check verifies less than
its Discord counterpart does. Do not port the code and assume the guarantee came with it.

---

## 7. Minimal smoke-test plan

Offline first, in the order below. T1–T5 need no Telegram account and would run today if the
blockers in §4.2 were resolved; they are the Telegram analogue of C1–C9, which already exist.

| # | Stage | Check | Expected |
|---|---|---|---|
| T1 | Contract | Register a Telegram chat | Until B1 is decided: **400**. This is the current correct behaviour and should be pinned as a test *now*, so widening the enum is a deliberate act that breaks a test. |
| T2 | Credential | Telegram bot token on every human-only operation, including as a real student's subject | 403 each — reuse T7c's builder table verbatim |
| T3 | Bot → backend | Slash/command handler registers the chat | `chn_` returned, reply **private to the invoker**, no public message |
| T4 | Backend → negotiation | Student creates a negotiation from their **own** client | 201; the bot is not involved and cannot see it |
| T5 | Consent | Participant requests a binding; all approve | Summary readable by the bot only after the last approval; **403 before**, byte-identical to every other denial |
| T6 | Safe response | Bot posts | Exactly one of the nine frozen sentences; conformance corpus in `tests/integration/connector/conformance.json` |
| T7 | Withdrawal | One participant withdraws | Posting stops within one poll; **nothing is said in the chat about why** |
| T8 | Audience | Chat made public, or a member added | §4.2 B4 — **this is the test that will fail**, and the one to run before believing any of the others |
| T9 | Negative | Bot asserts a Telegram user id maps to a student | Rejected; no endpoint accepts it |

T8 is the gate. If the audience number cannot be computed, T5 and T7 are enforcing consent
against a figure nobody can justify, and passing them would be misleading.

---

## 8. What is still needed

**From your friend:**

1. The connector's **repository or API documentation** — nothing can be designed against a bot
   whose interface is unknown.
2. **Is `@CubbieGroupieBot` one bot or a family?** And does it already have its own backend and
   data store? If it does, what does it currently keep about students?
3. **Who operates it**, where it runs, and what it logs.
4. **A private test group** where the bot is an administrator — not a public channel, for §4.2 B4.
5. Whether it can hold an **outbound bearer credential** and keep it out of logs.

**From you:**

6. **Is Telegram meant to replace Discord, or sit beside it?** This is the decisive question.
   Track 3's deliverable is a Discord assistant: T9 is implemented, reviewed and merged, and
   T7b is one bot token away from live verification. Telegram needs a contract change, a
   migration, a new identity ceremony, and an unresolved audience model. **Beside** is a second
   platform with the same privacy guarantees to re-establish; **instead** discards finished,
   reviewed work close to the deadline.
7. A decision on **B1**, which only you and I can make, and which should not be made before B4
   has an answer.

**Still missing internally, and blocking either way:** nothing in this repository issues a
`kind=bot` JWT. `manage.py` supports `provision` and `link-discord` only. The READMEs say
"operator-issued out of band", which today means by hand. Flagged in the Discord assessment,
still true, and blocks T7b as well as anything Telegram.

---

## 9. Summary

| Question | Answer |
|---|---|
| Telegram integration exists? | **NOT CONNECTED** — zero references in the entire history |
| `@CubbieGroupieBot` connected to CampusOS? | **NOT CONNECTED** from our side; what it *is* connected to is **UNVERIFIED** |
| Could a Telegram bot impersonate or approve? | **No** — already tested, platform-agnostic, 32 refusals |
| What would it take? | A frozen-contract change, a migration, a new identity ceremony, and an **unresolved audience model** |
| Biggest risk | Not plumbing. Telegram public rooms have an unbounded, unknowable audience, which is the number channel consent is built on. |
