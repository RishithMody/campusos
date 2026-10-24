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

# The agent CLIs are not installed on a CI runner, and the script is supposed to refuse
# rather than pretend. Tests that need one adapt instead of failing spuriously.
have() { command -v "$1" >/dev/null 2>&1; }

# The contract validator needs PyYAML and jsonschema. The repo venv has them; a bare
# system python does not, and the validator is supposed to refuse rather than pretend.
# Agent worktrees have no .venv of their own -- it is gitignored and lives in the primary
# worktree -- so fall back to that one. Python dependencies are not branch-specific.
PRIMARY="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
if   [ -x .venv/bin/python ];           then PYBIN=.venv/bin/python
elif [ -x "$PRIMARY/.venv/bin/python" ]; then PYBIN="$PRIMARY/.venv/bin/python"
else PYBIN=python3; fi
if have claude && have codex; then HAVE_CLIS=1; else HAVE_CLIS=0; fi

echo "Read-only commands"
t "help"                          0 $A help
if [ "$HAVE_CLIS" = "1" ]; then
  t "doctor: passes with both CLIs"  0 $A doctor
else
  # Correct behaviour without the CLIs: report the gap and exit non-zero.
  t "doctor: reports missing CLIs"   1 $A doctor
fi
t "list"                          0 $A list
t "status"                        0 $A status
t "unknown command is rejected"   1 $A bogus-command

echo "Guards refuse what they must"
WT_BEFORE="$(git worktree list | wc -l)"
t "create: unknown role"          1 $A create nosuchrole
t "create: unknown task"          1 $A create ml T99
# These four exercise guards that, if the guard is broken, DO something: create a
# worktree, or delete one. They used to hardcode `backend` (T2), which was safe only for
# as long as T2 was BLOCKED with no worktree. Once T2 went READY and got one, the create
# test created a real worktree and the cleanup test deleted it -- the suite quietly
# destroyed a live agent's branch, which is the worst possible moment to find this out.
#
# So the target is chosen at run time: a task that is BLOCKED *and* has no worktree. If
# the graph has no such task, these skip rather than reach for a live one.
SAFE_ROLE=""; SAFE_TASK=""
for pair in "ml T6" "qa T7" "orchestrator T8" "frontend T5" "frontend T9" "orchestrator T10"; do
  cand_role="${pair%% *}"; cand_task="${pair##* }"
  [ "$($A status 2>/dev/null | awk -v t="$cand_task" '$1==t {print $2}')" = "BLOCKED" ] || continue
  git worktree list --porcelain | grep -q "/${cand_task}-" && continue
  SAFE_ROLE="$cand_role"; SAFE_TASK="$cand_task"; break
done

if [ -z "$SAFE_TASK" ]; then
  skip "create: BLOCKED task"      "no BLOCKED task without a worktree to test against"
  skip "start: missing worktree"   "same"
  skip "review: missing worktree"  "same"
  skip "cleanup: missing worktree" "same"
else
  t "create: BLOCKED task ($SAFE_TASK)"      1 $A create "$SAFE_ROLE" "$SAFE_TASK"
  t "start: missing worktree ($SAFE_TASK)"   1 \
    env CAMPUSOS_ALLOW_BLOCKED=1 $A start "$SAFE_ROLE" "$SAFE_TASK"
  t "review: missing worktree ($SAFE_TASK)"  1 $A review "$SAFE_TASK"
  t "cleanup: missing worktree ($SAFE_TASK)" 1 $A cleanup "$SAFE_TASK"
fi
t "cleanup: unknown argument"     1 $A cleanup nosuchthing

# Whatever happened above, the suite must not have created or destroyed a worktree.
t "guards left every worktree alone" 0 \
  bash -c "[ \"$(git worktree list | wc -l)\" = \"$WT_BEFORE\" ]"

