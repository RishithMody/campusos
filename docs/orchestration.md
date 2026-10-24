# Operating the CampusOS agent system

The operator's runbook. Every command here is copy-pasteable into Warp. No Warp AI features, no
paid orchestration service, no extra framework — just `git worktree`, two CLIs you already have,
and Markdown files.

**Mental model:** each agent is an ordinary `claude` or `codex` session, in its own Git worktree,
on its own branch, given its context by a file. They never talk to each other directly and share
no memory. The repository is the only communication channel, and you are the only thing that
merges.

---

## 0. One-time setup

```bash
cd ~/campusos
./scripts/agents.sh doctor
```

`doctor` checks both CLIs, your Git identity, the hooks, and every coordination file. Fix
anything it flags before starting an agent.

The orchestration tooling has its own regression tests, which also run in CI:

```bash
./scripts/ci/test_agents_sh.sh
```

They assert on exit codes, because that is the contract — a guard that fails to refuse is
the failure mode that matters. They are non-destructive: the worktree-lifecycle tests skip
themselves if `task/T1-architecture` already exists.

---

## 1. Phase 0 — the Orchestrator goes first

**T0 is done.** The verified rules, with sources, are in `docs/hackathon-requirements.md`. Read
its "Open decisions for the human" table before anything else — five decisions (D1–D5) are yours,
and three of them block the only mandatory deliverable.

### 1a. Ship Track 1 (T0b) — do this before the product build

Verified: a Track 1 entry is **a folder with a `SKILL.md` in a public GitHub repo**. No review
gate, editable while the window is open, and edits keep accumulated votes. Track 1 also unlocks
Tracks 2 and 3, which the organizers' database refuses until Track 1 is in.

All three windows are open and **no close time is set** (checked 2026-10-24T18:50:26Z). Times
are never written down in the rules — they are read live, so re-check before planning around
time. The official way, from a clone of the hackathon kit:

```bash
python3 scripts/hackathon.py status      # run from skills/cubbie-hackathon/ in the kit
```

The kit is <https://github.com/imaginix-inc/cubbie-hackathon-kit>. It reads the organizers'
`settings` table with the site's publishable key, which the kit itself prints. A window with no
close time has **no deadline set yet** — do not guess one, and do not treat the site's "first
10 hours" as the cutoff.

Once you have answered D1–D3:

```bash
cd ~/campusos
./scripts/agents.sh create orchestrator T0b
./scripts/agents.sh start  orchestrator T0b
```

**Nothing is submitted without your explicit yes.** An entry is public the moment it is sent.

### 1b. Architecture and contracts (T1)

T2–T5 and T9 all build against the contracts T1 publishes, so nothing else may start until it
is done. T1 depends on nothing and can run in parallel with your D1–D3 decisions.

```bash
cd ~/campusos
./scripts/agents.sh create orchestrator T1
./scripts/agents.sh start  orchestrator T1
```

When T1 is done, the Orchestrator writes the T2–T5 and T9 assignments and moves T2/T3/T4 to
`READY`. Then you merge T1:

```bash
./scripts/agents.sh review T1                  # codex reviews the contracts independently
git -C ~/campusos merge --no-ff task/T1-architecture
```

**The contracts only exist on the T1 branch until you merge.** Do not `create` T2/T3/T4 before
the merge, or they will branch from a `main` with no `contracts/`.

### 1c. Tracks 2 and 3

Both are judged privately and **their criteria are not yet announced**. Track 2 is T7 → T10;
Track 3 is T9 → T11. Both require the Track 1 entry to exist first. T9 is a Discord bot, not a
Cubbie integration — Cubbie has no group chat (see ADR 0001).

---

## 2. Launch the first three agents

Only after T1 is merged. These three are the first parallel batch, and they fill all three slots.

```bash
cd ~/campusos

# Create the isolated worktrees (one branch + one worktree each)
./scripts/agents.sh create backend      # task/T2-backend   -> ~/campusos-worktrees/T2-backend
./scripts/agents.sh create gpu          # task/T3-gpu       -> ~/campusos-worktrees/T3-gpu
./scripts/agents.sh create ml           # task/T4-ml-baseline -> ~/campusos-worktrees/T4-ml-baseline

./scripts/agents.sh list
```

Then launch each one **in its own Warp tab** — they are interactive sessions and each occupies a
terminal:

