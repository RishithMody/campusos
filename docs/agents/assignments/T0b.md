# Assignment — T0b

| | |
|---|---|
| **Task** | `T0b` — Track 1 Cubbie Skill (mandatory deliverable) |
| **Agent** | Orchestrator |
| **CLI** | `claude` |
| **Reviewer** | Human |
| **Depends on** | T0 ✅ **and** human decision D2 (roster + entry owner) |
| **Status** | `BLOCKED` — on D2 only |
| **Branch** | `task/T0b-cubbie-skill` |
| **Worktree** | `~/campusos-worktrees/T0b-cubbie-skill` |
| **Repair attempts** | 0 / 3 |
| **GPU approval** | `NONE` — not required, and must stay that way |

## Objective

Ship the one mandatory deliverable: a Cubbie Skill, submitted to Track 1.

This is now the **highest-priority task in the project**, ahead of the product build. T0 verified
why: Track 1 gates Tracks 2 and 3 (the organizers' database refuses them until a Track 1 entry
exists), it is scored largely on **public votes accumulated over time**, and entries stay
editable while the window is open with their votes intact. It is also small — a folder with a
`SKILL.md` in a public GitHub repo is the entire bar.

A perfect demo with a missing mandatory deliverable scores zero, and forfeits two other tracks.

## Verified format — no guessing required

Full detail with sources: `docs/hackathon-requirements.md` §3, §5, §8.

```
<skill-name>/
├── SKILL.md          (required: YAML frontmatter + Markdown body)
├── scripts/          (optional)
├── references/       (optional)
└── assets/           (optional)
```

| Rule | Value |
|---|---|
| **Only hard failure** | no readable `SKILL.md` in the folder |
| `name` | `^[a-z0-9]+(?:-[a-z0-9]+)*$`, ≤64 chars, folder named after it |
| `description` | ≤1024 chars; **first sentence ≤200 chars** (that is what Cubbie's Skill list shows) |
| Body | ≤500 lines |
| Frontmatter fields | only `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools` |
| Install | the student texts Cubbie the **public** GitHub link; Cubbie `git clone`s it |
| Updates | Cubbie installs the **newest commit** — push to update, no resubmission needed |

There is **no** `cubbie.yaml` and no Cubbie-specific manifest.

## File ownership

**You own:** `skills/squad-sync/` (final name is part of this task), `submission/track1/`
**Read-only:** everything else. This task writes no backend, frontend, ml or infra code.

**Publishing target (D1):** the Skill ships in a **separate public GitHub repo**. `campusos`
stays private. Develop here, publish there; the submitted link points at the public repo.

## Scope — instructions only, no backend

Per ADR 0001 (D-3): the entry uses only Cubbie's **connected abilities** and has the student
share the result themselves. It must not depend on our API, our cluster, or anything we operate.
The hosted-API version is a later push to the same repo.

The human chose to submit **when polished** (D5). That makes this property more important, not
less: no deadline is published, so once the Skill exists keep it **validated and submittable on
short notice** — validator clean, repo public, roster known — and re-check the live windows.

## Acceptance criteria

- [ ] `SKILL.md` valid against every rule in the table above
- [ ] `python3 validate_cubbie_skill.py <folder>` reports no `FAIL`; warnings reviewed
- [ ] Cubbie's abilities named **in plain words** — never tool names, parameters or JSON
- [ ] Every *connected* ability (Canvas, Google) has a stated fallback for "not connected"
- [ ] Every send / book / submit step waits for the student's explicit yes
- [ ] The description says what this adds over Cubbie's built-in `study-plan-builder`, so Cubbie
      can tell them apart, and the name does not collide with a built-in
- [ ] A "Replies" section follows the kit's iMessage style guidance
- [ ] Installed from its public GitHub link on a **real Cubbie account**, main flow works
- [ ] No secrets, credentials, API keys, or private student data anywhere in the folder
- [ ] Submission fields within limits: project name ≤60, one-liner ≤140, 1–4 members with
      distinct emails, every link `https://`, repo link is `https://github.com/<owner>/<repo>`
- [ ] Submitted from the account the human nominated in D2, after they previewed and said yes

## Required tests

- `validate_cubbie_skill.py` clean of `FAIL` — **real output pasted in the handoff**
- Manual install-and-run on a real Cubbie account, recorded honestly. "Could not test — no
  Cubbie access" is a correct answer. A claimed pass that did not happen is not.

## Context the agent cannot infer

- The validator lives in the official kit, not in this repo:
  `skills/cubbie-skill-creator/scripts/validate_cubbie_skill.py` in
  <https://github.com/imaginix-inc/cubbie-hackathon-kit>. It needs PyYAML.
- **Cubbie texts only its own student.** Any flow that involves other people works by having
  *the student* share something. Do not design around Cubbie messaging a third party.
- **Scripts cannot call Cubbie's abilities.** Cubbie fetches the data and passes it in.
- Prefer the lightest sign-in rung that works. Every sign-in step costs installs, and installs
  are votes.
- Recommended product direction and the three candidate ideas:
  `docs/hackathon-requirements.md` → "Recommended Track 1 Skill". Confirm D3 first.

## Blocked on

| | Decision | Why it blocks |
|---|---|---|
| **D2** | Team roster (1–4, name + school email) and the entry **owner** | Only the owner can edit; one address is one account. **The only thing still blocking this task.** |

Settled already: D1 separate public Skill repo · D3 pivot to `squad-sync` · D5 submit when
polished, not early.

## Out of scope

- Product features, backend, frontend, ML, infra
- Tracks 2 and 3 (T9, T10, T11)
- Submitting anything without an explicit human yes

## Definition of done

1. All acceptance criteria met
2. Validator output pasted in the handoff; install test recorded honestly
3. Committed on `task/T0b-cubbie-skill`
4. `./scripts/agents.sh handoff T0b` completed and filled in
5. Entry submitted **after** an explicit human yes, and its gallery link recorded in
   `docs/hackathon-requirements.md`
6. Status `REVIEW`. **Do not merge.**
