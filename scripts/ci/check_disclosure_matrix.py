#!/usr/bin/env python3
"""Exhaustively check the disclosure ladder, everywhere it appears.

Why this exists as a committed check rather than an ad-hoc probe: the ladder was fixed on
the agent envelope and then immediately reintroduced on `transcript[].disclosed`, in the
same commit, because a new carrier for an availability envelope is a new place for the
ladder to be bypassed and nothing was watching for that. A review caught it. A review is
not a control.

So the rule is mechanical: **every carrier of a disclosure level is swept exhaustively.**
Adding a third carrier without registering it here should be hard to do silently -- see
`test_every_carrier_is_registered`, which fails when a schema grows a new nested
availability reference that this file does not know about.

Three checks:
  1. the ladder matrix -- every level combination accepts iff it is non-increasing;
  2. fixture isolation -- each invalid-*.json fails for exactly ONE reason, so that
     removing the constraint it targets actually turns it green;
  3. named regressions -- the specific states two reviews found, kept as assertions.

    .venv/bin/python scripts/ci/check_disclosure_matrix.py
    --contracts <dir>   check this directory instead of contracts/
"""

from __future__ import annotations

import copy
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEVELS = ["none", "free_busy", "category", "full"]
RANK = {lv: i for i, lv in enumerate(LEVELS)}

failures: list[str] = []
checks = 0


def fail(msg: str) -> None:
    failures.append(msg)


def slots_for(level: str) -> list[dict]:
    """The richest slot list each level permits, so the sweep tests a real payload."""
    if level == "none":
        return []
    slot = {"start": "2026-10-27T21:00:00Z", "end": "2026-10-27T23:00:00Z", "state": "busy"}
    if level in ("category", "full"):
        slot["category"] = "personal"
    if level == "full":
        slot["label"] = "therapy"
    return [slot]


def load(contracts: Path):
    try:
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource
    except ImportError:
        print("FAIL: jsonschema is not installed, so the disclosure matrix was NOT checked.")
        print("      uv pip install --python .venv/bin/python pyyaml jsonschema openapi-spec-validator")
        raise SystemExit(1)

    schemas = {}
    for p in sorted(contracts.glob("*.schema.json")):
        schemas[p.name] = json.loads(p.read_text())
    registry = Registry().with_resources(
        (s["$id"], Resource.from_contents(s)) for s in schemas.values() if "$id" in s
    )
    return schemas, registry, Draft202012Validator


def sweep_agent_envelope(contracts, schemas, registry, V) -> None:
    """Carrier 1: scope ceiling >= message level >= payload.availability level."""
    global checks
    name = "agent-protocol.schema.json"
    if name not in schemas:
        return
    base_path = contracts / "examples/agent-protocol/valid-propose.json"
    if not base_path.exists():
        fail(f"{name}: no valid-propose.json to sweep from")
        return
    base = json.loads(base_path.read_text())
    v = V(schemas[name], registry=registry)
    for ceiling, outer, inner in itertools.product(LEVELS, repeat=3):
        d = copy.deepcopy(base)
        d["scope"]["max_disclosure_level"] = ceiling
        d["disclosure_level"] = outer
        d["payload"]["availability"]["disclosure_level"] = inner
        d["payload"]["availability"]["slots"] = slots_for(inner)
        want = RANK[ceiling] >= RANK[outer] >= RANK[inner]
        checks += 1
        if v.is_valid(d) != want:
            verb = "ACCEPTED" if not want else "REJECTED"
            fail(
                f"agent envelope {verb} ceiling={ceiling} message={outer} nested={inner}; "
                f"the ladder must be non-increasing"
            )


def sweep_transcript(contracts, schemas, registry, V) -> None:
    """Carrier 2: transcript entry level >= its disclosed.availability level."""
    global checks
    name = "negotiation-state.schema.json"
    if name not in schemas:
        return
    base_path = contracts / "examples/negotiation-state/valid-converged.json"
    if not base_path.exists():
        fail(f"{name}: no valid-converged.json to sweep from")
        return
    base = json.loads(base_path.read_text())
    if not base.get("transcript") or "availability" not in base["transcript"][0].get("disclosed", {}):
        fail("valid-converged.json: transcript[0].disclosed.availability is required for this sweep")
        return
    v = V(schemas[name], registry=registry)
    for entry, inner in itertools.product(LEVELS, repeat=2):
        d = copy.deepcopy(base)
        t = d["transcript"][0]
        t["disclosure_level"] = entry
        t["disclosed"]["availability"]["disclosure_level"] = inner
        t["disclosed"]["availability"]["slots"] = slots_for(inner)
        want = RANK[entry] >= RANK[inner]
        checks += 1
        if v.is_valid(d) != want:
            verb = "ACCEPTED" if not want else "REJECTED"
            fail(
                f"transcript entry {verb} level={entry} nested={inner}; a transcript entry may "
                f"not carry an availability envelope above its own level"
            )


