#!/usr/bin/env bash
#
# secret_scan.sh — conservative secret scan for CampusOS.
#
#   ./scripts/ci/secret_scan.sh --staged   # staged files only (used by the pre-commit hook)
#   ./scripts/ci/secret_scan.sh --tracked  # all tracked files (used by CI)
#
# This is a deliberately simple safety net with no external dependency, not a
# replacement for a real scanner. For stronger coverage add gitleaks or trufflehog
# to CI; this catches the mistakes that actually happen during a hackathon.
#
# To allow a genuine false positive, put this marker on the same line:
#   pragma: allowlist secret
#
set -uo pipefail

MODE="${1:---staged}"
case "$MODE" in
  --staged)  FILES="$(git diff --cached --name-only --diff-filter=ACM)" ;;
  --tracked) FILES="$(git ls-files)" ;;
  *) echo "usage: $0 [--staged|--tracked]" >&2; exit 2 ;;
esac

[ -z "$FILES" ] && { echo "secret-scan: no files to scan"; exit 0; }

FAIL=0

# ---- 1. filenames that should never be committed -----------------------------
while IFS= read -r f; do
  [ -z "$f" ] && continue
  case "$f" in
    *.env|.env|.env.*)
      case "$f" in *.example|*.sample|*.template) continue ;; esac
      echo "BLOCKED  $f  — environment files must not be committed (commit .env.example instead)"
      FAIL=1 ;;
    *.pem|*.p12|*.pfx|*.jks|id_rsa|id_dsa|id_ecdsa|id_ed25519|*_rsa|*.keystore)
      echo "BLOCKED  $f  — looks like a private key or keystore"
      FAIL=1 ;;
    *credentials.json|*service-account*.json|.netrc|.pgpass)
      echo "BLOCKED  $f  — looks like a credentials file"
      FAIL=1 ;;
    *.ckpt|*.safetensors|*.bin|*.pt|*.pth|*.gguf)
      echo "BLOCKED  $f  — model weights must not be committed (use the cluster or object storage)"
      FAIL=1 ;;
  esac
done <<< "$FILES"

# ---- 2. high-confidence credential patterns in file contents -----------------
# One pattern per line: <label>|<ERE>
PATTERNS='AWS access key id|AKIA[0-9A-Z]{16}
Private key block|-----BEGIN [A-Z ]*PRIVATE KEY-----
GitHub token|gh[pousr]_[A-Za-z0-9]{30,}
OpenAI API key|sk-[A-Za-z0-9]{32,}
Anthropic API key|sk-ant-[A-Za-z0-9_-]{20,}
Slack token|xox[baprs]-[A-Za-z0-9-]{10,}
HuggingFace token|hf_[A-Za-z0-9]{30,}
Google API key|AIza[0-9A-Za-z_-]{35}
Hardcoded secret assignment|(api[_-]?key|secret[_-]?key|client[_-]?secret|access[_-]?token|auth[_-]?token|api[_-]?secret|app[_-]?secret|private[_-]?key|passphrase|password|passwd|token|secret|credential)[[:space:]]*[:=][[:space:]]*.{0,2}[A-Za-z0-9/+_-]{16,}
Bearer credential|[Bb]earer[[:space:]]+[A-Za-z0-9._~+/-]{20,}'

while IFS= read -r f; do
  [ -z "$f" ] && continue
  [ -f "$f" ] || continue
  # skip binaries and this scanner's own pattern list
  case "$f" in scripts/ci/secret_scan.sh) continue ;; esac
  grep -Iq . "$f" 2>/dev/null || continue

  while IFS= read -r pat; do
    [ -z "$pat" ] && continue
    label="${pat%%|*}"; regex="${pat#*|}"
    hits="$(grep -nEi "$regex" "$f" 2>/dev/null | grep -v 'pragma: allowlist secret' || true)"
    if [ -n "$hits" ]; then
      echo "$hits" | while IFS= read -r h; do
        echo "BLOCKED  $f:${h%%:*}  — possible $label"
      done
      FAIL=1
    fi
  done <<< "$PATTERNS"
done <<< "$FILES"

if [ "$FAIL" != "0" ]; then
  cat >&2 <<'MSG'

secret-scan FAILED.

Do not bypass this with --no-verify. Instead:
  - move the value into an environment variable and commit .env.example
  - if it is a genuine false positive, add on that line:  pragma: allowlist secret
  - if a secret was already committed, it must be rotated — removing it from the
    diff does not remove it from history.

MSG
  exit 1
fi

echo "secret-scan: clean"