```bash
# Warp tab 1
cd ~/campusos && ./scripts/agents.sh start backend

# Warp tab 2
cd ~/campusos && ./scripts/agents.sh start gpu

# Warp tab 3
cd ~/campusos && ./scripts/agents.sh start ml
```

`start` resolves the worktree, verifies the right CLI is installed, `cd`s into the worktree, and
launches the CLI with a prompt that tells the agent which files to read. It does **not** pass any
flag that bypasses the CLI's own permission or sandbox protections — you still approve actions
as normal.

Frontend comes later, when contracts are stable and a slot frees up:

```bash
./scripts/agents.sh cleanup gpu          # free a slot once T3 is merged
./scripts/agents.sh create frontend
./scripts/agents.sh start frontend
```

The 3-agent limit is enforced: `create` refuses a fourth implementation worktree.

---

## 3. Monitoring progress

From any terminal, including while agents are running:

```bash
cd ~/campusos
./scripts/agents.sh status
```

You get: the task graph with current status, and per worktree — the branch, uncommitted file
count, commits ahead/behind `main`, last commit, and how many review attempts are used. Plus the
most recent handoffs.

Lighter views:

```bash
./scripts/agents.sh list                            # just worktrees and branches
git -C ~/campusos log --oneline --graph --all -15    # what every branch has actually done
cat docs/agents/status.md                            # the Orchestrator's written view
ls -t docs/agents/handoffs/                          # newest handoffs first
```

**What to actually read.** Don't watch the agent terminals — read what they wrote:

1. `docs/agents/handoffs/<TASK>-<n>.md` — the agent's own report: tests run with real output,
   known limitations, next action
2. `docs/agents/reviews/<TASK>/attempt-<n>.md` — the independent reviewer's findings
3. `git -C ~/campusos-worktrees/T2-backend diff main...HEAD` — the truth

An agent reporting `REVIEW` in its handoff is your signal to review.

---

## 4. The review loop

Bounded at **three** repair attempts. There is no autonomous infinite loop.

```
implement → test → commit → independent review → (fix → re-test → re-review) × max 3 → you merge
```

```bash
./scripts/agents.sh review backend
```

This refuses if the worktree is dirty (an unreproducible review is worthless), counts previous
attempts, seeds `docs/agents/reviews/T2/attempt-N.md` from the template, and launches the
**opposite CLI** — Claude Code reviews Codex's work and vice versa. An agent reviewing its own
output just converges on its own blind spots.

The reviewer ends with one verdict:

| Verdict | What you do |
|---|---|
| `PASS` | Merge it (step 5). |
| `CHANGES_REQUESTED` | Send it back: `./scripts/agents.sh start backend`, point the agent at the attempt file. Then `review` again — the counter increments. |
| `BLOCKED` | The reviewer says what it needs. Usually a missing dependency. |
| `ESCALATE` | Three attempts used. **Read `docs/agents/reviews/T2/ESCALATION.md` and decide yourself.** |

On a fourth attempt the script **refuses to run** and writes `ESCALATION.md` with the review
history, the commits, and the diff size. Your options are re-scope, accept with documented
limitations, reassign, or drop. To deliberately resume a stopped loop, delete `ESCALATION.md` —
that act is intentionally manual.

---

## 5. Merging — only you do this

Agents cannot merge. Three things stop them: `main` is checked out in the primary worktree so a
linked worktree cannot switch to it; `pre-merge-commit` rejects merges from agent worktrees; and
`pre-push` rejects pushes to `main` from them.

Before merging, confirm: the reviewer said `PASS`, the handoff shows **real** test output, and
you have read the diff.

```bash
cd ~/campusos
git log --oneline main..task/T2-backend          # what is coming
git diff main...task/T2-backend                  # read it
./scripts/ci/secret_scan.sh --tracked            # independent of the hook

git merge --no-ff task/T2-backend                # --no-ff keeps the task boundary visible
git push                                         # CI runs here
```

Then update the graph and free the slot:

```bash
# Orchestrator sets T2 to DONE in docs/task-graph.md (or edit it yourself)
./scripts/agents.sh cleanup backend
```

`cleanup` refuses if there are uncommitted changes, and only ever deletes a branch with
`git branch -d` — never `-D`. An unmerged branch always survives, so you cannot lose work to it.