def check_every_carrier_is_registered(schemas) -> None:
    """Catch a new carrier of the availability envelope that nothing sweeps.

    Greps every schema for a $ref to the availability contract and compares the set of
    locations against the two this file sweeps. A third one is not necessarily wrong --
    but it must be swept, and the point is that adding it silently should fail here.
    """
    global checks
    checks += 1
    known = {
        ("agent-protocol.schema.json", "properties/payload/properties/availability"),
        ("negotiation-state.schema.json",
         "properties/transcript/items/properties/disclosed/properties/availability"),
    }
    found = set()

    def walk(node, path, fname):
        if isinstance(node, dict):
            if node.get("$ref", "").endswith("availability.schema.json"):
                found.add((fname, "/".join(path)))
            for k, v in node.items():
                walk(v, path + [k], fname)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, path + [str(i)], fname)

    for fname, schema in schemas.items():
        if fname == "availability.schema.json":
            continue
        walk(schema, [], fname)

    for carrier in sorted(found - known):
        fail(
            f"{carrier[0]}: a new availability carrier at {carrier[1]} is not swept by this "
            f"check. Every carrier needs its own ladder conditionals and its own sweep -- "
            f"this is exactly how the transcript leak was introduced."
        )


def check_fixture_isolation(contracts, schemas, registry, V) -> None:
    """Each invalid fixture must fail for exactly one reason.

    A negative fixture that also happens to be missing an unrelated required field stays
    red even if the constraint it is named for is deleted, so it silently stops testing
    anything. Exactly one error means deleting that constraint turns it green, and the
    validator's unrejected-negative check then fires.
    """
    global checks
    examples = contracts / "examples"
    if not examples.is_dir():
        return
    for folder in sorted(p for p in examples.iterdir() if p.is_dir()):
        sname = f"{folder.name}.schema.json"
        if sname not in schemas:
            continue
        v = V(schemas[sname], registry=registry)
        for fixture in sorted(folder.glob("invalid-*.json")):
            checks += 1
            errors = list(v.iter_errors(json.loads(fixture.read_text())))
            if len(errors) == 1:
                continue
            rel = fixture.relative_to(ROOT) if ROOT in fixture.parents else fixture
            if not errors:
                fail(f"{rel}: expected to be rejected, but it validated")
                continue
            where = "; ".join(
                f"{'/'.join(str(x) for x in e.path) or '(root)'}: {e.message[:70]}"
                for e in errors[:4]
            )
            fail(
                f"{rel}: fails for {len(errors)} reasons, must be exactly 1 so that removing "
                f"the targeted constraint turns it green -- {where}"
            )


def check_named_regressions(contracts, schemas, registry, V) -> None:
    """The exact states the reviews found. Kept so they cannot come back quietly."""
    global checks
    name = "negotiation-state.schema.json"
    if name not in schemas:
        return
    v = V(schemas[name], registry=registry)
    pend_p = contracts / "examples/negotiation-state/valid-awaiting-approval.json"
    if not pend_p.exists():
        return
    pend = json.loads(pend_p.read_text())

    # Review 2, F1: a viewer who has approved while peers have not.
    checks += 1
    done = copy.deepcopy(pend)
    done["viewer"]["awaiting_me"] = False
    done["viewer"]["state"] = "accepted"
    done["participants"][0]["state"] = "accepted"
    done["pending_approvals"] = []
    errs = [f"{'/'.join(str(x) for x in e.path) or '(root)'}: {e.message}" for e in v.iter_errors(done)]
    if errs:
        fail(
            "a viewer who has already approved, while peers are still deciding, must be "
            f"representable with an empty pending_approvals -- rejected with: {errs}"
        )

    # Review 2, F1 converse: the flag may not disagree with the array.
    checks += 1
    drift = copy.deepcopy(pend)
    drift["viewer"]["awaiting_me"] = False
    if v.is_valid(drift):
        fail("awaiting_me=false with a populated pending_approvals must be rejected")

    # Review 2, F3: prose in a transcript entry.
    conv_p = contracts / "examples/negotiation-state/valid-converged.json"
    if conv_p.exists():
        checks += 1
        prose = json.loads(conv_p.read_text())
        prose["transcript"][0]["disclosed"]["summary"] = "Ana has therapy at 2pm"
        if v.is_valid(prose):
            fail("free-text prose in transcript[].disclosed must be rejected; use summary_code")


def main() -> int:
    contracts = ROOT / "contracts"
    if "--contracts" in sys.argv:
        contracts = Path(sys.argv[sys.argv.index("--contracts") + 1]).resolve()
    if not contracts.is_dir():
        print("SKIP: contracts/ does not exist yet -- it is produced by T1.")
        return 0

    schemas, registry, V = load(contracts)
    if not schemas:
        print("SKIP: no schemas in contracts/ yet.")
        return 0

    sweep_agent_envelope(contracts, schemas, registry, V)
    sweep_transcript(contracts, schemas, registry, V)
    check_every_carrier_is_registered(schemas)
    check_fixture_isolation(contracts, schemas, registry, V)
    check_named_regressions(contracts, schemas, registry, V)

    for f in failures:
        print(f"FAIL  {f}")
    print(f"\n{checks} disclosure check(s) run, {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