echo "Three-track task IDs are known to the tooling"
# T9/T10/T11 were added when the project expanded to all three Cubbie tracks. A task the
# script does not know is refused by create, so an unknown ID would silently block the work.
t "create: T9 is a known task"    1 $A create frontend T9
t "create: T10 is a known task"   1 $A create orchestrator T10
t "create: T11 is a known task"   1 $A create orchestrator T11
# Exit 1 above is the BLOCKED-dependency guard, not an unknown-task error. Distinguish the
# two by their messages: an unknown ID says so explicitly.
t "T9 is not reported unknown"    1 bash -c "$A create frontend T9 2>&1 | grep -q 'unknown task'"
t "T10 is not reported unknown"   1 bash -c "$A create orchestrator T10 2>&1 | grep -q 'unknown task'"
t "T11 is not reported unknown"   1 bash -c "$A create orchestrator T11 2>&1 | grep -q 'unknown task'"
t "create: T0c is a known task"   1 bash -c "$A create orchestrator T0c 2>&1 | grep -q \"unknown task\""
t "T0c is not reported unknown"   1 bash -c "$A create orchestrator T0c 2>&1 | grep -q \"unknown task\""
t "T99 is still reported unknown" 0 bash -c "$A create ml T99 2>&1 | grep -q 'unknown task'"

echo "Review waiver is an honest override"
# An owner may skip the review; they may not record it as a PASS. These assert the
# guards, and that the artefact says what it is.
t "waive: task is required"        1 bash -c "$A waive"
t "waive: unknown task refused"    1 bash -c "$A waive T99 --owner o --reason r"
t "waive: owner is required"       1 bash -c "$A waive T1 --reason r"
t "waive: reason is required"      1 bash -c "$A waive T1 --owner o"
t "waive: unknown argument"        1 bash -c "$A waive T1 --owner o --reason r --bogus x"
t "waive: no worktree is refused"  1 bash -c "$A waive T7 --owner o --reason r"
# And the help must point at it rather than at a way to fake one.
# Static checks on the template, because running a successful waive would write a real
# WAIVER.md into the repo -- a test must not leave a governance artefact behind.
t "waive: template says it is not a PASS" 0 bash -c "grep -q 'This is not a PASS' scripts/agents.sh"
t "waive: template records REVIEW_WAIVED" 0 bash -c "grep -q 'REVIEW_WAIVED' scripts/agents.sh"
t "waive: template claims no verdict"     1 bash -c "grep -Eq 'Verdict.*(PASS|APPROVED)' scripts/agents.sh"
t "waive: documented in help"      0 bash -c "$A help 2>&1 | grep -q 'waive <TASK>'"

echo "CI helper scripts"
t "validate_contracts runs"       0 $PYBIN scripts/ci/validate_contracts.py
if [ -d contracts ] && [ -n "$(ls -A contracts 2>/dev/null)" ]; then
  t "validate_contracts --strict"   0 $PYBIN scripts/ci/validate_contracts.py --strict
else
  t "validate_contracts --strict"   1 $PYBIN scripts/ci/validate_contracts.py --strict
fi
t "secret_scan --tracked"         0 ./scripts/ci/secret_scan.sh --tracked
t "secret_scan rejects bad mode"  2 ./scripts/ci/secret_scan.sh --bogus-mode

echo "Contract validator catches what it is for"
# A validator that silently does nothing is worse than none: it reports success. These
# assert on the three ways that can happen. Built in a temp dir so the repo is untouched.
cdir="$(mktemp -d)/contracts"; mkdir -p "$cdir/examples/thing"
cat > "$cdir/thing.schema.json" <<'JSON'
{"$schema":"https://json-schema.org/draft/2020-12/schema","title":"Thing","type":"object",
 "properties":{"id":{"type":"string"},"n":{"type":"integer","minimum":0}},
 "required":["id","n"],"additionalProperties":false}
JSON
printf '{"id":"a","n":1}\n'  > "$cdir/examples/thing/valid-basic.json"
printf '{"id":"a","n":-5}\n' > "$cdir/examples/thing/invalid-negative.json"
t "fixtures: a correct set passes"  0 $PYBIN scripts/ci/validate_contracts.py --contracts "$cdir"

# An "invalid" fixture the schema happily accepts means the schema constrains nothing.
printf '{"id":"a","n":7}\n' > "$cdir/examples/thing/invalid-negative.json"
t "fixtures: unrejected negative"   1 $PYBIN scripts/ci/validate_contracts.py --contracts "$cdir"
printf '{"id":"a","n":-5}\n' > "$cdir/examples/thing/invalid-negative.json"

