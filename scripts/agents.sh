#!/usr/bin/env bash
#
# agents.sh — CampusOS multi-agent orchestration CLI
#
# Manages one Git worktree per task, launches Claude Code / Codex sessions with the
# right context, and runs a bounded review loop. Deliberately dependency-free:
# standard git + bash 3.2 (macOS default), no orchestration framework.
#
#   ./scripts/agents.sh help
#
set -euo pipefail

# ---------------------------------------------------------------- configuration

MAX_IMPL_AGENTS=3          # hard concurrency limit on implementation agents
MAX_REPAIR_ATTEMPTS=3      # bounded review loop

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Resolve the *main* worktree root, even when this script is invoked from a linked
# worktree copy: --git-common-dir always points at the main repo's .git directory.
_common_dir="$(git -C "$SCRIPT_DIR" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
if [ -z "$_common_dir" ]; then
  echo "error: not inside a git repository (looked from $SCRIPT_DIR)" >&2
  exit 1
fi
REPO_ROOT="$(dirname "$_common_dir")"
WORKTREE_DIR="${CAMPUSOS_WORKTREE_DIR:-${REPO_ROOT}-worktrees}"
BASE_BRANCH="${CAMPUSOS_BASE_BRANCH:-main}"
GRAPH="$REPO_ROOT/docs/task-graph.md"

# Launch behaviour. Defaults are deliberately conservative: we never pass a flag
# that bypasses a CLI's own permission or sandbox protections.
#   CAMPUSOS_CLAUDE_PERMISSION_MODE  unset -> use the user's own Claude Code default
#   CAMPUSOS_CODEX_SANDBOX           workspace-write -> writes confined to the worktree
CLAUDE_PERMISSION_MODE="${CAMPUSOS_CLAUDE_PERMISSION_MODE:-}"
CODEX_SANDBOX="${CAMPUSOS_CODEX_SANDBOX:-workspace-write}"

# ----------------------------------------------------------------------- output

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  B=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'
  GRN=$'\033[32m'; YEL=$'\033[33m'; N=$'\033[0m'
else
  B=""; DIM=""; RED=""; GRN=""; YEL=""; N=""
fi

info() { printf '%s\n' "$*"; }
ok()   { printf '%s✓%s %s\n' "$GRN" "$N" "$*"; }
warn() { printf '%s!%s %s\n' "$YEL" "$N" "$*" >&2; }
die()  { printf '%s✗ %s%s\n' "$RED" "$*" "$N" >&2; exit 1; }
hdr()  { printf '\n%s%s%s\n' "$B" "$*" "$N"; }

# ------------------------------------------------------------------- registries

# role -> "<default_task> <impl_cli> <role_file> <holds_impl_slot>"
role_meta() {
  case "$1" in
    orchestrator) echo "T1 claude orchestrator no" ;;
    backend)      echo "T2 codex  backend-engineer yes" ;;
    gpu)          echo "T3 codex  gpu-infra-engineer yes" ;;
    ml)           echo "T4 claude ml-engineer yes" ;;
    frontend)     echo "T5 codex  frontend-engineer yes" ;;
    qa)           echo "T7 codex  qa-security-reviewer no" ;;
    *) return 1 ;;
  esac
}
ALL_ROLES="orchestrator backend gpu ml frontend qa"

# task -> branch/worktree slug
task_slug() {
  case "$1" in
    T0)  echo "requirements" ;;
    T0b) echo "cubbie-skill" ;;
    T1)  echo "architecture" ;;
    T2)  echo "backend" ;;
    T3)  echo "gpu" ;;
    T4)  echo "ml-baseline" ;;
    T5)  echo "frontend" ;;
    T6)  echo "finetune" ;;
    T7)  echo "integration" ;;
    T8)  echo "submission" ;;
    *) return 1 ;;
  esac
}

# Tasks that consume one of the MAX_IMPL_AGENTS slots.
is_impl_task() {
  case "$1" in T2|T3|T4|T5|T6) return 0 ;; *) return 1 ;; esac
}

field() { echo "$1" | awk -v i="$2" '{print $i}'; }

# File modification time as a unix timestamp. BSD (macOS) and GNU stat disagree on flags.
file_mtime() {
  stat -f '%m' "$1" 2>/dev/null || stat -c '%Y' "$1" 2>/dev/null || echo 0
}

# Count existing files from a glob. An unmatched glob stays literal and fails -f, so this
# returns 0 without a pipeline -- `ls <glob> | wc -l` fails under `set -o pipefail`.
count_files() {
  local n=0 f
  for f in "$@"; do
    [ -f "$f" ] && n=$((n + 1)) || true
  done
  echo "$n"
}

resolve_role() {
  local r="$1"
  role_meta "$r" >/dev/null 2>&1 || die "unknown role '$r'. Known roles: $ALL_ROLES"
}

