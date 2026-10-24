#!/usr/bin/env bash
#
# test_agents_sh.sh — regression tests for the orchestration tooling itself.
#
# The orchestration script is the thing standing between six agents and the repository,
# so it gets tests like anything else. These assert on EXIT CODES, because that is the
# contract: a guard that fails to refuse is the failure mode that matters.
#
# Read-only and guard tests always run. Tests that create a worktree run only when that
# is safe (the T1 branch does not already exist), so this is non-destructive on a working
# repository and complete in CI's fresh checkout.
#
#   ./scripts/ci/test_agents_sh.sh
#
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1
A=./scripts/agents.sh
pass=0; fail=0; skipped=0

t() {
  local name="$1" exp="$2"; shift 2
  "$@" >/dev/null 2>&1
  local got=$?
  if [ "$got" = "$exp" ]; then
    pass=$((pass + 1)); printf '  PASS  %-50s (exit %s)\n' "$name" "$got"
  else
    fail=$((fail + 1)); printf '  FAIL  %-50s (exit %s, expected %s)\n' "$name" "$got" "$exp"
  fi
}
skip() { skipped=$((skipped + 1)); printf '  SKIP  %-50s (%s)\n' "$1" "$2"; }

echo "Read-only commands"
t "help"                          0 $A help
t "doctor"                        0 $A doctor
t "list"                          0 $A list
t "status"                        0 $A status
t "unknown command is rejected"   1 $A bogus-command

echo "Guards refuse what they must"
t "create: unknown role"          1 $A create nosuchrole
t "create: unknown task"          1 $A create ml T99
t "create: BLOCKED task"          1 $A create backend
t "start: missing worktree"       1 env CAMPUSOS_ALLOW_BLOCKED=1 $A start backend
t "review: missing worktree"      1 $A review backend
t "cleanup: missing worktree"     1 $A cleanup backend
t "cleanup: unknown argument"     1 $A cleanup nosuchthing

echo "CI helper scripts"
t "validate_contracts (pre-T1)"   0 python3 -I scripts/ci/validate_contracts.py
t "validate_contracts --strict"   1 python3 -I scripts/ci/validate_contracts.py --strict
t "secret_scan --tracked"         0 ./scripts/ci/secret_scan.sh --tracked
t "secret_scan rejects bad mode"  2 ./scripts/ci/secret_scan.sh --bogus-mode

echo "Secret scan actually catches secrets"
tmp="$(mktemp -d)"
# The fake credentials are assembled at runtime from harmless halves, so this test file
# does not itself contain a string the scanner would (correctly) refuse to commit.
{
  printf 'AWS_KEY = "%s%s"\n'      'AKIA' 'IOSFODNN7EXAMPLE'
  printf 'GITHUB_TOKEN = "%s%s"\n' 'ghp_' '0123456789abcdefghijklmnopqrstuvwx'
} > "$tmp/planted.py"
(
  cd "$tmp" || exit 1
  git init -q . && git add -A >/dev/null 2>&1
  cp "$OLDPWD/scripts/ci/secret_scan.sh" .
  ./secret_scan.sh --staged >/dev/null 2>&1
  exit $?
)
if [ $? -eq 1 ]; then
  pass=$((pass + 1)); printf '  PASS  %-50s (exit 1)\n' "planted credentials are blocked"
else
  fail=$((fail + 1)); printf '  FAIL  %-50s\n' "planted credentials were NOT blocked"
fi
rm -rf "$tmp"

echo "Worktree lifecycle"
if git show-ref --verify --quiet refs/heads/task/T1-architecture; then
  skip "create / handoff / cleanup" "task/T1-architecture already exists"
else
  t "create T1 (READY in the graph)"  0 $A create orchestrator T1
  t "create: never overwrites"        1 $A create orchestrator T1
  t "list with a worktree"            0 $A list
  t "status with a worktree"          0 $A status
  t "start: dry run resolves"         0 env CAMPUSOS_DRY_RUN=1 $A start orchestrator T1
  t "review: refuses, no commits"     1 $A review T1
  t "handoff: scaffolds a file"       0 $A handoff T1
  t "cleanup: refuses when dirty"     1 $A cleanup T1
  # The handoff above is an uncommitted file; discard it so cleanup can proceed.
  wt="${CAMPUSOS_WORKTREE_DIR:-$(pwd)-worktrees}/T1-architecture"
  [ -d "$wt" ] && git -C "$wt" clean -qfd
  t "cleanup: succeeds when clean"    0 $A cleanup T1
fi

printf '\n%s passed, %s failed, %s skipped\n' "$pass" "$fail" "$skipped"
[ "$fail" -eq 0 ] || exit 1
