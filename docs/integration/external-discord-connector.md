# Integration assessment — reusing an external Discord connector

| | |
|---|---|
| **Status** | Assessment only. No production code changed. |
| **Date** | 2026-10-24 |
| **Author** | Orchestrator (Claude Code) |
| **Blocked on** | The connector's repository or API documentation, and the owner's go-ahead to connect |
| **Affects** | T7b (live Discord verification), `groupchat/` (possibly retired), nothing in `backend/` |

---

## 0. The headline

**No backend adapter is required, and none should be written.**

CampusOS already treats a Discord bot as an untrusted client. `docs/architecture.md:71`
(boundary **B1**) says so explicitly — *"every surface above the line is untrusted, including
our own frontend and our own Discord bot"* — and `backend/service.py` enforces it. The
consequence is that the interface an external connector needs **is already the frozen REST
API**, and it is extremely small:

> A Discord connector needs exactly **two** CampusOS endpoints, **one** credential, and a
> **nine-row rendering table**. Nothing else.

`groupchat/` is not a privileged component. It is a reference implementation of that same
small client contract, in 4 files and ~300 lines. Your friend's connector can replace it
outright without the backend knowing or caring, provided it honours the same three things.

What this means for requirement 4 (*"do not create a second Discord bot or duplicate the
scheduling backend"*): the scheduling backend cannot be duplicated, because the connector has
no access to any of it. The second-bot question is real and is **§6 — the one genuine blocker**.

---

## 1. What was inspected

| Area | Files | Finding |
|---|---|---|
| Discord adapter | `backend/channels/discord.py` (118 lines) | `Discord` is a two-method `Protocol`: `audience()`, `member()`. `DiscordREST` implements it against `discord.com/api/v10`. Fails closed on non-text channels, incomplete pagination, missing intent. |
| Channel vocabulary | `backend/channels/summary.py` (41 lines) | Closed status→template map. No inference import, enforced by the module docstring and by review. Validates its own output against the frozen `ChannelSummary` before returning. 403 on any unmapped status. |
| Routing | `backend/app.py:213-391` | Routes are **generated from `contracts/api.openapi.yaml`**, not hand-declared. Request and response bodies are schema-validated in both directions. An endpoint that is not in the contract does not exist. |
| Authorization | `backend/auth.py` (44 lines), `backend/service.py:29-35, 539-655` | Identity comes from the JWT and nothing else. `kind ∈ {human, agent, bot}`. `Service.student()` **raises 403 for any bot token**, so a bot can never act as a student. |
| Identity binding | `backend/manage.py` | Discord IDs are bound by operator-run OAuth verification against `users/@me`. Never asserted by a bot. |
| Reference client | `groupchat/{api,bot,publisher,render}.py` | The full client contract, already written once. |
| Frozen contract | `contracts/api.openapi.yaml` | 19 operations. Channel consent is 4 of them. |
| Live verification | `docs/task-graph.md:620-686` | T7b, `BLOCKED` on token + go-ahead. |

---

## 2. Minimum interface for an external connector

### 2.1 The complete bot-callable surface

Of the 19 operations in the frozen contract, a bot credential can reach exactly **three**,
and only two of them carry any data about a negotiation. **Verified empirically**, not by
reading — every operation was probed with a `kind=bot` token against the real app (see
§2.4):

| # | Call | Purpose | Returns |
|---|---|---|---|
| 1 | `POST /v1/channels` | Register a room as a disclosure audience | `{channel_id: "chn_…", confirmed: false}` |
| 2 | `GET /v1/negotiations/{negotiation_id}/channel-summary?channel_id=chn_…` | The only thing it may post | `ChannelSummary` |
| — | `GET /v1/health` | Liveness. Authenticated, but returns `{"status":"ok","version":"1.0.0"}` and touches no student data. | fixed literal |

That is the entire interface. All 16 remaining operations return **403** to a bot token. There
is no third endpoint to add.

**1 — `POST /v1/channels`**

```http
POST /v1/channels
Authorization: Bearer <CampusOS bot JWT>
Content-Type: application/json

{"platform": "discord",
 "platform_channel_id": "<Discord snowflake, string>",
 "max_disclosure_level": "free_busy"}
```

`max_disclosure_level` is capped at `none | free_busy` **by the schema**, not by convention —
`category` and `full` describe *why* a student is busy, and a room is the wrong audience for
that at any consent level a bot could collect. The backend independently calls Discord to
confirm the bot can actually view that channel (`service.py:542`); a connector cannot register
a room it is not in, or a room in another guild. Idempotent per `platform_channel_id`, but see
the subject-stability warning in §6.3.

**2 — `GET /v1/negotiations/{id}/channel-summary`**

Authorized only when `kind == "bot"` **and** `channel.bot == token.sub` **and**
`channel.guild == token.guild` **and** the binding status is exactly `confirmed`
(`service.py:628-640`). Everything else — never requested, `pending_consent`, `declined`,
`withdrawn`, `pending_reconsent` — returns an **identical 403 with an identical body**. The
connector must not try to distinguish them: a bot that could tell `declined` from `pending`
could report a private no into the room.

The correct response to 403 is **to say nothing and stop polling.**

### 2.2 Evidence for the claim above

Asserting "only two endpoints" from reading the code would not be good enough, so every
operation in the frozen contract was called with a `kind=bot` credential against the real
application (SQLite, injected fakes, no network):

```
GET    /health                                          200  <- reachable, no student data
GET    /me                                              403
POST   /me                                              403
POST   /me/chat                                         403
PUT    /me/availability                                 403
GET    /negotiations                                    403
POST   /negotiations                                    403
GET    /negotiations/{negotiation_id}                   403
POST   /negotiations/{negotiation_id}/messages          403   (via load() -> student())
GET    /negotiations/{negotiation_id}/stream            403
POST   /approvals/{approval_id}                         403
POST   /channels                                        201  <- reachable
POST   /channels/{channel_id}/members                   403
POST   /negotiations/{id}/channel-bindings              403
GET    /negotiations/{id}/channel-bindings              403
DELETE /negotiations/{id}/channel-bindings/{channel_id} 403
GET    /negotiations/{id}/channel-summary               403  <- 200 only with a confirmed binding
POST   /grants                                          403
DELETE /grants/{grant_id}                               403
```

Method note: a first pass returned **400** rather than 403 for five operations, because body
and parameter validation runs *before* authorization in `app.py`. Those were re-probed with
valid bodies and real identifiers from a live negotiation, and all five returned 403. Reporting
the first pass as proof would have been wrong — a 400 says the request was malformed, not that
the caller was refused. `POST .../messages` is the one case established by code path rather
than a crafted envelope: it calls `load()` → `student()`, the same path the probe already drove
to 403 through `GET /negotiations/{id}`.

The probe script is at
`/private/tmp/claude-502/-Users-rishithmody-campusos/a9fd285a-931a-4400-b47a-1bfcdcab0447/scratchpad/probe_bot_surface.py`.
It is scratch, not committed. **Recommend promoting it to C1–C4** in §8.1, where it becomes a
permanent regression test that the bot surface never silently grows.

### 2.3 The three things the connector must do

1. **Hold a CampusOS bot JWT** (HS256, `iss=campusos`, `aud=campusos-api`, `kind=bot`,
   `guild=<one guild id>`). This is *not* the Discord bot token and *not* the JWT signing key.
2. **Call those two endpoints over HTTPS/443** (HTTP permitted on loopback only, for local dev).
3. **Render the nine frozen templates verbatim** — §5.

### 2.4 What the connector must *not* do

- Not read `GET /negotiations/{id}` — bots get 403, and that document is filtered for *one
  participant*, which is not permission to broadcast it to a room.
- Not create negotiations, submit availability, bind channels, or answer approvals. All are
  human-token-only.
- Not assert "this Discord user is that CampusOS student" — §4.
- Not compose its own sentence, ever. Not even an error. Not even "something went wrong with
  negotiation neg_abc" — the *existence* of a negotiation is itself disclosure.
- Not cache a summary and re-post it. One fresh authorization check per update
  (`groupchat/publisher.py:1`); consent can be withdrawn between polls.
- Not log HTTP response bodies. `groupchat/bot.py:131-133` disables the `discord` and `httpx`
  loggers precisely because they embed response content.

---

## 3. Requirement 5, honestly assessed

You asked for an adapter that lets the connector *"trigger scheduling requests, retrieve safe
status summaries, and initiate private approval flows."* Two of those three are already
possible. The third is not, and should not be made possible.

| Capability | Possible? | How |
|---|---|---|
| Trigger scheduling requests | **Partly, and that is correct** | A slash command can register the channel and reply **ephemerally** with the `chn_` reference and instructions. It cannot create the negotiation. |
| Retrieve safe status summaries | **Yes, fully** | `GET …/channel-summary`, poll, render, dedupe, stop on 403. |
| Initiate private approval flows | **No — and this is deliberate** | See below. |

**Why the connector cannot initiate approvals.** `POST /negotiations/{id}/channel-bindings`
raises a `post_to_channel` approval for every participant, and it is human-token-only
(`service.py:592-593`: `self.identity.human()`). The contract's own words: *"There is no
channel-specific consent mechanism, deliberately: one approval surface means one place where
consent can be got wrong."* If a bot could raise approvals, a Discord user could spam approval
requests at students who never consented to be contacted — and the request itself leaks that a
negotiation exists.

**What "initiate" can safely mean,** and what T9 already does: the slash command replies
*ephemerally* (visible only to the invoker) with the channel reference and a pointer to the
student's own client. The student acts on their own device, authenticated as themselves. The
connector hands over a pointer; it never carries the consent. Keep this shape.

**If the connector supports Discord buttons/modals,** a button may deep-link the student to
their own authenticated client. A button must never carry an approval to CampusOS on the
student's behalf — a Discord interaction proves someone clicked in a room, not that the
CampusOS account holder consented.

---

## 4. Binding Discord user IDs to CampusOS students

This already works and **must not be changed**.

```
Student's OAuth ceremony  →  operator sets CAMPUSOS_DISCORD_OAUTH_ACCESS_TOKEN
                          →  python -m backend.manage link-discord <subject>
                          →  backend calls Discord users/@me with that token
                          →  verified snowflake stored on Student.discord_id
```

`backend/manage.py:14-26` verifies the identity with Discord rather than accepting a claimed
ID. The comment at `manage.py:51` states the rule: *"Never take a Discord ID asserted by a
bot."*

Then `POST /channels/{channel_id}/members` **takes no body**. It is authenticated as the
student with a human token, and the backend uses the already-verified Discord identity and
asks Discord whether that identity is a member of this channel (`service.py:562-575`). The
contract explains why this is not a bot-submittable mapping: *"If the bot could assert 'this
Discord user is that CampusOS student', it could bind a student's data to an account they do
not control, and every consent decision downstream would be worthless."*

**Implication for the integration:** the external connector contributes **nothing** to identity
binding. It never sends a Discord user ID to CampusOS in any request. If the connector's API
offers to tell us who its users are, we decline. This is also the answer to requirement 6: the
binding is already secure because the connector is not in it.

**Gap, unchanged by this integration:** there is still no self-service OAuth callback. An
operator runs `link-discord` per student. Fine for a 3-student demo, not a product.

---

## 5. Disclosure restrictions — unchanged, and now a porting risk

`ChannelSummary` carries **no free text**. The server picks a `template_id` from a closed enum
and the client renders it from typed slots. There is deliberately no `other` or `custom` id:
*"an escape hatch here would be the whole hole reopened."*

The table both sides implement verbatim:

| `template_id` | Rendered |
|---|---|
| `gathering_availability` | Collecting availability from {participant_count} people. |
| `proposal_on_table` | There's a time on the table -- round {round} of {max_rounds}. |
| `awaiting_approvals` | Waiting on everyone to confirm. |
| `converged` | Locked in: {agreed_slot}. |
| `failed_no_overlap` | No time works for everyone in this window. |
| `failed_max_rounds` | No time found in {max_rounds} rounds -- over to you. |
| `expired` | This one timed out. |
| `cancelled` | Someone withdrew, so this is off. |
| `consent_withdrawn` | I've been asked to stop posting about this one. |

No template interpolates a name, a label, a category, a reason, or any free string.
`{agreed_slot}` is formatted from timestamps in the channel's own timezone.

`consent_withdrawn` is **deliberately unreachable** in our renderer: withdrawal is communicated
by a uniform 403 and silence, never by a public announcement. It exists in the table so that
neither codebase treats the enum as open.

### 5.1 The new risk this integration introduces

Today `groupchat/render.py` loads `contracts/api.openapi.yaml` **at import time** and validates
every payload against the frozen schema before rendering. If the connector lives in another
repository — and especially in another language — that coupling is lost and the renderer
becomes a hand-copied constant table that can drift from the contract silently.

**This is the single largest privacy risk of switching connectors**, larger than anything about
tokens. Mitigations, in order of preference:

1. **Connector imports our renderer.** If it is Python, `groupchat/render.py` is 100 lines with
   two dependencies and already hostile-payload tested (792 payloads, T9 review). Ship it as
   the integration adapter and the problem disappears.
2. **Contract conformance test in CI.** A test that reads the frozen enum from
   `api.openapi.yaml` and asserts the connector's table has exactly those nine keys and exactly
   those nine strings. Fails the build on drift. **Required if option 1 is not taken.**
3. **A thin CampusOS-side proxy** that returns pre-rendered text. Rejected: it would put a
   server-composed sentence back on the wire, which is the exact design the contract removed.

---

## 6. The one genuine blocker: our backend needs a Discord credential too

This is the part that does not fall out neatly, and it needs your decision.

`backend/channels/discord.py` is **not optional glue**. It is how the backend independently
verifies (a) that the bot can view the channel and (b) how many people can actually read the
room — which is what channel consent is *about*. It calls Discord as a bot
(`Authorization: Bot <token>`, `CAMPUSOS_DISCORD_TOKEN`) and needs **Server Members Intent**.

`DiscordREST.context()` fetches `users/@me`, resolves *that bot's* guild membership, and
requires it to pass `can_view`. **So whichever bot identity the backend holds must itself be a
member of the guild and able to see the channel.**

### 6.1 Three options

| | Approach | Second bot? | Verdict |
|---|---|---|---|
| **A** | Friend's bot token is also configured as `CAMPUSOS_DISCORD_TOKEN` on our backend | **No** | **Recommended.** One Discord application; their process runs the gateway, ours runs REST verification. |
| **B** | Our own verification bot joins the same guild alongside theirs | Yes | Works, but violates requirement 4. |
| **C** | Backend trusts the connector's claims about audience size and membership | No | **Reject.** Destroys B1, the audience-growth re-consent rule, and the entire consent model. |

**Recommend A.** Be clear-eyed about what it asks: a Discord bot token is full control of that
bot application. Your friend is extending real trust, and it is reciprocal — our backend
becomes able to act as their bot. Agree in advance that the token lives only in our backend's
environment, is never committed, and is rotated when the demo ends.

**If your friend will not share the token, take B and accept the second bot.** Requirement 4
should yield here, because the only no-second-bot alternative is C, and C is not a trade-off —
it is removing the thing the product is for.

### 6.2 No tooling issues the bot JWT

Searched `backend/`, `scripts/`, `docs/`: `manage.py` supports `provision` and `link-discord`
only. **Nothing mints a `kind=bot` JWT with a `guild` claim.** The READMEs say "operator-issued
out of band", which today means by hand. This blocks T7b whether or not we switch connectors.

**Recommended (small, additive, after you approve):** `python -m backend.manage issue-bot
<subject> --guild <id> --ttl <hours>`, printing once to stdout and never persisting. Strictly
local, like the rest of `manage.py`, and never an HTTP route.

### 6.3 Subject stability

`register_channel` sets `channel.bot = token.sub` and `channel-summary` requires
`channel.bot == token.sub` (`service.py:548, 631-635`). A channel registered under one bot
subject is **permanently unreadable** by a token with a different subject — `POST /channels`
returns 403 rather than re-registering (`service.py:547-549`).

Consequences: pick the connector's subject **once**, before any live registration; re-issuing
must keep the same `sub`; and any channel T9's bot already registered is unusable by the new
connector. For a fresh test server this is free, so **register nothing until the subject is final**.

---

## 7. Changes required to T7b

T7b is currently scoped to *our* bot. Switching connectors changes what is verified, and in two
places **weakens** it — those need recording, not hiding.

### 7.1 Still valid, unchanged

- Guild Members intent confirmed enabled in the Developer Portal, **and the failure mode when
  it is not** — this is now *more* important: it is our backend that needs the intent, while
  the friend's connector may work fine without it, so the failure will look like our bug.
- Real permission calculation checked against Discord's own answer, both ways. **This remains
  the highest-risk unknown in the project** (`task-graph.md:641-646`): `can_view()` and its
  fixtures were written by the same agent, so if Discord's real overwrite semantics differ,
  both are wrong together. Unaffected by the connector choice — it is our code either way.
- Full consent cycle: bind → all approve → summary posted → one withdraws → **posting stops**.
- Declined and pending indistinguishable, live.
- A rate limit encountered and survived.
- Real channel transcript in the handoff, every line one of the nine frozen sentences.
- `tests/live/discord/` skips visibly without a token.

### 7.2 New criteria

- [ ] **Connector conformance**: its rendered output is byte-identical to `render.py` for all
      nine templates, including the dash and timezone formatting.
- [ ] **Connector sends no Discord user IDs to CampusOS.** Verified by capturing every outbound
      request during a full cycle, not by reading its source.
- [ ] **Connector cannot call a human-only endpoint.** Point its credential at
      `POST /negotiations/{id}/channel-bindings` and `GET /negotiations/{id}`; both must 403.
- [ ] **403 handling is silent.** On withdrawal the connector stops and says nothing in-channel.
- [ ] **No free text reaches the channel** under connector error conditions — timeouts, 503,
      malformed payloads, its own internal exceptions. T9's bot was audited for this; a
      third-party one has not been.
- [ ] **Subject stability** recorded: the `sub` used, and that it will not change.
- [ ] If option A: **token custody recorded** — who holds it, where it lives, rotation date.

### 7.3 Criteria that become weaker — record, do not quietly drop

- [ ] **Source auditability.** We cannot assert the connector never composes prose, only that it
      did not during the tests we ran. State it that way in the handoff.
- [ ] **Supply chain.** Its dependencies are not ours and are not pinned by us. If it is to run
      with a token that can read our summaries, its lockfile should be reviewed at least once.
- [ ] If option B: **two bots in one guild** changes the audience count our backend computes.
      Bots are guild members. Verify whether `can_view` counts them, and whether that shifts
      `audience_size_at_consent` and so the re-consent trigger.

### 7.4 Scope

T7b currently owns `tests/live/discord/` and the `groupchat/README.md` checklist. If `groupchat/`
is retired, that is an **Orchestrator** decision, not T7b's — and I would keep it: it is the
executable specification of correct client behaviour and the only thing we can diff a
third-party connector against. Keep the mock path working regardless; CI has no token.

---

## 8. Test cases

Opt-in by environment, visible skip with a reason, never a silent pass. A Discord test that
no-ops without a token is worse than none.

### 8.1 Offline — no Discord, no token, runnable now (`tests/integration/connector/`)

| # | Case | Expected |
|---|---|---|
| C1 | Connector token on `GET /negotiations/{id}` | 403 |
| C2 | Connector token on `POST /negotiations/{id}/channel-bindings` | 403 |
| C3 | Connector token on `GET …/channel-bindings` | 403 |
| C4 | Connector token on `PUT /me/availability`, `POST /approvals/{id}`, `POST /grants` | 403 each |
| C5 | `GET …/channel-summary` with binding `pending_consent` / `declined` / `withdrawn` / `pending_reconsent` / absent | 403, **byte-identical bodies** across all five |
| C6 | `POST /channels` with `max_disclosure_level: "category"` and `"full"` | 400, schema rejection |
| C7 | `POST /channels` for a channel registered by a different `sub` | 403 |
| C8 | Nine-template conformance against the enum read from `api.openapi.yaml` | exact match, no extras, no missing |
| C9 | Connector renderer vs `render.py` on the full `ChannelSummary` fixture set | byte-identical |
| C10 | Connector fed a payload with an extra property, an unknown `template_id`, `round > max_rounds`, mismatched `negotiation_id` | refuses to render; posts nothing |
| C11 | Connector fed 503s, timeouts, truncated JSON | posts nothing; no exception text in-channel |
| C12 | Full cycle against a recording proxy | **zero** Discord user IDs in any request body or query string |

C1–C9 can be written against the existing `FakeDiscord` harness **before the connector arrives**,
because they test our side of the boundary. Worth doing now.

### 8.2 Live — needs the token, the server, and your go-ahead (`tests/live/discord/`)

| # | Case | Expected |
|---|---|---|
| L1 | Slash command registers the actual invoking channel | `chn_` returned, reply **ephemeral** |
| L2 | Backend `audience()` against the real guild | count matches a hand count of who can see the room |
| L3 | Member who can view vs member who cannot (role overwrite) | `member()` matches Discord's own answer, **both ways** |
| L4 | Guild Members intent **disabled** | documented failure mode, fails closed |
| L5 | Thread, forum, DM | 403, fails closed |
| L6 | Channel in another guild | 403 |
| L7 | Full consent cycle, 3 students | one summary posted per state change, no duplicates |
| L8 | One participant withdraws | posting stops within one poll; **nothing said in-channel** |
| L9 | Audience grows past `audience_size_at_consent` | `pending_reconsent`, posting stops |
| L10 | Rate limit | no crash, no double-post |
| L11 | Full transcript | every line one of the nine frozen sentences |
| L12 | Backend down mid-watch | connector stops, posts nothing |

### 8.3 Mutation checks

The suite must have teeth — this is how T2, T9 and T7a were each verified:

- Break the connector's `converged` template string → C9 fails.
- Make the connector ignore 403 → L8 fails.
- Remove the `channel.bot == sub` check in `service.py` → C7 fails.
- Add a tenth template to the connector → C8 fails.

If any mutation leaves the suite green, the suite is decorative.

---

## 9. What I need from the connector documentation

1. **Language and runtime** — decides whether option 1 of §5.1 (import `render.py`) is open.
2. **Is it one Discord application or several?** Decides §6.1 directly.
3. **Will your friend share the bot token with our backend,** or do we accept a second bot?
4. **Does it have a stable service identity** we can mint a `kind=bot` JWT for and never change?
5. **Can it hold a bearer credential** for an outbound HTTPS API, with the token in its
   environment and never logged?
6. **Does it support ephemeral replies?** Required — the `chn_` handoff must not be public.
7. **What does it log, and does it log response bodies?**
8. **Does it have any existing notion of "user identity" it would want to send us?** The answer
   must end up being "it sends none".
9. **Who operates it during the demo,** and can it be pointed at a loopback CampusOS for testing
   before anything touches a real server?

---

## 10. Recommended sequence

1. **Now, no connector needed:** write C1–C9. They pin our side of the boundary and are useful
   whatever connector arrives. ~Half a day, no external dependency.
2. **Now, needs your approval:** add `manage.py issue-bot`. Blocks T7b either way. ~1 hour.
3. **On receiving the docs:** answer §9, pick A or B, finalise the subject.
4. **Then:** C10–C12 against the real connector, still offline.
5. **Then, with your explicit go-ahead:** T7b live, §8.2.

Steps 1 and 2 are the only ones that touch the repository, both are additive, and neither
changes production code or a frozen contract. Nothing in steps 3–5 happens without you.

---

## Appendix — unrelated doc drift found while reading

`docs/architecture.md:265-266` still says the bot *"reads `GET /negotiations/{id}/channel-summary`
and posts the `text` verbatim"*. There has been no `text` field since `template_id` replaced it
in T1's second review round. The code is right and the prose is stale. One-line fix, noted here
rather than silently changed, since this assessment is not supposed to modify anything.