# Read a task's status straight out of the task-graph status board, so the graph
# stays the single source of truth rather than a duplicated state file.
task_status() {
  [ -f "$GRAPH" ] || { echo "UNKNOWN"; return; }
  local s
  s="$(awk -v t="$1" -F'|' '$2 ~ "^ *"t" *$" {print $(NF-1); exit}' "$GRAPH" | tr -d ' `')"
  [ -n "$s" ] && echo "$s" || echo "UNKNOWN"
}

branch_for() { echo "task/$1-$(task_slug "$1")"; }
path_for()   { echo "$WORKTREE_DIR/$1-$(task_slug "$1")"; }

count_impl_worktrees() {
  local n=0 t
  for t in T2 T3 T4 T5 T6; do
    [ -d "$(path_for "$t")" ] && n=$((n + 1)) || true
  done
  echo "$n"
}

require_cli() {
  local cli="$1"
  command -v "$cli" >/dev/null 2>&1 || die \
"required CLI '$cli' is not installed or not on PATH.
  claude -> https://claude.com/claude-code
  codex  -> npm i -g @openai/codex  (or: brew install codex)"
}

other_cli() { [ "$1" = "claude" ] && echo "codex" || echo "claude"; }

# ------------------------------------------------------------------ cmd: create

cmd_create() {
  local role="${1:-}" task="${2:-}"
  [ -n "$role" ] || die "usage: agents.sh create <role> [TASK_ID]"
  resolve_role "$role"
  local meta; meta="$(role_meta "$role")"
  [ -n "$task" ] || task="$(field "$meta" 1)"
  task_slug "$task" >/dev/null 2>&1 || die "unknown task '$task'. See docs/task-graph.md"

  local branch path status
  branch="$(branch_for "$task")"; path="$(path_for "$task")"
  status="$(task_status "$task")"

  # Dependency gate: the graph says whether this task may start.
  if [ "$status" = "BLOCKED" ] && [ -z "${CAMPUSOS_ALLOW_BLOCKED:-}" ]; then
    die "$task is BLOCKED in docs/task-graph.md — its dependencies are not satisfied.
Do not start a task before its dependencies are DONE. The Orchestrator moves it to
READY once they are. To override deliberately: CAMPUSOS_ALLOW_BLOCKED=1 $0 create $role $task"
  fi
  [ "$status" = "DONE" ] && warn "$task is already marked DONE in the task graph." || true

  # Never overwrite an existing branch or worktree.
  if git -C "$REPO_ROOT" show-ref --verify --quiet "refs/heads/$branch"; then
    die "branch '$branch' already exists — refusing to overwrite.
Resume it with:  $0 start $role $task
Or remove it first with: $0 cleanup $task"
  fi
  if [ -e "$path" ]; then
    die "path '$path' already exists — refusing to overwrite."
  fi
  if git -C "$REPO_ROOT" worktree list --porcelain | grep -qx "worktree $path"; then
    die "a worktree is already registered at '$path' — refusing to overwrite."
  fi

  # Concurrency limit.
  if is_impl_task "$task"; then
    local n; n="$(count_impl_worktrees)"
    if [ "$n" -ge "$MAX_IMPL_AGENTS" ] && [ -z "${CAMPUSOS_ALLOW_OVER_LIMIT:-}" ]; then
      die "concurrency limit reached: $n/$MAX_IMPL_AGENTS implementation worktrees exist.
Finish and clean one up before starting another:
  $0 status
  $0 cleanup <TASK_ID>
To override deliberately: CAMPUSOS_ALLOW_OVER_LIMIT=1 $0 create $role $task"
    fi
  fi

  git -C "$REPO_ROOT" show-ref --verify --quiet "refs/heads/$BASE_BRANCH" \
    || die "base branch '$BASE_BRANCH' does not exist yet. Make an initial commit on $BASE_BRANCH first."

  mkdir -p "$WORKTREE_DIR"
  git -C "$REPO_ROOT" worktree add -b "$branch" "$path" "$BASE_BRANCH" >/dev/null
  ok "created worktree for $task ($role)"
  info "  branch:   $branch"
  info "  path:     $path"
  info "  based on: $BASE_BRANCH"
  info ""
  info "Next:  $0 start $role $task"
}

# -------------------------------------------------------------------- cmd: list

cmd_list() {
  hdr "Worktrees"
  printf '%-6s %-12s %-26s %-10s %s\n' "TASK" "ROLE" "BRANCH" "STATUS" "PATH"
  printf '%s\n' "$DIM--------------------------------------------------------------------------------$N"

  local main_branch
  main_branch="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '-')"
  printf '%-6s %-12s %-26s %-10s %s\n' "-" "orchestr." "$main_branch" "-" "$REPO_ROOT (primary)"

  local found=0 t path role r meta
  for t in T0 T0b T1 T2 T3 T4 T5 T6 T7 T8; do
    path="$(path_for "$t")"
    [ -d "$path" ] || continue
    found=1
    role="?"
    for r in $ALL_ROLES; do
      meta="$(role_meta "$r")"
      [ "$(field "$meta" 1)" = "$t" ] && role="$r" || true
    done
    printf '%-6s %-12s %-26s %-10s %s\n' \
      "$t" "$role" "$(branch_for "$t")" "$(task_status "$t")" "$path"
  done
  [ "$found" -eq 0 ] && info "$DIM  (no task worktrees yet — create one with: $0 create backend)$N" || true

  info ""
  info "Implementation slots in use: $(count_impl_worktrees)/$MAX_IMPL_AGENTS"
}

