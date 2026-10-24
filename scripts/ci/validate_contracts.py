#!/usr/bin/env python3
"""Validate the shared contracts in contracts/.

Three agents build against these files in parallel from sessions with no shared memory,
so a malformed or self-contradictory contract is one of the most expensive failures
available to this project. This check runs in CI and in T1's definition of done.

What it checks:
  1. every contract file parses (JSON Schema, OpenAPI YAML);
  2. every schema is itself a legal JSON Schema;
  3. the agent envelope carries the fields needed to route a message safely;
  4. each schema has at least one valid and one deliberately invalid example fixture,
     the valid one validates, and **the invalid one is actually rejected**.

Exits 0 and says so plainly when contracts/ does not exist yet -- a missing contract
before T1 is the expected state, not a failure.

Dependencies (PyYAML, jsonschema) are required whenever there is something that needs
them. A missing dependency is a hard FAIL, never a silent skip: a validator that quietly
does nothing is worse than no validator, because it reports success.

    ./scripts/ci/validate_contracts.py            # from the repo's .venv
    .venv/bin/python scripts/ci/validate_contracts.py

    --strict            fail if contracts/ is missing or empty (use after T1 is DONE)
    --contracts <dir>   check this directory instead of contracts/ (used by the tests)

Set up the environment with:
    uv venv --python 3.11 .venv && uv pip install --python .venv/bin/python pyyaml jsonschema
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"
EXAMPLES = CONTRACTS / "examples"

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

SETUP_HINT = (
    "install it with:  uv pip install --python .venv/bin/python pyyaml jsonschema\n"
    "         then run: .venv/bin/python scripts/ci/validate_contracts.py"
)

errors: list[str] = []
warnings: list[str] = []
checked = 0


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict | None:
    global checked
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        errors.append(f"{rel(path)}: invalid JSON -- {exc}")
        return None
    checked += 1
    if not isinstance(data, dict):
        errors.append(f"{rel(path)}: top level must be an object")
        return None
    return data


def check_schema_shape(path: Path, data: dict) -> None:
    """House rules that keep a schema usable by an agent reading it cold."""
    if "$schema" not in data:
        warnings.append(f"{rel(path)}: no $schema key; declare the JSON Schema draft")
    if "title" not in data:
        warnings.append(f"{rel(path)}: no title")
    if data.get("type") == "object" and "properties" not in data:
        errors.append(f"{rel(path)}: type 'object' with no properties")

    if path.name == "agent-protocol.schema.json":
        props = set((data.get("properties") or {}).keys())
        missing = REQUIRED_ENVELOPE_FIELDS - props
        if missing:
            errors.append(
                f"{rel(path)}: agent envelope is missing required field(s): "
                f"{', '.join(sorted(missing))}. These are needed to route a message safely "
                "(identity, authority, disclosure limit, traceability)."
            )
        disclosure = (data.get("properties") or {}).get("disclosure_level") or {}
        if "enum" not in disclosure:
            errors.append(
                f"{rel(path)}: disclosure_level must be an enum. The privacy tests in T2, T4 "
                "and T5 are written against these values."
            )


def check_yaml(path: Path) -> None:
    global checked
    try:
        import yaml
    except ImportError:
        errors.append(
            f"{rel(path)}: cannot validate -- PyYAML is not installed, so this OpenAPI "
            f"document was NOT checked.\n         {SETUP_HINT}"
        )
        return
    try:
        data = yaml.safe_load(path.read_text())
    except Exception as exc:  # noqa: BLE001 - surface any parser error verbatim
        errors.append(f"{rel(path)}: invalid YAML -- {exc}")
        return
    checked += 1
    if not isinstance(data, dict):
        errors.append(f"{rel(path)}: OpenAPI document must be a mapping at the top level")
        return
    if "openapi" in path.name:
        for key in ("openapi", "info", "paths"):
            if key not in data:
                errors.append(f"{rel(path)}: OpenAPI doc missing '{key}'")


def build_registry(schemas: list[tuple[Path, dict]]):
    """Resolve $refs between contract files offline.

    The schemas reference each other by their public $id. Without a registry, jsonschema
    would try to fetch those URLs over the network and the check would fail in CI for a
    reason that has nothing to do with the contracts.
    """
    try:
        from referencing import Registry, Resource
    except ImportError:
        errors.append(
            "cannot resolve $refs between contracts -- the 'referencing' package is missing "
            f"(it ships with jsonschema).\n         {SETUP_HINT}"
        )
        return None
    registry = Registry()
    for path, schema in schemas:
        if "$id" in schema:
            registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    return registry


def check_fixtures(schema_path: Path, schema: dict, registry=None) -> None:
    """Each schema needs a valid fixture AND one that is correctly rejected.

    A schema nobody has exercised is a guess. The negative fixture is the one that
    actually matters: it proves the schema constrains something.
    """
    try:
        import jsonschema
    except ImportError:
        errors.append(
            f"{rel(schema_path)}: cannot validate -- jsonschema is not installed, so this "
            f"schema and its fixtures were NOT checked.\n         {SETUP_HINT}"
        )
        return

    stem = schema_path.name.removesuffix(".schema.json")
    folder = EXAMPLES / stem

    validator_cls = jsonschema.validators.validator_for(schema)
    try:
        validator_cls.check_schema(schema)
    except jsonschema.exceptions.SchemaError as exc:
        errors.append(f"{rel(schema_path)}: not a legal JSON Schema -- {exc.message}")
        return
    validator = validator_cls(schema, registry=registry) if registry else validator_cls(schema)

    if not folder.is_dir():
        errors.append(
            f"{rel(schema_path)}: no example fixtures. Create {rel(folder)}/valid-*.json "
            "and invalid-*.json -- a schema with no exercised examples is a guess."
        )
        return

    valid = sorted(folder.glob("valid-*.json"))
    invalid = sorted(folder.glob("invalid-*.json"))
    if not valid:
        errors.append(f"{rel(folder)}: no valid-*.json fixture")
    if not invalid:
        errors.append(
            f"{rel(folder)}: no invalid-*.json fixture. The deliberately-invalid case is "
            "what proves the schema rejects anything at all."
        )

    def unresolved(fixture: Path, exc: Exception) -> None:
        # A $ref to a schema that is not in contracts/ would otherwise be fetched over the
        # network, or blow up with a traceback. Both are wrong: report it as the contract bug
        # it is, and name the ref so it can be fixed.
        errors.append(
            f"{rel(fixture)}: {schema_path.name} has an unresolvable $ref -- {exc}. Every "
            "referenced schema must be a contract in this directory, declaring that exact $id."
        )

    for fixture in valid:
        data = load_json(fixture)
        if data is None:
            continue
        try:
            found = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
        except Exception as exc:  # noqa: BLE001 - unresolvable $ref and friends
            unresolved(fixture, exc)
            continue
        if found:
            first = found[0]
            where = "/".join(str(p) for p in first.path) or "(root)"
            errors.append(
                f"{rel(fixture)}: expected to VALIDATE against {schema_path.name} but failed "
                f"at {where}: {first.message}"
            )

    for fixture in invalid:
        data = load_json(fixture)
        if data is None:
            continue
        try:
            accepted = validator.is_valid(data)
        except Exception as exc:  # noqa: BLE001
            unresolved(fixture, exc)
            continue
        if accepted:
            errors.append(
                f"{rel(fixture)}: expected to be REJECTED by {schema_path.name}, but it "
                "validated. Either the fixture is not actually invalid, or the schema is "
                "too permissive -- both are bugs other agents will build on."
            )


def main() -> int:
    global CONTRACTS, EXAMPLES
    strict = "--strict" in sys.argv
    if "--contracts" in sys.argv:
        CONTRACTS = Path(sys.argv[sys.argv.index("--contracts") + 1]).resolve()
        EXAMPLES = CONTRACTS / "examples"

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

    schemas: list[tuple[Path, dict]] = []

    for path in files:
        # Fixtures are instances, not schemas. They are checked against their schema below.
        if EXAMPLES in path.parents:
            if path.suffix != ".json":
                warnings.append(f"{rel(path)}: unexpected non-JSON file among the fixtures")
            continue

        if path.suffix == ".json":
            data = load_json(path)
            if data is None:
                continue
            check_schema_shape(path, data)
            if path.name.endswith(".schema.json"):
                schemas.append((path, data))
            else:
                warnings.append(
                    f"{rel(path)}: name it <thing>.schema.json so its fixtures can be found"
                )
        elif path.suffix in (".yaml", ".yml"):
            check_yaml(path)
        elif path.suffix == ".md":
            continue
        else:
            warnings.append(f"{rel(path)}: unrecognised contract file type")

    registry = build_registry(schemas)
    for schema_path, schema in schemas:
        check_fixtures(schema_path, schema, registry)

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")

    print(
        f"\n{checked} contract file(s) parsed, {len(schemas)} schema(s) exercised against "
        f"fixtures, {len(errors)} error(s), {len(warnings)} warning(s)"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
