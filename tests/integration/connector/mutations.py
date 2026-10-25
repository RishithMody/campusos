"""Mutation harness for the connector boundary suite (T7c).

Run manually; pytest does not collect it. Review attempt 1 reported mutation counts from
a scratch directory that no longer existed, so the numbers could not be checked. This
makes them reproducible:

    PYTHONPATH=. python tests/integration/connector/mutations.py

Each mutation is applied to a throwaway copy of the repository in a temporary directory.
The working tree is never modified. A mutation that leaves the suite green is a hole in
the tests, not a fact about the code -- except where it is genuinely equivalent, and the
burden of proving that is on whoever claims it.
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
# The mutated surfaces are no longer all covered by the connector suite alone: the
# audience-identity gate is pinned there, but the publisher latch lives in the groupchat
# suite and the channel gate in the backend one. A mutation is only "killed" if the whole
# set of suites that cover it runs.
SUITES = ("tests/integration/connector/", "tests/groupchat/", "tests/backend/")
SKIP = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache"}

# (id, file, what it removes, old text, new text)
MUTATIONS = [
    (
        "M1",
        "backend/service.py",
        "student() stops refusing bot credentials",
        'if student is None or self.identity.kind == "bot":',
        "if student is None:",
    ),
    (
        "M2",
        "backend/service.py",
        "channel ownership check dropped from channel_summary",
        "            or channel.bot != self.identity.subject\n",
        "",
    ),
    (
        "M3",
        "backend/service.py",
        "summary served for any binding status, not only confirmed",
        'if not binding or binding["status"] != "confirmed":',
        "if not binding:",
    ),
    (
        "M4",
        "groupchat/render.py",
        "renderer sentence drifts from the frozen table",
        '"converged": "Locked in: {agreed_slot}.",',
        '"converged": "Locked in! {agreed_slot}.",',
    ),
    (
        "M5",
        "backend/channels/discord.py",
        "a non-200 from Discord is treated as success",
        "                if response.status_code != 200:",
        "                if False:",
    ),
    (
        "M6",
        "backend/service.py",
        "guild claim no longer required to register a channel",
        'if self.identity.kind != "bot" or not self.identity.guild:',
        'if self.identity.kind != "bot":',
    ),
    # M7 is an *equivalent* mutant, demonstrated rather than assumed (T12, 2026-10-25):
    # with the isinstance guard removed, every non-list body -- {}, {"a": 1}, "string", 7,
    # None, [{"bad": 1}] -- still raises Problem(503), either through the surrounding
    # `except (KeyError, TypeError, ValueError)` or through the bot-not-in-`visible` check.
    # The guard is defence in depth and states the intent locally; it changes no outcome.
    # It survives because there is no behaviour left to observe, not because a test is
    # missing. Keep it in the list: if the except clause is ever narrowed, it will start
    # failing, and that is exactly when someone needs to know.
    (
        "M7",
        "backend/channels/discord.py",
        "malformed member page guard removed (equivalent -- see note above)",
        "                if not isinstance(members, list):",
        "                if False:",
    ),
    (
        "M8",
        "backend/channels/discord.py",
        "non-numeric channel and guild ids accepted",
        "        if not channel.isdigit() or not guild.isdigit():",
        "        if False:",
    ),
    (
        "M9",
        "backend/channels/discord.py",
        "missing bot token no longer fails closed",
        "        if not self.token:",
        "        if False:",
    ),
    (
        "M10",
        "backend/channels/discord.py",
        "the bot's own VIEW_CHANNEL check removed",
        "        if not can_view(membership, server, room):\n            raise Problem(403)",
        "        if False:\n            raise Problem(403)",
    ),
    (
        "M11",
        "backend/service.py",
        "channel guild binding no longer checked on summary",
        "            or channel.guild != self.identity.guild\n",
        "",
    ),
    # T12. The audience-identity gate and the publisher latch.
    (
        "M12",
        "backend/service.py",
        "re-consent compares headcount again, not audience identity",
        'if self.audience_identity(audience) != binding.get("audience"):',
        'if audience.size > binding["size"]:',
    ),
    (
        "M13",
        "backend/service.py",
        "an audience that cannot be identified no longer fails closed",
        "        if not audience.fingerprint:",
        "        if False:",
    ),
    (
        "M14",
        "backend/service.py",
        "bind records no audience identity to compare against",
        '            "audience": self.audience_identity(audience),\n',
        "",
    ),
    (
        "M15",
        "backend/channels/discord.py",
        "the fingerprint ignores who is in the room",
        '    for viewer in sorted(viewers):\n        digest.update(f"{len(viewer)}:{viewer}\\n".encode())',
        '    for viewer in sorted(viewers):\n        digest.update(b"")',
    ),
    (
        "M16",
        "groupchat/publisher.py",
        "a refused publisher is reusable; the stop is advisory again",
        "        if self.stopped:\n            return False\n",
        "",
    ),
]


def apply(target: Path, path: str, old: str, new: str) -> None:
    source = target / path
    text = source.read_text()
    if text.count(old) != 1:
        raise SystemExit(f"mutation does not apply uniquely in {path}: {text.count(old)} match(es)")
    source.write_text(text.replace(old, new))


def run_suite(cwd: Path, python: str) -> tuple[bool, str]:
    result = subprocess.run(  # noqa: S603
        [python, "-m", "pytest", *SUITES, "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=cwd,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(cwd), "PATH": "/usr/bin:/bin", "HOME": str(cwd)},
    )
    return result.returncode == 0, (result.stdout.strip().splitlines() or [""])[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable, help="interpreter with the test deps")
    parser.add_argument("--only", help="run a single mutation id, e.g. M7")
    args = parser.parse_args()

    survivors = []
    with tempfile.TemporaryDirectory(prefix="t7c-mutations-") as tmp:
        pristine = Path(tmp) / "repo"
        shutil.copytree(ROOT, pristine, ignore=shutil.ignore_patterns(*SKIP))
        ok, line = run_suite(pristine, args.python)
        print(f"{'baseline':6} {'':58} {'PASS' if ok else 'FAIL'}  {line}")
        if not ok:
            print("baseline is not green; fix that before trusting any mutation result")
            return 2
        for ident, path, what, old, new in MUTATIONS:
            if args.only and ident != args.only:
                continue
            target = Path(tmp) / ident
            shutil.copytree(pristine, target)
            apply(target, path, old, new)
            ok, line = run_suite(target, args.python)
            verdict = "SURVIVED" if ok else "killed"
            if ok:
                survivors.append((ident, what))
            print(f"{ident:6} {what:58} {verdict:8}  {line}")
            shutil.rmtree(target)

    if survivors:
        print("\nSurvivors -- each is a hole in the suite unless proven equivalent:")
        for ident, what in survivors:
            print(f"  {ident}  {what}")
        return 1
    print("\nAll mutations killed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