# ------------------------------------------------------------------ cmd: status

cmd_status() {
  hdr "CampusOS agent status"
  info "repo:      $REPO_ROOT"
  info "worktrees: $WORKTREE_DIR"
  info "slots:     $(count_impl_worktrees)/$MAX_IMPL_AGENTS implementation agents"

  hdr "Task graph"
  if [ -f "$GRAPH" ]; then
    awk -F'|' 'NF>3 && $2 ~ /^ *T[0-9]/ {
      gsub(/^ +| +$/,"",$2); gsub(/^ +| +$/,"",$3); gsub(/^ +| +$/,"",$4);
      st=$(NF-1); gsub(/[ `]/,"",st);
      printf "  %-5s %-10s %-22s %s\n", $2, st, $4, $3
    }' "$GRAPH"
  else
    warn "docs/task-graph.md not found"
  fi

  hdr "Worktree detail"
  local any=0 t path branch dirty ahead behind last reviews esc
  for t in T0 T0b T1 T2 T3 T4 T5 T6 T7 T8; do
    path="$(path_for "$t")"
    [ -d "$path" ] || continue
    any=1
    branch="$(branch_for "$t")"
    dirty="$(git -C "$path" status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
    ahead="$(git -C "$path" rev-list --count "$BASE_BRANCH..HEAD" 2>/dev/null || echo '?')"
    behind="$(git -C "$path" rev-list --count "HEAD..$BASE_BRANCH" 2>/dev/null || echo '?')"
    last="$(git -C "$path" log -1 --pretty='%h %s' 2>/dev/null || echo 'no commits')"

    printf '\n  %s%s%s  %s\n' "$B" "$t" "$N" "$branch"
    printf '    status      %s\n' "$(task_status "$t")"
    if [ "$dirty" = "0" ]; then
      printf '    working dir clean\n'
    else
      printf '    %suncommitted changes: %s file(s)%s\n' "$YEL" "$dirty" "$N"
    fi
    printf '    commits     %s ahead / %s behind %s\n' "$ahead" "$behind" "$BASE_BRANCH"
    printf '    last commit %s\n' "$last"

    reviews="$(count_files "$REPO_ROOT/docs/agents/reviews/$t"/attempt-*.md)"
    esc="$REPO_ROOT/docs/agents/reviews/$t/ESCALATION.md"
    if [ -f "$esc" ]; then
      printf '    %sreview      ESCALATED — human decision required%s\n' "$RED" "$N"
    elif [ "$reviews" != "0" ]; then
      printf '    review      %s/%s repair attempts used\n' "$reviews" "$MAX_REPAIR_ATTEMPTS"
    fi
  done
  [ "$any" -eq 0 ] && info "$DIM  (no task worktrees yet)$N" || true

  hdr "Recent handoffs"
  local recent f base
  recent="$(
    for f in "$REPO_ROOT/docs/agents/handoffs"/*.md; do
      [ -f "$f" ] || continue
      base="$(basename "$f")"
      [ "$base" = "TEMPLATE.md" ] && continue || true
      printf '%s\t%s\n' "$(file_mtime "$f")" "$(basename "$f")"
    done | sort -rn | head -5 | cut -f2-
  )"
  if [ -n "$recent" ]; then
    printf '%s\n' "$recent" | while IFS= read -r f; do info "  $f"; done
  else
    info "$DIM  (none)$N"
  fi
  info ""
}

# ----------------------------------------------------------------- cmd: cleanup

cmd_cleanup() {
  local arg="${1:-}"
  [ -n "$arg" ] || die "usage: agents.sh cleanup <role|TASK_ID>"

  local task="$arg"
  if role_meta "$arg" >/dev/null 2>&1; then task="$(field "$(role_meta "$arg")" 1)"; fi
  task_slug "$task" >/dev/null 2>&1 || die "unknown role or task '$arg'"

  local branch path; branch="$(branch_for "$task")"; path="$(path_for "$task")"
  [ -d "$path" ] || die "no worktree at '$path' — nothing to clean up."

  # 1. Never discard uncommitted work.
  local dirty; dirty="$(git -C "$path" status --porcelain | wc -l | tr -d ' ')"
  if [ "$dirty" != "0" ]; then
    hdr "Uncommitted changes in $task — refusing to clean up"
    git -C "$path" status --short
    die "commit or discard these changes yourself, then re-run.
This script will not delete uncommitted work."
  fi

  # 2. Warn about commits that are not yet in the base branch.
  local unmerged; unmerged="$(git -C "$path" rev-list --count "$BASE_BRANCH..HEAD" 2>/dev/null || echo 0)"
  if [ "$unmerged" != "0" ]; then
    warn "$branch has $unmerged commit(s) not in $BASE_BRANCH."
    info "  The worktree will be removed but the ${B}branch will be kept${N}, so no work is lost."
    info "  Review it with:  git -C $REPO_ROOT log $BASE_BRANCH..$branch"
  fi

  git -C "$REPO_ROOT" worktree remove "$path"
  ok "removed worktree $path"

  # 3. Only ever a safe delete. `git branch -d` refuses if the branch is unmerged;
  #    we never force with -D, so an unreviewed branch always survives.
  if git -C "$REPO_ROOT" branch -d "$branch" 2>/dev/null; then
    ok "deleted branch $branch (was fully merged into $BASE_BRANCH)"
  else
    info "$DIM  branch $branch kept — not merged into $BASE_BRANCH.$N"
    info "$DIM  This script never force-deletes a branch. Delete it yourself if you are sure.$N"
  fi
}

# ------------------------------------------------------- shared launch plumbing

# Context handed to every agent session. Points at files rather than inlining
# them: Claude Code and Codex share no memory, so the repo is the only channel.
build_context_prompt() {
  local role="$1" task="$2" role_file="$3" extra="${4:-}"
  cat <<EOP
You are the ${role} agent on CampusOS, working on task ${task}.

You are one of several agents working in parallel in isolated Git worktrees. You share NO
conversation memory with the other agents. Everything you need is in this repository, and
anything another agent needs must be written to a file here.

Read these files now, in this order, before doing anything else:

  1. CLAUDE.md                                  - shared rules for every agent (binding)
  2. docs/agents/roles/${role_file}.md          - your role, scope, and hard limits
  3. docs/task-graph.md                         - the dependency DAG; find ${task}
  4. docs/agents/assignments/${task}.md         - your task brief and acceptance criteria
  5. docs/agents/status.md                      - what the other agents are doing

Then, before editing any file:
  - State which task you are on and summarise its acceptance criteria.
  - State which files you own and will touch. Do not touch files outside that set.
  - Give me a short plan and wait for my go-ahead.

Non-negotiable constraints (full detail in CLAUDE.md):
  - Never merge or push to ${BASE_BRANCH}. Git hooks will reject it. Merging is a human decision.
  - Only edit files your task owns. Protected shared files are Orchestrator-only.
  - contracts/ is read-only unless you are the Orchestrator on T1.
  - No GPU/cluster access or training without a human-signed approval token in your
    assignment file. See docs/infra-policy.md.
  - Report only what actually ran. Paste real command output. Never claim an unrun test passed.
  - When the task is done: run the required tests, commit, write a handoff with
    ./scripts/agents.sh handoff ${task}, and set the task to REVIEW. Do not merge.
${extra}
EOP
}

launch_cli() {
  local cli="$1" wt="$2" name="$3" prompt="$4"
  require_cli "$cli"

  if [ -n "${CAMPUSOS_DRY_RUN:-}" ]; then
    hdr "DRY RUN — nothing was launched"
    info "  cli:      $cli"
    info "  session:  $name"
    info "  worktree: $wt"
    if [ "$cli" = "claude" ]; then
      info "  command:  claude --name '$name'${CLAUDE_PERMISSION_MODE:+ --permission-mode $CLAUDE_PERMISSION_MODE} '<prompt>'"
    else
      info "  command:  codex --sandbox $CODEX_SANDBOX '<prompt>'"
    fi
    hdr "Prompt the agent would receive"
    printf '%s\n' "$prompt"
    return 0
  fi

  hdr "Launching $cli"
  info "  session:  $name"
  info "  worktree: $wt"
  info "$DIM  (exiting the CLI returns you here)$N"
  info ""
  cd "$wt"
  if [ "$cli" = "claude" ]; then
    set -- --name "$name"
    [ -n "$CLAUDE_PERMISSION_MODE" ] && set -- "$@" --permission-mode "$CLAUDE_PERMISSION_MODE" || true
    exec claude "$@" "$prompt"
  else
    exec codex --sandbox "$CODEX_SANDBOX" "$prompt"
  fi
}

# ------------------------------------------------------------------- cmd: start

cmd_start() {
  local role="${1:-}" task="${2:-}"
  [ -n "$role" ] || die "usage: agents.sh start <role> [TASK_ID]"
  resolve_role "$role"
  local meta; meta="$(role_meta "$role")"
  [ -n "$task" ] || task="$(field "$meta" 1)"
  task_slug "$task" >/dev/null 2>&1 || die "unknown task '$task'"

  local cli role_file status wt
  cli="$(field "$meta" 2)"; role_file="$(field "$meta" 3)"
  status="$(task_status "$task")"

  # A task worktree is used when it exists. The Orchestrator may also work directly in
  # the primary worktree (docs/contracts only), so for that role a missing worktree is
  # not an error; for every other role it is, because agents must stay isolated.
  wt="$(path_for "$task")"
  if [ ! -d "$wt" ]; then
    if [ "$role" = "orchestrator" ]; then
      wt="$REPO_ROOT"
    else
      die "no worktree for $task.
Create it first:  $0 create $role $task"
    fi
  fi

  if [ "$status" = "BLOCKED" ] && [ -z "${CAMPUSOS_ALLOW_BLOCKED:-}" ]; then
    die "$task is BLOCKED — dependencies not satisfied. See docs/task-graph.md"
  fi
  [ -f "$REPO_ROOT/docs/agents/assignments/$task.md" ] \
    || warn "docs/agents/assignments/$task.md does not exist — the agent will have no task brief.
  The Orchestrator should write it before you start this agent."

  launch_cli "$cli" "$wt" "$task-$role" \
    "$(build_context_prompt "$role" "$task" "$role_file")"
}

# ------------------------------------------------------------------ cmd: review

cmd_review() {
  local arg="${1:-}" reviewer="${2:-}"
  [ -n "$arg" ] || die "usage: agents.sh review <role|TASK_ID> [claude|codex]"

  local task="$arg" impl_cli="" role_file="qa-security-reviewer"
  if role_meta "$arg" >/dev/null 2>&1; then
    task="$(field "$(role_meta "$arg")" 1)"
    impl_cli="$(field "$(role_meta "$arg")" 2)"
  else
    local r
    for r in $ALL_ROLES; do
      [ "$(field "$(role_meta "$r")" 1)" = "$task" ] && impl_cli="$(field "$(role_meta "$r")" 2)" || true
    done
  fi
  task_slug "$task" >/dev/null 2>&1 || die "unknown role or task '$arg'"

  # Independence: review with the opposite CLI from the one that wrote the code.
  if [ -z "$reviewer" ]; then
    [ -n "$impl_cli" ] && reviewer="$(other_cli "$impl_cli")" || reviewer="codex"
  fi
  case "$reviewer" in claude|codex) ;; *) die "reviewer must be 'claude' or 'codex'" ;; esac

  local wt branch; wt="$(path_for "$task")"; branch="$(branch_for "$task")"
  [ -d "$wt" ] || die "no worktree for $task at '$wt' — nothing to review."

  local dirty; dirty="$(git -C "$wt" status --porcelain | wc -l | tr -d ' ')"
  if [ "$dirty" != "0" ]; then
    git -C "$wt" status --short
    die "$task has uncommitted changes. The implementing agent must commit before review —
a review of an uncommitted tree cannot be reproduced."
  fi
  local n_commits; n_commits="$(git -C "$wt" rev-list --count "$BASE_BRANCH..HEAD" 2>/dev/null || echo 0)"
  if [ "$n_commits" = "0" ]; then
    die "$branch has no commits beyond $BASE_BRANCH — nothing to review."
  fi

  # Refuse to review a branch that has absorbed another task branch. Reviewing it would
  # pass another agent's unreviewed work through this task's review, and blur the file
  # ownership that makes parallel agents safe. Checked here because it is only reliably
  # detectable after the merge commit exists (see .githooks/post-merge).
  local foreign="" other
  for other in $(git -C "$wt" for-each-ref --format='%(refname:short)' refs/heads/task/ 2>/dev/null); do
    # A branch with no commits of its own still points at the base branch, so it is
    # trivially an ancestor of everything. Nothing to absorb -- skip it.
    if [ "$other" = "$branch" ] \
       || git -C "$wt" merge-base --is-ancestor "refs/heads/$other" "refs/heads/$BASE_BRANCH" 2>/dev/null; then
      continue
    fi
    if git -C "$wt" merge-base --is-ancestor "refs/heads/$other" HEAD 2>/dev/null; then
      foreign="$foreign  $other"$'\n'
    fi
  done
  if [ -n "$foreign" ]; then
    hdr "$branch has absorbed another agent's branch"
    printf '%s\n' "$foreign"
    die "refusing to review $task.
Each task is reviewed on its own diff. Merging another task branch in smuggles
unreviewed work past its reviewer and blurs file ownership.

The implementing agent should undo the merge:
  git -C $wt reset --hard <commit before the merge>

If it genuinely needs that work, the Orchestrator sequences the tasks instead."
  fi

  # ---- bounded loop: count prior attempts, escalate instead of looping forever
  local rdir="$REPO_ROOT/docs/agents/reviews/$task"
  mkdir -p "$rdir"
  local prior attempt
  prior="$(count_files "$rdir"/attempt-*.md)"
  attempt=$((prior + 1))

  if [ -f "$rdir/ESCALATION.md" ]; then
    die "$task is already ESCALATED. Human decision required.
Read: docs/agents/reviews/$task/ESCALATION.md
Re-opening the loop is a deliberate human act: delete that file to resume."
  fi

  if [ "$attempt" -gt "$MAX_REPAIR_ATTEMPTS" ]; then
    hdr "Repair attempts exhausted for $task"
    {
      echo "# ESCALATION — $task"
      echo
      echo "**Generated:** $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
      echo "**Branch:** \`$branch\`"
      echo "**Repair attempts used:** $prior / $MAX_REPAIR_ATTEMPTS"
      echo
      echo "The bounded review loop stopped automatically. $MAX_REPAIR_ATTEMPTS review/repair"
      echo "cycles did not converge, so the loop halted rather than retrying indefinitely."
      echo
      echo "## Human decision required"
      echo
      echo "Choose one:"
      echo "- Re-scope or decompose the task, then reset the loop"
      echo "- Accept the current state with known limitations documented"
      echo "- Reassign to a different agent or implement by hand"
      echo "- Drop the task (check whether anything on the critical path depends on it)"
      echo
      echo "## Review history"
      echo
      local f
      for f in "$rdir"/attempt-*.md; do
        [ -f "$f" ] || continue
        echo "- [\`$(basename "$f")\`](./$(basename "$f"))"
      done
      echo
      echo "## Commits on the branch"
      echo
      echo '```'
      git -C "$wt" log --oneline "$BASE_BRANCH..HEAD" 2>/dev/null || true
      echo '```'
      echo
      echo "## Diff size"
      echo
      echo '```'
      git -C "$wt" diff --stat "$BASE_BRANCH...HEAD" 2>/dev/null || true
      echo '```'
      echo
      echo "## To resume"
      echo
      echo "Resuming is deliberate: delete this file, then re-run"
      echo "\`./scripts/agents.sh review $task\`. The attempt counter continues from $prior."
    } > "$rdir/ESCALATION.md"
    warn "wrote docs/agents/reviews/$task/ESCALATION.md"
    die "$MAX_REPAIR_ATTEMPTS repair attempts exhausted — stopping, as designed.
No further automated review will run for $task until a human intervenes."
  fi

  # ---- seed the attempt file from the template so the reviewer fills a real artifact
  local out="$rdir/attempt-$attempt.md"
  local rel="docs/agents/reviews/$task/attempt-$attempt.md"
  if [ ! -f "$out" ]; then
    if [ -f "$REPO_ROOT/docs/reviews/TEMPLATE.md" ]; then
      sed -e "s|<TASK_ID>|$task|g" \
          -e "s|<N>|$attempt|g" \
          -e "s|<BRANCH>|$branch|g" \
          -e "s|<REVIEWER>|$reviewer|g" \
          -e "s|<DATE>|$(date -u '+%Y-%m-%dT%H:%M:%SZ')|g" \
          "$REPO_ROOT/docs/reviews/TEMPLATE.md" > "$out"
    else
      warn "docs/reviews/TEMPLATE.md missing — creating a bare attempt file"
      printf '# Review %s — attempt %s\n' "$task" "$attempt" > "$out"
    fi
  fi

  hdr "Review $task — attempt $attempt of $MAX_REPAIR_ATTEMPTS"
  info "  branch:       $branch ($n_commits commit(s) ahead of $BASE_BRANCH)"
  info "  implemented by: ${impl_cli:-unknown}"
  info "  reviewer:     $reviewer  $DIM(independent: opposite CLI)$N"
  info "  write-up:     $rel"
  [ "$attempt" -eq "$MAX_REPAIR_ATTEMPTS" ] && \
    warn "this is the LAST attempt. If it does not pass, the loop escalates to you." || true

  launch_cli "$reviewer" "$wt" "$task-review-$attempt" "$(cat <<EOP
You are the independent QA / Security Reviewer for CampusOS, reviewing task ${task}
(branch ${branch}). This is repair attempt ${attempt} of ${MAX_REPAIR_ATTEMPTS}.

You did NOT write this code and you share no memory with the agent that did. Review the diff
itself, not the author's description of it.

Read first:
  1. CLAUDE.md                                        - shared rules
  2. docs/agents/roles/${role_file}.md                - your role and hard limits
  3. docs/task-graph.md                               - ${task}'s acceptance criteria
  4. docs/agents/assignments/${task}.md               - the task brief
  5. docs/agents/handoffs/                            - the implementer's latest handoff for ${task}
  6. docs/reviews/TEMPLATE.md                         - the review checklist you must complete

Review the change:
  git diff ${BASE_BRANCH}...HEAD
  git log --oneline ${BASE_BRANCH}..HEAD
$( [ "$reviewer" = "codex" ] && printf '\n  A fast complementary pass:  codex review --base %s\n' "$BASE_BRANCH" || true )
Check every dimension in the template: correctness against acceptance criteria, security and
privacy, API contract compatibility, test coverage, regressions, and unnecessary complexity.

Run the task's required tests yourself. Paste the real command and the real output into your
write-up. If a test cannot run, record why — never record a pass you did not observe.
A review that claims green on an unrun suite is worse than no review, because it is trusted.

Write your findings into this file, which is already seeded with the template:
  ${rel}

Finish with exactly one verdict: PASS, CHANGES_REQUESTED, BLOCKED, or ESCALATE.
  - PASS               -> recommend human merge. You do not merge.
  - CHANGES_REQUESTED  -> list findings precisely enough for the implementing agent to fix them
                          without guessing. It returns for attempt $((attempt + 1)).
  - BLOCKED            -> you could not review; say exactly what you need.

Hard limits: do not rewrite the implementation (you may write tests that demonstrate a defect),
do not merge or push to ${BASE_BRANCH}, and do not exceed ${MAX_REPAIR_ATTEMPTS} attempts.
EOP
)"
}

