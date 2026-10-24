#!/usr/bin/env python3
"""Validate the shared contracts in contracts/.

Three agents build against these files in parallel from sessions with no shared memory,
so a malformed or self-contradictory contract is one of the most expensive failures
available to this project. This check runs in CI and in T1's definition of done.

Exits 0 and says so plainly when contracts/ does not exist yet -- a missing contract
before T1 is the expected state, not a failure.

Usage:
    ./scripts/ci/validate_contracts.py [--strict]

    --strict  fail if contracts/ is missing or empty (use after T1 is DONE)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"

# Fields the agent-protocol envelope must carry. Derived from the privacy model: a message
# is only safe to route if we know who sent it, who they speak for, how far their authority
# goes, and how much they are permitted to disclose.
REQUIRED_ENVELOPE_FIELDS = {
    "sender",
    "represented_student",
    "scope",
    "disclosure_level",
    "intent",
    "payload",
    "trace_id",
}

errors: list[str] = []
warnings: list[str] = []
checked = 0


def check_json_schema(path: Path) -> dict | None:
    global checked
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        errors.append(f"{path.relative_to(ROOT)}: invalid JSON -- {exc}")
        return None
    checked += 1

    if not isinstance(data, dict):
        errors.append(f"{path.relative_to(ROOT)}: top level must be an object")
        return None
    if "$schema" not in data:
        warnings.append(f"{path.relative_to(ROOT)}: no $schema key; declare the JSON Schema draft")
    if "title" not in data:
        warnings.append(f"{path.relative_to(ROOT)}: no title")
    if data.get("type") == "object" and "properties" not in data:
        errors.append(f"{path.relative_to(ROOT)}: type 'object' with no properties")
    return data


def check_yaml(path: Path) -> dict | None:
    global checked
    try:
        import yaml  # type: ignore
    except ImportError:
        warnings.append(
            f"{path.relative_to(ROOT)}: SKIPPED -- PyYAML not installed "
            "(pip install pyyaml to validate this file)"
        )
        return None
    try:
        data = yaml.safe_load(path.read_text())
    except Exception as exc:  # noqa: BLE001 - surface any parser error verbatim
        errors.append(f"{path.relative_to(ROOT)}: invalid YAML -- {exc}")
        return None
    checked += 1
    return data if isinstance(data, dict) else None


def main() -> int:
    strict = "--strict" in sys.argv

    if not CONTRACTS.is_dir():
        msg = "contracts/ does not exist yet -- it is produced by T1 (architecture and contracts)."
        if strict:
            print(f"FAIL: {msg}")
            return 1
        print(f"SKIP: {msg}")
        return 0

    files = sorted(p for p in CONTRACTS.rglob("*") if p.is_file())
    if not files:
        msg = "contracts/ is empty -- T1 has not published the contracts yet."
        if strict:
            print(f"FAIL: {msg}")
            return 1
        print(f"SKIP: {msg}")
        return 0

    for path in files:
        if path.suffix == ".json":
            data = check_json_schema(path)
            if data and path.name == "agent-protocol.schema.json":
                props = set((data.get("properties") or {}).keys())
                missing = REQUIRED_ENVELOPE_FIELDS - props
                if missing:
                    errors.append(
                        f"{path.relative_to(ROOT)}: agent envelope is missing required "
                        f"field(s): {', '.join(sorted(missing))}. These are needed to route a "
                        "message safely (identity, authority, disclosure limit, traceability)."
                    )
                disclosure = (data.get("properties") or {}).get("disclosure_level") or {}
                if "enum" not in disclosure:
                    errors.append(
                        f"{path.relative_to(ROOT)}: disclosure_level must be an enum. "
                        "The privacy tests in T2, T4, and T5 are written against these values."
                    )
        elif path.suffix in (".yaml", ".yml"):
            data = check_yaml(path)
            if data and "openapi" in path.name:
                for key in ("openapi", "info", "paths"):
                    if key not in data:
                        errors.append(f"{path.relative_to(ROOT)}: OpenAPI doc missing '{key}'")
        elif path.suffix == ".md":
            continue
        else:
            warnings.append(f"{path.relative_to(ROOT)}: unrecognised contract file type")

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")

    print(f"\n{checked} contract file(s) parsed, {len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