# A valid fixture that does not validate means schema and examples have drifted apart.
printf '{"id":"a"}\n' > "$cdir/examples/thing/valid-basic.json"
t "fixtures: broken positive"       1 $PYBIN scripts/ci/validate_contracts.py --contracts "$cdir"
printf '{"id":"a","n":1}\n' > "$cdir/examples/thing/valid-basic.json"

# A schema nobody exercised is a guess.
rm -rf "$cdir/examples/thing"
t "fixtures: none at all"           1 $PYBIN scripts/ci/validate_contracts.py --contracts "$cdir"
mkdir -p "$cdir/examples/thing"
printf '{"id":"a","n":1}\n'  > "$cdir/examples/thing/valid-basic.json"
printf '{"id":"a","n":-5}\n' > "$cdir/examples/thing/invalid-negative.json"

# A $ref pointing at a schema that is not in contracts/ must be a clean error, not a
# traceback and not a silent network fetch.
cat > "$cdir/refs.schema.json" <<'JSON'
{"$schema":"https://json-schema.org/draft/2020-12/schema","$id":"https://example.test/refs.json",
 "title":"Refs","type":"object","properties":{"x":{"$ref":"https://example.test/missing.json"}},
 "required":["x"]}
JSON
mkdir -p "$cdir/examples/refs"
printf '{"x":{}}\n'   > "$cdir/examples/refs/valid-x.json"
printf '{"y":1}\n'    > "$cdir/examples/refs/invalid-missing-x.json"
t "unresolvable \$ref is an error"  1 $PYBIN scripts/ci/validate_contracts.py --contracts "$cdir"
t "unresolvable \$ref: no traceback" 1 bash -c "$PYBIN scripts/ci/validate_contracts.py --contracts '$cdir' 2>&1 | grep -q Traceback"
rm -rf "$cdir/examples/refs" "$cdir/refs.schema.json"

# An OpenAPI document must be checked against the OpenAPI spec, not just parsed as YAML.
# "It is valid YAML with three keys" is not what the T1 acceptance criterion claims.
mkdir -p "$cdir/examples/thing"
cat > "$cdir/svc.openapi.yaml" <<'YAML'
openapi: 3.1.0
info: { title: Svc, version: "1.0.0" }
paths:
  /ping:
    get:
      responses:
        "200": { description: ok }
YAML
t "openapi: a valid document passes"  0 $PYBIN scripts/ci/validate_contracts.py --contracts "$cdir"

# Valid YAML, every top-level key present, still not a legal OpenAPI document.
cat > "$cdir/svc.openapi.yaml" <<'YAML'
openapi: 3.1.0
info: { title: Svc }
paths:
  /ping:
    get:
      responses:
        "200": { description: ok }
YAML
t "openapi: invalid doc is rejected"  1 $PYBIN scripts/ci/validate_contracts.py --contracts "$cdir"

# A $ref into our own contract namespace must resolve from this directory. If it does not,
# a client generating types would silently reach for the network.
cat > "$cdir/svc.openapi.yaml" <<'YAML'
openapi: 3.1.0
info: { title: Svc, version: "1.0.0" }
paths:
  /ping:
    get:
      responses:
        "200":
          description: ok
          content:
            application/json:
              schema: { $ref: "https://campusos.dev/contracts/v1/nope.schema.json" }
YAML
t "openapi: dangling \$ref is an error" 1 $PYBIN scripts/ci/validate_contracts.py --contracts "$cdir"
t "openapi: dangling \$ref: no traceback" 1 bash -c "$PYBIN scripts/ci/validate_contracts.py --contracts '$cdir' 2>&1 | grep -q Traceback"
rm -f "$cdir/svc.openapi.yaml"

# Missing dependencies must be an explicit failure, never a silent skip. CAMPUSOS_REEXEC=1
# suppresses the convenience re-exec so this exercises the real no-dependency path --
# otherwise the thing that makes the command pleasant to run would hide the thing that
# makes it trustworthy.
if python3 -I -c "import jsonschema" 2>/dev/null; then
  skip "deps missing is a hard failure" "system python3 already has jsonschema"
else
  t "deps missing is a hard failure" 1 \
    env CAMPUSOS_REEXEC=1 python3 -I scripts/ci/validate_contracts.py --contracts "$cdir"
  # ...and with the guard off, the same interpreter must find the venv and succeed.
  t "deps missing: re-execs under the venv" 0 \
    python3 scripts/ci/validate_contracts.py --contracts "$cdir"
