# Cubbie Hackathon — verified requirements

**Task:** T0. **Status:** verified against official sources on the dates shown.
**Rule for this file:** every claim carries a source and a date checked. Anything not published
is recorded under [`## Unverified`](#unverified), never guessed. If you add to this file, keep
that property — a fabricated requirement here propagates into every other task.

Last checked: **2026-10-24**.

---

## Sources

| # | Source | What it is | Checked |
|---|---|---|---|
| S1 | <https://hackathon.cubbie.ai/> | The event site. Self-described **working draft**: "dates, place and scoring are still being finalized" | 2026-10-24 |
| S2 | <https://hackathon.cubbie.ai/skill.md> | Official machine-readable instructions for AI assistants | 2026-10-24 |
| S3 | <https://github.com/imaginix-inc/cubbie-hackathon-kit> | Official hackathon kit (Apache-2.0) | 2026-10-24 |
| S4 | [`skills/cubbie-hackathon/references/rules.md`](https://raw.githubusercontent.com/imaginix-inc/cubbie-hackathon-kit/main/skills/cubbie-hackathon/references/rules.md) | Tracks, rules, judging, submission limits. Header says "as of 2026-10-22" | 2026-10-24 |
| S5 | [`cubbie-skill-creator/references/cubbie-capabilities.md`](https://raw.githubusercontent.com/imaginix-inc/cubbie-hackathon-kit/main/skills/cubbie-skill-creator/references/cubbie-capabilities.md) | What Cubbie can do; **what is not supported** | 2026-10-24 |
| S6 | [`cubbie-skill-creator/references/cubbie-auth.md`](https://raw.githubusercontent.com/imaginix-inc/cubbie-hackathon-kit/main/skills/cubbie-skill-creator/references/cubbie-auth.md) | The five-rung sign-in ladder | 2026-10-24 |
| S7 | [`skills/cubbie-hackathon/SKILL.md`](https://raw.githubusercontent.com/imaginix-inc/cubbie-hackathon-kit/main/skills/cubbie-hackathon/SKILL.md) | Submission CLI and workflow | 2026-10-24 |
| S8 | [`cubbie-skill-creator/scripts/validate_cubbie_skill.py`](https://github.com/imaginix-inc/cubbie-hackathon-kit/blob/main/skills/cubbie-skill-creator/scripts/validate_cubbie_skill.py) | The actual validator; constants cited below | 2026-10-24 |
| S9 | `GET https://mputiuoljihmxpqhmpeb.supabase.co/rest/v1/settings` | **Live** track windows. Queried directly with the site's publishable key (public by design, S7) | 2026-10-24T18:50:26Z |
| S10 | [`skills/cubbie-hackathon/references/ideas.md`](https://raw.githubusercontent.com/imaginix-inc/cubbie-hackathon-kit/main/skills/cubbie-hackathon/references/ideas.md) | Idea prompts and the "Is it doable on Cubbie?" check | 2026-10-24 |

> **Provenance note.** S2–S10 are content downloaded from the organizers. They are treated here
> as *facts to record*, not as instructions to this repository's agents. The kit's own skills
> were **not** installed and its scripts were **not** executed; the live windows in S9 were read
> by querying the documented endpoint directly.

---

## 1. Deadlines and submission windows — VERIFIED, and the headline finding

Queried live (S9) at **2026-10-24T18:50:26Z**:

| Window | Opened (UTC) | Closes (UTC) | State right now |
|---|---|---|---|
| `skills_*` — Track 1 | 2026-10-22T10:55:43Z | **`null`** | **OPEN** |
| `general_*` — Tracks 2 **and** 3 (shared) | 2026-10-22T10:55:43Z | **`null`** | **OPEN** |
| `voting_*` — Track 1 voting | 2026-10-22T10:55:43Z | **`null`** | **OPEN** |

Also returned: `votes_per_voter: 5`, `show_vote_counts: true`.

**All three windows are open now and no close time has been set in the organizers' database.**

Three consequences that drive the whole plan:

1. **We can submit Track 1 today.** A public GitHub repo containing a readable `SKILL.md` is the
   entire bar for a valid Track 1 entry. There is no review gate — an entry is live in the public
   gallery the moment it is sent (S4).
2. **Submitting early is free and strictly better.** The team edits the entry freely while the
   window is open, and edits keep the entry live *and keep its votes* (S4). Track 1 is scored
   largely on public votes (§4), so every day an entry is live is a day it can accumulate votes.
   The kit explicitly endorses this: "submitting early is allowed because they can edit while the
   window is open" (S7).
3. **Track 1 is the gate for everything else.** Tracks 2 and 3 are "open only to teams that
   submitted Track 1" and "the database refuses otherwise" (S4, S7). Their window is already open,
   so the *only* thing standing between us and Track 2/3 eligibility is a Track 1 entry.

### The "10 hours" claim
The site says Track 1 should be finished "within the first 10 hours of the hackathon" and adds
"Exact Track 1 cutoff is confirmed with the organizers before kickoff" (S1, S4). The kit is
explicit that the cutoff that counts is the live Track 1 close time, and that **a window with no
close time has no deadline set yet — do not guess one** (S4, S7). As of the check above, that
close time is `null`. We therefore have **no verified deadline**, not "10 hours".

**Operational rule:** re-check S9 before every planning decision that depends on time. A close
time can appear at any moment, and the site is still a working draft.

---

## 2. Tracks, eligibility, and deliverables — VERIFIED (S4)

| | Track 1 · Cubbie Skills | Track 2 · Agent-to-Agent | Track 3 · Group Chat Assistant |
|---|---|---|---|
| Who | Every team; **unlocks 2 and 3** | Teams that submitted Track 1 | Teams that submitted Track 1 |
| Built on | A Cubbie Skill, run by Cubbie | **Anything** — any messaging app, any open-source framework | Same as Track 2 |
| Hand in | GitHub repo link (required); public TikTok/Instagram demo video optional | GitHub repo (required); website + demo video optional | Same as Track 2 |
| Judged by | Public votes on the site + the video's social engagement | Judges, privately | Judges, privately |
| Window | `skills_*` | `general_*` (shared with Track 3) | `general_*` (shared with Track 2) |

- Teams are **1 to 4 members**, each with a name and email, listed on every entry (S4).
- **One entry per person per track.** Whoever sends it owns it; listed members can see it but
  cannot start a second entry for that track, and **only the owner can edit it** (S4).
- A team may enter **either or both** of Tracks 2 and 3 (S7).

### What each track asks you to show (S4)
- **Track 1:** a working Skill running on Cubbie; a clear student use case; a short public video
  (optional to submit, counts toward the social score when posted).
- **Tracks 2 and 3:** a working prototype tied to a real campus scenario; a clear reason students
  would say "we need this"; and **if multi-agent, how agents handle conflicting constraints, what
  they share, and when they ask their students to confirm.**

> That last clause is, almost word for word, the thesis CampusOS was already built around. Track 2
> is the natural home for the negotiation and disclosure work already specified in `CLAUDE.md`.

---

## 3. What a Cubbie Skill actually is — VERIFIED (S2, S5, S8)

**A folder containing a `SKILL.md`, in a public GitHub repository.** A student installs it by
texting the repo link to Cubbie; Cubbie asks first, then fetches it with ordinary commands such as
`git clone` (S5). There is no app, no backend, and **no Cubbie-specific manifest** — "Cubbie has no
Skill installer of its own (no `cubbie.yaml`)" (S8).

It is the standard [Agent Skills](https://agentskills.io) format:

```
skill-name/
├── SKILL.md          (required: YAML frontmatter + Markdown body)
├── scripts/          (optional)
├── references/       (optional)
└── assets/           (optional)
```

### Hard limits from the validator (S8)

| Rule | Value |
|---|---|
| **Only hard failure** | no readable `SKILL.md` in the folder |
| `name` pattern | `^[a-z0-9]+(?:-[a-z0-9]+)*$` — lowercase, hyphenated |
| `name` max | 64 chars; the folder should be named after it |
| `description` max | 1024 chars (Agent Skills limit) |
| Description **first sentence** | ≤ 200 chars — this is what Cubbie's Skill list displays |
| `SKILL.md` body | ≤ 500 lines recommended |
| Allowed frontmatter fields | `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools` |
| Large-file warnings | 10 MB/file, 100 MB or 10,000 files/repo |

Everything except a missing `SKILL.md` is a **warning**, not a failure. Validate with
`python3 scripts/validate_cubbie_skill.py <folder>` from the kit (needs PyYAML).

### Where Cubbie installs it
`/user/skills/<name>/`, `~/.agents/skills/`, or `~/.claude/skills/`. The whole folder is copied to
the student's persistent drive; Cubbie can read every file in it. **Installs are per student** —
keys, logins and saved state stay with that student (S5).

### Updating after submission
Cubbie installs the **newest commit** of the repository, so pushing updates the Skill. The entry's
repo link needs no re-submission (S7).

---

## 4. Judging — PARTIALLY VERIFIED

**Track 1 (S1, S4):** "Judges mainly look at public votes on this site and your video's engagement
on social media." The site automatically reads views, likes, comments and shares of the posted
video and combines them with site votes into **one score** on the Track 1 board.
- The demo video must be on **TikTok or Instagram** — the only two platforms the form accepts.
- Up to **5 additional** social posts may be added until voting closes; their reach also counts.
- Voting requires a **school email** (`*.edu` or a known school domain; `+tag` aliases refused).
  One vote per project, not for an entry you own or are listed on, votes are retractable.
  **5 votes per voter** (S9).

**Tracks 2 and 3 (S4):** "Judged privately on what you show us. **Full criteria are announced
before kickoff.**" → see [Unverified](#unverified). The gallery lists these with no votes or ranking.

**Exact weights for any track are not published.** Do not plan against a numeric weighting.

---

## 5. Repository visibility — VERIFIED (S4)

- **Track 1:** the Skill link **must** be a GitHub repo URL —
  `https://github.com/<owner>/<repo>`, or a folder inside it. It must be **public**: a private repo
  installs on Cubbie only after the student signs in to git on Cubbie's computer (S5), which no
  voter or judge will do.
- **Tracks 2 and 3:** "GitHub repo required". The gallery card shows GitHub's preview card, and
  **"GitHub's preview card only shows for public repos."**

**Conclusion: the repository must be public, before judging, for all three tracks.** This is a
decision the human must make deliberately — see [Open decisions](#open-decisions-for-the-human).

---

## 6. Model, API and compute restrictions — VERIFIED: none stated, but the sandbox constrains Track 1

**No rule anywhere in S1–S10 restricts external APIs, self-hosted models, or GPU inference.**
Tracks 2 and 3 explicitly allow "any open-source framework" (S4). A self-hosted Qwen3 8B on our own
H200s therefore **complies**.

But Track 1 runs inside **Cubbie's sandbox**, which has hard technical limits (S5):

| Supported | **Not supported** |
|---|---|
| Skills in Agent Skills format, from a git repo link, `.zip`, or a README install command | **MCP servers, remote or local** |
| Python and Node scripts; Python packages in a venv under `HOME`; global npm packages | System packages (`apt`) |
| **HTTPS (port 443) to any website** | Plain HTTP, SSH, mail, other ports and databases; **reaching a server you start from outside the sandbox** |
| Sign-in via Cubbie's browser, CLI login links, student API keys | OAuth "Sign in with…" buttons for your own app; **hosting your team's keys for all students** |
| Cubbie's abilities, called by Cubbie as `SKILL.md` describes | **Scripts calling Cubbie's abilities directly**; **Cubbie texting anyone other than its own student** |

Consequences for CampusOS:
- A Skill script **may** call our own HTTPS API — this is the legitimate bridge from Track 1 into
  the shared platform. It must be a **publicly reachable HTTPS endpoint**; an SSH-tunnelled H200
  endpoint is unreachable from the sandbox.
- **MCP is ruled out** as a Cubbie integration path.
- "Keep personal data with the student. Send data to your own server **only when the Skill says so
  plainly**" (S5) — a disclosure obligation that happens to match this project's privacy thesis.

### Sign-in ladder — take the lightest rung that works (S6)
1. No sign-in → 2. Accounts already connected to Cubbie (Canvas, Google) → 3. Sign-in on the
website in Cubbie's browser → 4. CLI login link → 5. The student's own API key.
Never ask for a password or key in the chat; Cubbie has a secure-input page for that.
Every sign-in step costs installs, and installs are votes (S10).

---

## 7. Cubbie's existing abilities — VERIFIED (S5)

Canvas *(connected)*; reminders and scheduled check-ins *(including phone calls)*; background tasks;
web search and page/PDF reading; a cloud browser that clicks and fills forms; Google *(connected:
Gmail, Calendar, Drive, Docs, Sheets, Tasks, Contacts)*; email events *(connected)*; document and
slide generation *(Word, PDF, Excel, Markdown, `.ics`, HTML)*; file and media reading *(photos, PDFs,
voice-note transcription)*; memory across conversations; secure input; and a **code sandbox** running
Python/Node with persistent files.

A Skill names these **in plain words** ("read the student's Canvas assignments due in the next 7
days"), never as tool names, parameters or JSON.

### ⚠️ Cubbie already ships two Skills of its own (S5)
- **`email-to-professor`** — drafts formal emails to professors or TAs.
- **`study-plan-builder`** — *"builds or adjusts a day-by-day study or review plan from free time
  and deadlines."*

The docs instruct: "give yours a different name… A Skill in the same area should add something
these do not (a specific workflow, a script, a recurring check-in) and say so in its description."

**This directly collides with the Track 1 brief as written** — see
[Conflicts with the current plan](#conflicts-between-the-verified-rules-and-the-current-plan).

---

## 8. Submission mechanics — VERIFIED (S4, S7)

Sign in with Google or a 6-digit email code. **One email address is one account**; a school alias,
a personal Gmail, dotted/undotted Gmail or a `+tag` is a *different* account and cannot edit the
other's entry. **Use the school email**, and sign in as the person who should own the entry.

Submission is via the site (`https://hackathon.cubbie.ai/#submit`) or the kit's CLI.

### Field limits (enforced by the organizers' database)

| Field | Limit |
|---|---|
| Team name | ≤ 60 chars |
| Project name | ≤ 60 chars (defaults to team name) |
| One-liner / pitch | ≤ 140 chars |
| Members | 1–4, distinct emails, name + email each |
| Every link | must start with `https://` |
| Track 1 Skill link | must be `https://github.com/<owner>/<repo>` (or a folder in it) |
| Track 1 post | optional; must match the chosen platform (`tiktok` or `instagram`) |
| Tracks 2/3 | GitHub repo **required**; website (one link) and demo video optional |

**Public on submission:** team name, project name, one-liner, links.
**Never public:** members and their emails.
Organizers may send an entry back with a note (it leaves the gallery until edited, allowed even
after the window closes) or take it down permanently.

---

## Conflicts between the verified rules and the current plan

Three findings contradict the expanded brief. Each needs a decision before building.

### C1 — Track 3 cannot be built on Cubbie's group chat. There is no such thing.
The brief says "Group chat integration using the interface supported by Cubbie." **Cubbie has no
group chat interface.** It lives in a *1:1* iMessage thread with its own student, and
**"Cubbie texts only its own student. Reaching friends, classmates or professors goes through the
student"** (S5). Cubbie cannot join a group chat or message a third party.

The rules anticipate this: Tracks 2 and 3 "don't need to be built on Cubbie" and accept "any
messaging app: iMessage, Slack, WhatsApp, Discord, or another" (S4).
**Recommendation: build Track 3 on Discord.** The organizers run their own Discord
(<https://discord.gg/7eJADTbQMT>), bot APIs are free and well documented, and it demos on screen.

### C2 — Track 1 as briefed collides head-on with Cubbie's built-in `study-plan-builder`.
The brief asks for "intelligent study planning, schedule management, and personalized
recommendations." Cubbie already ships exactly that (§7). A Skill that duplicates a built-in is
weak on originality and will struggle to trigger, since Cubbie already handles those requests.
**Recommendation: pivot Track 1 to the one thing the built-ins cannot do — coordination *between*
students with minimum disclosure.** See the recommendation below.

### C3 — Agent-to-agent traffic cannot flow through Cubbie.
Track 2 must not be designed as "Cubbie talks to Cubbie". It cannot (S5). Agent-to-agent messaging
belongs to our own FastAPI/LangGraph service; Cubbie is one student-facing *client* of it, and the
student is always the one who shares the link. This matches the Track 2 rules, which never require
Cubbie at all.

---

## Recommended Track 1 Skill

### The three candidates

| # | Skill | The student moment | Cubbie abilities | Sign-in | Extends to |
|---|---|---|---|---|---|
| **1** | **Privacy-preserving group scheduling** *(recommended)* | "Everyone's 'free sometime'." Six texts later, still no time. | Canvas, Google Calendar, memory, reminders, documents (`.ics`) | Rung 2 (already connected) | Track 2 **and** 3 directly |
| 2 | **Group-project rescue** | "can someone start the slides 🙏" — Canvas group assignment, nobody has begun | Canvas, memory, reminders, Gmail drafts | Rung 2 | Track 3 |
| 3 | **Syllabus collision radar** | Week 9 has three deadlines and a midterm, and you find out on Monday | Canvas, documents, reminders, background tasks | Rung 2 | Track 2 (compare collision maps) |

### Recommendation: #1 — privacy-preserving group scheduling

The student's Cubbie reads their own Canvas deadlines and Google Calendar, computes their free/busy
windows, and produces a **minimum-disclosure availability summary** — `busy 2–4pm`, never
`therapy at 2pm` — plus a link the student sends to the group themselves. Each member's Cubbie does
the same. The CampusOS service negotiates a time across the submitted availability, and each
student's Cubbie comes back to *its own student* to confirm before anything is booked.

Why this one:

- **It is the gap in the built-ins.** `study-plan-builder` plans *one* student's time. Nothing
  Cubbie ships coordinates *across* students, because Cubbie structurally cannot (C1/C3). This is
  originality the rules actively reward, and the description can say so explicitly as S5 requires.
- **It obeys every sandbox constraint by construction.** The student does the sharing, so
  "Cubbie texts only its own student" is honoured rather than worked around. HTTPS to our own API
  is the one supported integration path, and we use exactly that.
- **It is one product across three tracks, which is the stated goal.** The availability envelope
  *is* the Track 2 agent-to-agent message. The negotiation *is* the Track 2 deliverable. The Discord
  bot in Track 3 is the group-side surface of the same negotiation. One backend, three submissions.
- **It answers Track 2's judging prompt almost verbatim** — "how agents handle conflicting
  constraints, what they share, and when they ask their students to confirm" (S4). Conflicting
  constraints, minimum disclosure, human approval. That sentence could be our demo script.
- **It demos in 20 vertical seconds**, which is how Track 1 is actually scored: three phones, a
  group chat going nowhere, one confirmed time — and the hook that wins the comments section,
  *"it never tells your friends why you're busy."* Privacy is a visible, shareable feature here,
  not a compliance checkbox.
- **It degrades gracefully.** With no friends connected it still answers "when am I actually free
  this week?" from Canvas + Calendar alone — so it is useful on first install, before any network
  effect exists.

Proposed `name`: **`squad-sync`** (lowercase-hyphenated, 10 chars, no collision with a built-in).
Final name and the ≤200-char first sentence are a T0b decision.

**Phase-1 scope for Track 1: instructions-only, no backend.** The lightest valid Skill is a
`SKILL.md` that uses only connected abilities and has the student share a generated summary. The
hosted-API version is an *upgrade* we push to the same repo later — Cubbie always installs the
newest commit (§3), and the entry needs no resubmission. This keeps a valid Track 1 entry live and
accumulating votes from day one, with no dependency on our backend being up.

---

## Open decisions for the human

| # | Decision | Blocks | Why it needs you |
|---|---|---|---|
| D1 | **Make the repo public, and when.** Required for all three tracks (§5). | T0b, all submissions | Irreversible disclosure. The repo must be public before judging; nothing is published until you say so. |
| D2 | **Team roster:** 1–4 members, name + school email each; who **owns** the entry. | T0b | Only the owner can edit; wrong account = a second entry nobody can fix. School email also enables voting. |
| D3 | **Confirm Track 1 pivot (C2)** from solo study planning to cross-student coordination. | T0b, T1 | Changes the product thesis; the rest of the plan follows from it. |
| D4 | **Confirm Track 3 on Discord (C1)**, since Cubbie group chat does not exist. | Track 3 tasks | Adds a messaging dependency the original brief did not have. |
| D5 | **Submit Track 1 early** (a minimal valid entry now, improved by pushing commits)? | Track 2/3 eligibility | Gains voting days and unlocks Tracks 2/3 immediately. Entry is public the instant it is sent. |

---

## Unverified

Not published as of 2026-10-24. **Do not plan against these; ask on
[the organizers' Discord](https://discord.gg/7eJADTbQMT).**

1. **Every deadline.** All three close times are `null` (S9). The "first 10 hours" framing is on the
   site but the authoritative cutoff is unset. **This is the single largest planning risk.**
2. **Kickoff date and time**, and therefore what "the first 10 hours" is measured from.
3. **Judging criteria and weights for Tracks 2 and 3** — "announced before kickoff" (S4), not yet.
4. **The relative weight of site votes vs. social engagement** in the Track 1 score.
5. **Demo video length, hashtags or tags.** The kit says explicitly: don't make them up (S7).
6. **Event location / whether it is virtual or in person.** Site is a working draft (S1).
7. **Any licensing requirement for submissions.** Nothing stated. (The *kit* is Apache-2.0; that is
   the kit's own licence, not a rule imposed on entries.)
8. **Demo format or time limit for Tracks 2 and 3.** Nothing stated beyond an optional video.
9. **Whether organizers re-review or moderate entries**, beyond the stated power to send one back
   or take it down (S4).
10. **Voting window close**, and whether voting closes with the Track 1 window or separately.