# ----------------------------------------------------------------- cmd: handoff

cmd_handoff() {
  local arg="${1:-}"
  [ -n "$arg" ] || die "usage: agents.sh handoff <role|TASK_ID>"
  local task="$arg"
  if role_meta "$arg" >/dev/null 2>&1; then task="$(field "$(role_meta "$arg")" 1)"; fi
  task_slug "$task" >/dev/null 2>&1 || die "unknown role or task '$arg'"

  local wt; wt="$(path_for "$task")"
  [ -d "$wt" ] || wt="$REPO_ROOT"

  local tpl="$REPO_ROOT/docs/agents/handoffs/TEMPLATE.md"
  [ -f "$tpl" ] || die "handoff template missing: $tpl"

  local n=1
  while [ -f "$wt/docs/agents/handoffs/$task-$n.md" ]; do n=$((n + 1)); done
  local out="$wt/docs/agents/handoffs/$task-$n.md"
  mkdir -p "$(dirname "$out")"

  local sha files
  sha="$(git -C "$wt" rev-parse --short HEAD 2>/dev/null || echo 'NO-COMMIT-YET')"
  files="$(git -C "$wt" diff --stat "$BASE_BRANCH...HEAD" 2>/dev/null | tail -20)"

  sed -e "s|<TASK_ID>|$task|g" \
      -e "s|<N>|$n|g" \
      -e "s|<BRANCH>|$(branch_for "$task")|g" \
      -e "s|<COMMIT>|$sha|g" \
      -e "s|<DATE>|$(date -u '+%Y-%m-%dT%H:%M:%SZ')|g" \
      "$tpl" > "$out"

  if [ -n "$files" ]; then
    {
      echo
      echo "---"
      echo
      echo "## Diff stat (auto-generated at handoff time)"
      echo
      echo '```'
      echo "$files"
      echo '```'
    } >> "$out"
  fi

  ok "created handoff: ${out#$wt/}"
  info "  commit: $sha"
  info ""
  info "Now fill it in — every section. Paste REAL test output, not a summary."
  info "Then commit it and set $task to REVIEW in docs/task-graph.md (ask the Orchestrator)."
}