fi
rm -rf "$(dirname "$cdir")"

echo "Disclosure matrix guards every carrier"
# The ladder was fixed on the agent envelope and reintroduced on the transcript in the
# same commit. These assert the guard itself works, on throwaway copies.
mdir="$(mktemp -d)/contracts"; mkdir -p "$mdir/examples/thing"
cat > "$mdir/thing.schema.json" <<'JSON'
{"$schema":"https://json-schema.org/draft/2020-12/schema","title":"Thing","type":"object",
 "properties":{"id":{"type":"string"},"n":{"type":"integer","minimum":0}},
 "required":["id","n"],"additionalProperties":false}
JSON
printf '{"id":"a","n":1}\n'  > "$mdir/examples/thing/valid-basic.json"
printf '{"id":"a","n":-5}\n' > "$mdir/examples/thing/invalid-negative.json"
t "matrix: an isolated negative passes"  0 $PYBIN scripts/ci/check_disclosure_matrix.py --contracts "$mdir"

# A negative failing for two reasons stays red even if its named constraint is deleted,
# so it quietly stops testing anything.
printf '{"n":-5}\n' > "$mdir/examples/thing/invalid-negative.json"
t "matrix: non-isolated negative caught"  1 $PYBIN scripts/ci/check_disclosure_matrix.py --contracts "$mdir"
printf '{"id":"a","n":-5}\n' > "$mdir/examples/thing/invalid-negative.json"

# A negative that validates is the worst case: it asserts nothing at all.
printf '{"id":"a","n":7}\n' > "$mdir/examples/thing/invalid-negative.json"
t "matrix: unrejected negative caught"    1 $PYBIN scripts/ci/check_disclosure_matrix.py --contracts "$mdir"
printf '{"id":"a","n":-5}\n' > "$mdir/examples/thing/invalid-negative.json"

# A new carrier of the availability envelope that nothing sweeps.
cat > "$mdir/availability.schema.json" <<'JSON'
{"$schema":"https://json-schema.org/draft/2020-12/schema",
 "$id":"https://campusos.dev/contracts/v1/availability.schema.json",
 "title":"Availability","type":"object","properties":{"x":{"type":"string"}}}
JSON
cat > "$mdir/carrier.schema.json" <<'JSON'
{"$schema":"https://json-schema.org/draft/2020-12/schema","title":"Carrier","type":"object",
 "properties":{"a":{"$ref":"https://campusos.dev/contracts/v1/availability.schema.json"}}}
JSON
t "matrix: unswept carrier caught"        1 $PYBIN scripts/ci/check_disclosure_matrix.py --contracts "$mdir"
rm -rf "$(dirname "$mdir")"

echo "Skill privacy audit"
# The Skill folder leaves a private repo for a public one, and emits text a student
# pastes into a group chat. Both are one-way doors.
if [ -d skills/squad-sync ]; then
  t "audit: the real Skill is clean"  0 $PYBIN scripts/ci/audit_skill_privacy.py --skill skills/squad-sync
  adir="$(mktemp -d)/squad-sync"; mkdir -p "$adir"
  cp -R skills/squad-sync/. "$adir/"
  printf '\n<!-- reach me at someone@example.edu -->\n' >> "$adir/SKILL.md"
  t "audit: catches a leaked email"   1 $PYBIN scripts/ci/audit_skill_privacy.py --skill "$adir"
  cp -R skills/squad-sync/. "$adir/"
  printf '\nimport socket\n' >> "$adir/scripts/squad_sync.py"
  t "audit: catches a network import" 1 $PYBIN scripts/ci/audit_skill_privacy.py --skill "$adir"
  rm -rf "$(dirname "$adir")"
else
  skip "audit: the real Skill is clean" "skills/squad-sync is not on this branch yet"
fi

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
  if have claude; then
    t "start: dry run resolves"       0 env CAMPUSOS_DRY_RUN=1 $A start orchestrator T1
  else
    t "start: refuses, claude absent" 1 env CAMPUSOS_DRY_RUN=1 $A start orchestrator T1
    skip "start: dry run resolves" "claude not installed"
  fi
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
