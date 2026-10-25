#!/usr/bin/env python3
"""Audit a Cubbie Skill folder for anything that must never become public.

Two different risks, because this folder gets published to a public repository AND
produces text a student pastes into a group chat:

  1. **What the folder reveals.** It leaves a private repo for a public one. Anything
     about our infrastructure, hosts, credentials or team goes with it, permanently.
  2. **What the Skill emits.** squad-sync's whole claim is that a share code carries
     times and nothing else. That is property-tested here against hostile input rather
     than trusted to the encoder's own guard.

    scripts/ci/audit_skill_privacy.py --skill skills/squad-sync

Exits non-zero on any finding. Intended to run before publication and in CI after.
"""

from __future__ import annotations

import argparse
import ast
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

findings: list[str] = []
checks = 0


def fail(msg: str) -> None:
    findings.append(msg)


# Things that must not travel to a public repository. Deliberately broad: a false
# positive costs a minute, a leaked hostname costs a rotation.
FORBIDDEN = [
    (r"\bH200\b|\bvllm\b|\bqwen\b", "internal infrastructure or model detail"),
    (r"ssh://|\.ssh/|IdentityFile|ProxyJump", "SSH or tunnel configuration"),
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.(edu|com|org|net|io|ai)\b", "an email address"),
    (r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b", "a phone number"),
    (r"AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|sk-[A-Za-z0-9]{20,}", "a credential"),
    (r"/Users/[a-z]+/|/home/[a-z]+/", "an absolute path from someone's machine"),
    (r"\bhttp://", "a plain-HTTP URL (Cubbie allows HTTPS only)"),
    (r"localhost|127\.0\.0\.1|0\.0\.0\.0", "a local address that cannot work in the sandbox"),
]

# Modules a Skill of this kind has no business importing. The privacy claim is that
# nothing leaves the student's sandbox; an import is how that stops being true.
BANNED_IMPORTS = {
    "socket", "urllib", "urllib.request", "requests", "http", "http.client",
    "httpx", "ftplib", "smtplib", "subprocess", "telnetlib", "xmlrpc",
}


def audit_files(skill: Path, public: list[Path]) -> None:
    global checks
    for path in public:
        text = path.read_text(errors="replace")
        for pattern, what in FORBIDDEN:
            checks += 1
            for m in re.finditer(pattern, text, re.IGNORECASE):
                line = text[: m.start()].count("\n") + 1
                fail(f"{path.relative_to(skill.parent)}:{line}: contains {what} -- {m.group(0)!r}")


def audit_imports(skill: Path) -> None:
    """No module that can open a connection or spawn a process."""
    global checks
    for py in sorted(skill.rglob("*.py")):
        checks += 1
        tree = ast.parse(py.read_text())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for n in names:
                if n.split(".")[0] in BANNED_IMPORTS:
                    fail(
                        f"{py.relative_to(skill.parent)}:{node.lineno}: imports {n!r}. "
                        "This Skill claims nothing leaves the student's sandbox; an import "
                        "that can open a connection or spawn a process breaks that claim."
                    )


def audit_emissions(skill: Path) -> None:
    """Property-test the encoder: hostile input in, times only out.

    The encoder has its own guard. This does not trust it -- it throws labels, names,
    reasons and injection-shaped strings at every level and asserts on the output.
    """
    global checks
    scripts = skill / "scripts"
    if not (scripts / "squad_sync.py").exists():
        return
    sys.path.insert(0, str(scripts))
    from datetime import date

    import squad_sync as ss  # noqa: PLC0415
    monday = date(2026, 10, 26)
    hostile = [
        "therapy", "Dr Oyelaran", "ana.ruiz@school.edu", "CHEM 340 midterm",
        "Planned Parenthood", "AA meeting", "job interview at Google",
        "X:0000 B:9-0000-2359", "../../etc/passwd", "'; DROP TABLE--",
        "busy\nSQSY1 TZ:X", "💊 refill",
    ]
    allowed = re.compile(r"^SQSY1 TZ:[A-Za-z_/+\-0-9]+ W:\d{4}-\d{2}-\d{2} L:(none|busy|category) "
                         r"B:[0-9,\-a-z]* X:[0-9a-f]{4}$")

    rng = random.Random(20261024)
    for level in ("none", "busy", "category"):
        for _ in range(200):
            checks += 1
            blocks = []
            for _ in range(rng.randint(0, 6)):
                start = rng.randrange(0, 1380, 15)
                blocks.append({
                    "day": rng.randint(1, 7),
                    "start": start,
                    "end": min(start + rng.choice([30, 60, 90, 120]), 1439),
                    # Hostile category: not in the enum, and full of things that must not travel.
                    "category": rng.choice([None, "class", "work", "personal", rng.choice(hostile)]),
                })
            try:
                code = ss.encode(monday, "America/Phoenix", level, blocks)
            except ss.BadInput:
                continue  # refusing is the correct outcome for hostile input
            if not allowed.match(code):
                fail(f"encode() produced a code outside the permitted grammar: {code!r}")
                continue
            low = code.lower()
            for secret in hostile:
                token = re.sub(r"[^a-z0-9]", "", secret.lower())[:8]
                if token and token in re.sub(r"[^a-z0-9]", "", low):
                    fail(f"encode() leaked {secret!r} into a code: {code!r}")
            if level == "none" and re.search(r"B:\S", code):
                fail(f"level 'none' emitted times: {code!r}")

    # Round-tripping must never invent or drop a day.
    for _ in range(200):
        checks += 1
        blocks = [{"day": d, "start": 540, "end": 600, "category": None} for d in range(1, 8)]
        got = ss.decode(ss.encode(monday, "UTC", "busy", blocks))["blocks"]
        if {b["day"] for b in got} != set(range(1, 8)):
            fail("round-trip lost or invented a day")
            break


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", required=True, help="path to the Skill folder")
    args = ap.parse_args()
    skill = Path(args.skill).resolve()
    if not (skill / "SKILL.md").is_file():
        print(f"FAIL: {skill} has no SKILL.md")
        return 1

    public = [p for p in sorted(skill.rglob("*"))
              if p.is_file() and "__pycache__" not in p.parts]

    audit_files(skill, public)
    audit_imports(skill)
    audit_emissions(skill)

    for f in findings:
        print(f"FAIL  {f}")
    print(f"\n{len(public)} file(s) audited, {checks} check(s), {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