# ------------------------------------------------------------------ cmd: doctor

cmd_doctor() {
  local fail=0
  hdr "CampusOS orchestration health check"

  info "repo root:  $REPO_ROOT"
  info "worktrees:  $WORKTREE_DIR"
  info "base branch: $BASE_BRANCH"

  hdr "Required CLIs"
  local c
  for c in git claude codex; do
    if command -v "$c" >/dev/null 2>&1; then
      ok "$c  $(command -v "$c")"
    else
      warn "$c NOT FOUND"; fail=1
    fi
  done
  for c in node npm python3 docker gh jq; do
    if command -v "$c" >/dev/null 2>&1; then ok "$c"; else info "$DIM  - $c not found (needed later)$N"; fi
  done

  hdr "Git identity (required to commit)"
  local gn ge
  gn="$(git -C "$REPO_ROOT" config user.name  || true)"
  ge="$(git -C "$REPO_ROOT" config user.email || true)"
  if [ -n "$gn" ] && [ -n "$ge" ]; then ok "$gn <$ge>"; else
    warn "git user.name / user.email not set — commits will fail"
    info "  git -C $REPO_ROOT config user.name  'Your Name'"
    info "  git -C $REPO_ROOT config user.email 'you@example.com'"
    fail=1
  fi

  hdr "Guard rails"
  local hp; hp="$(git -C "$REPO_ROOT" config core.hooksPath || true)"
  if [ "$hp" = ".githooks" ]; then ok "core.hooksPath = .githooks"; else
    warn "core.hooksPath is '${hp:-unset}', expected '.githooks' — merge/secret guards are OFF"
    info "  git -C $REPO_ROOT config core.hooksPath .githooks"
    fail=1
  fi
  for c in pre-commit pre-merge-commit post-merge pre-push; do
    if [ -x "$REPO_ROOT/.githooks/$c" ]; then ok "hook $c executable"; else
      warn "hook .githooks/$c missing or not executable"; fail=1
    fi
  done

  hdr "Coordination files"
  local f
  for f in CLAUDE.md AGENTS.md docs/task-graph.md docs/agents/status.md \
           docs/reviews/TEMPLATE.md docs/agents/handoffs/TEMPLATE.md docs/infra-policy.md; do
    if [ -f "$REPO_ROOT/$f" ]; then ok "$f"; else warn "$f missing"; fail=1; fi
  done
  for c in $ALL_ROLES; do
    f="docs/agents/roles/$(field "$(role_meta "$c")" 3).md"
    [ -f "$REPO_ROOT/$f" ] || { warn "$f missing"; fail=1; }
  done
  ok "six role definitions present"

  hdr "Concurrency"
  info "  $(count_impl_worktrees)/$MAX_IMPL_AGENTS implementation slots in use"

  info ""
  if [ "$fail" -eq 0 ]; then ok "all checks passed"; else
    warn "some checks failed — see above"; return 1
  fi
}