If a merge conflicts, that is an ownership bug: two tasks claimed the same file. Resolve it, then
fix the ownership declaration in `docs/task-graph.md` so it cannot recur.

---

## 6. Everyday command reference

```bash
./scripts/agents.sh doctor                  # health check
./scripts/agents.sh create <role> [TASK]    # new branch + worktree; never overwrites
./scripts/agents.sh list                    # worktrees, branches, task status
./scripts/agents.sh status                  # full dashboard
./scripts/agents.sh start <role> [TASK]     # launch the agent's CLI with context
./scripts/agents.sh review <role|TASK> [cli]  # bounded independent review
./scripts/agents.sh handoff <role|TASK>     # scaffold a handoff, commit hash pre-filled
./scripts/agents.sh cleanup <role|TASK>     # safe worktree removal
./scripts/agents.sh help
```

Roles: `orchestrator` `backend` `gpu` `ml` `frontend` `qa`

One role can hold several tasks — pass a task ID for a task-specific branch:

```bash
./scripts/agents.sh create ml T6            # task/T6-finetune, separate from task/T4-ml-baseline
```

Useful environment overrides:

```bash
CAMPUSOS_DRY_RUN=1 ./scripts/agents.sh start backend                  # show the command + prompt, launch nothing
CAMPUSOS_CODEX_SANDBOX=read-only ./scripts/agents.sh review backend   # read-only reviewer
CAMPUSOS_ALLOW_BLOCKED=1 ./scripts/agents.sh create ml T6             # start a BLOCKED task on purpose
CAMPUSOS_ALLOW_OVER_LIMIT=1 ./scripts/agents.sh create frontend       # exceed 3 agents on purpose
```

`CAMPUSOS_DRY_RUN=1` is the quickest way to see exactly what context an agent will get
before you spend a session on it.

---

## 7. Concurrency, and why three

Three implementation agents, maximum — enforced by `create`.

The limit is not about machine capacity. It is about **your** capacity: you are the only reviewer
of record and the only one who merges. Four agents produce more diffs than one person can read
carefully, and unread diffs are how a multi-agent system quietly fills a repo with plausible,
broken code.

- First batch after T1: **backend, GPU, ML**
- Frontend starts when contracts are stable and a slot frees
- QA runs at checkpoints and holds **no** slot
- The Orchestrator coordinates and writes no feature code
- **No nested agent swarms.** One session, one task.

---

## 8. GPU work

No agent touches the H200s during normal development. Everything runs on mocks.

To authorise GPU work, *you* write a token into the task's assignment file:

```markdown
| **GPU approval** | GRANTED 2026-10-25 by Rishith · scope: vLLM serve Qwen3-8B, 1 GPU · budget: 4 GPU-hours · expires 2026-10-26T00:00Z |
```

Scope, budget, and expiry are required. Approval to serve inference is not approval to train.
No agent — including the Orchestrator — may write this token. Full rules:
`docs/infra-policy.md`.

---

## 9. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `branch 'task/T2-backend' already exists` | Working as designed — nothing is overwritten. Resume with `start`, or `cleanup` first. |
| `T2 is BLOCKED in docs/task-graph.md` | Dependencies unmet. Check the graph. Override only deliberately with `CAMPUSOS_ALLOW_BLOCKED=1`. |
| `concurrency limit reached: 3/3` | Finish and `cleanup` one agent first. |
| `pre-commit blocked: protected shared state` | An agent tried to edit `CLAUDE.md`, the task graph, or `scripts/`. Correct: it should put the request in its handoff. |
| `pre-commit blocked: committing to 'main'` | An agent is on the wrong branch. `git switch -c task/<ID>-<slug>`. |
| `secret-scan FAILED` | A credential is staged. Move it to an env var. **Do not use `--no-verify`.** If it was already committed, rotate it. |
| `cleanup` refuses — uncommitted changes | Deliberate. Commit or discard yourself; the script will not delete your work. |
| Branch survives `cleanup` | It was not merged into `main`. The script never force-deletes. Delete it by hand if you are sure. |
| `git worktree` says a path is already registered but the directory is gone | `git -C ~/campusos worktree prune` |
| `You merged work that is not yours` | An agent merged another task branch. It must `git reset --hard HEAD@{1}`. `review` refuses that branch until it does. |
| An agent claims tests pass but they don't | This is the failure mode to watch for. Always check the handoff's pasted output against a real run. Report it to the reviewer as a finding. |