# -------------------------------------------------------------------- cmd: help

cmd_help() {
  cat <<EOP
${B}agents.sh${N} — CampusOS multi-agent orchestration

${B}USAGE${N}
  ./scripts/agents.sh <command> [args]

${B}WORKTREES${N}
  create <role> [TASK]    Create branch + worktree for a task. Never overwrites.
                          Refuses if the task is BLOCKED or the 3-agent limit is reached.
  list                    List worktrees, branches, and task status.
  status                  Full dashboard: task graph, per-worktree git state, review attempts.
  cleanup <role|TASK>     Remove a worktree. Refuses if there are uncommitted changes.
                          Only ever deletes a branch with 'git branch -d' (never -D).

${B}AGENTS${N}
  start <role> [TASK]     Launch the role's CLI in its worktree with full task context.
  review <role|TASK> [cli]
                          Launch an independent review (opposite CLI by default).
                          Bounded at ${MAX_REPAIR_ATTEMPTS} attempts, then escalates to you.
  handoff <role|TASK>     Scaffold a handoff file with the commit hash pre-filled.

${B}MAINTENANCE${N}
  doctor                  Verify CLIs, git identity, hooks, and coordination files.
  help                    This message.

${B}ROLES${N}
  orchestrator  T1  claude   architecture, contracts, coordination, merge prep
  backend       T2  codex    FastAPI, agent protocol, LangGraph, Postgres/Redis
  gpu           T3  codex    H200 validation, vLLM, Docker, benchmarks
  ml            T4  claude   datasets, baseline eval, LoRA, experiment tracking
  frontend      T5  codex    Next.js dashboard, chat, negotiation visualisation
  qa            T7  codex    tests, independent review, privacy/authz, regressions

  A role may hold several tasks. Pass a TASK_ID for a task-specific branch:
    ./scripts/agents.sh create ml T6      # task/T6-finetune, separate from task/T4-ml-baseline

${B}TYPICAL FLOW${N}
  ./scripts/agents.sh doctor
  ./scripts/agents.sh start orchestrator          # T0 then T1: requirements, contracts
  ./scripts/agents.sh create backend              # after T1 is DONE
  ./scripts/agents.sh create gpu
  ./scripts/agents.sh create ml
  ./scripts/agents.sh start backend               # in its own terminal tab
  ./scripts/agents.sh status                      # monitor from anywhere
  ./scripts/agents.sh review backend              # independent review when it reports REVIEW
  # then YOU merge:  git -C ${REPO_ROOT} merge --no-ff task/T2-backend

${B}ENVIRONMENT${N}
  CAMPUSOS_WORKTREE_DIR            override worktree parent (default: <repo>-worktrees)
  CAMPUSOS_BASE_BRANCH             override base branch (default: main)
  CAMPUSOS_CODEX_SANDBOX           codex --sandbox value (default: workspace-write)
  CAMPUSOS_CLAUDE_PERMISSION_MODE  claude --permission-mode (default: your own setting)
  CAMPUSOS_ALLOW_BLOCKED=1         deliberately start a BLOCKED task
  CAMPUSOS_ALLOW_OVER_LIMIT=1      deliberately exceed ${MAX_IMPL_AGENTS} implementation agents
  CAMPUSOS_DRY_RUN=1               print the resolved command and prompt, launch nothing

${B}WHAT THIS SCRIPT WILL NOT DO${N}
  - merge or push to ${BASE_BRANCH}            (human decision; git hooks also enforce it)
  - force-delete a branch or discard uncommitted work
  - connect to the H200 cluster or start any GPU job
  - pass flags that bypass a CLI's permission or sandbox protections
  - launch nested agent swarms
EOP
}

# ------------------------------------------------------------------------- main

case "${1:-help}" in
  create)  shift; cmd_create  "$@" ;;
  list|ls) shift; cmd_list    "$@" ;;
  status)  shift; cmd_status  "$@" ;;
  cleanup) shift; cmd_cleanup "$@" ;;
  start)   shift; cmd_start   "$@" ;;
  review)  shift; cmd_review  "$@" ;;
  handoff) shift; cmd_handoff "$@" ;;
  doctor)  shift; cmd_doctor  "$@" ;;
  help|-h|--help) cmd_help ;;
  *) printf '%sunknown command: %s%s\n\n' "$RED" "$1" "$N" >&2; cmd_help >&2; exit 1 ;;
esac
