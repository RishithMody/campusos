import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from pydantic import BaseModel, ValidationError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from backend.common import Problem, instant
from backend.protocol.agent_protocol_models import AgentToAgentMessageEnvelopeV1
from backend.protocol.availability_models import AvailabilityEnvelopeV1
from backend.protocol.negotiation_state_models import NegotiationStateV1

ROOT = Path(__file__).resolve().parents[2] / "contracts"
SCHEMAS = {p.stem: json.loads(p.read_text()) for p in ROOT.glob("*.schema.json")}
REGISTRY = Registry().with_resources(
    (s["$id"], Resource.from_contents(s)) for s in SCHEMAS.values()
)
API = yaml.safe_load((ROOT / "api.openapi.yaml").read_text())
REGISTRY = REGISTRY.with_resource(
    "urn:campusos:api", Resource.from_contents(API, default_specification=DRAFT202012)
)

LEVELS = ("none", "free_busy", "category", "full")


def validate(value: Any, schema: dict[str, Any], status: int = 400) -> None:
    validator = Draft202012Validator(schema, registry=REGISTRY, format_checker=FormatChecker())
    if not validator.is_valid(value):
        raise Problem(status, "Invalid request" if status == 400 else "Disclosure violation")


def contract(value: Any, name: str, status: int = 400) -> None:
    validate(value, SCHEMAS[name + ".schema"], status)
    models: dict[str, type[BaseModel]] = {
        "availability": AvailabilityEnvelopeV1,
        "agent-protocol": AgentToAgentMessageEnvelopeV1,
        "negotiation-state": NegotiationStateV1,
    }
    try:
        models[name].model_validate(value)
    except ValidationError:
        raise Problem(status, "Invalid request") from None


def temporal(value: dict[str, Any]) -> None:
    try:
        if "start" in value and "end" in value:
            if instant(value["start"]) >= instant(value["end"]):
                raise ValueError("invalid interval")
        if "timezone" in value:
            ZoneInfo(value["timezone"])
        if "window" in value and "slots" in value:
            for slot in value["slots"]:
                if instant(slot["start"]) < instant(value["window"]["start"]) or instant(
                    slot["end"]
                ) > instant(value["window"]["end"]):
                    raise ValueError("slot outside window")
        for child in value.values():
            if isinstance(child, dict):
                temporal(child)
            elif isinstance(child, list):
                for item in child:
                    if isinstance(item, dict):
                        temporal(item)
    except (ValueError, ZoneInfoNotFoundError, TypeError):
        raise Problem(400, "Invalid time interval or timezone") from None


def disclosure(envelope: dict[str, Any], ceiling: str) -> None:
    level = envelope.get("disclosure_level")
    if level not in LEVELS:
        raise Problem(400, "Invalid request")
    if LEVELS.index(level) > LEVELS.index(ceiling):
        raise Problem(422, "Disclosure violation")
    slots = envelope.get("slots", [])
    if not isinstance(slots, list) or any(not isinstance(s, dict) for s in slots):
        raise Problem(400, "Invalid request")
    for slot in slots:
        if (
            level == "none"
            or (level == "free_busy" and ("category" in slot or "label" in slot))
            or (level == "category" and "label" in slot)
        ):
            raise Problem(422, "Disclosure violation")


def message(value: dict[str, Any]) -> None:
    if not isinstance(value.get("scope", {}), dict) or not isinstance(
        value.get("payload", {}), dict
    ):
        raise Problem(400, "Invalid request")
    level = value.get("disclosure_level")
    ceiling = value.get("scope", {}).get("max_disclosure_level")
    if level in LEVELS and ceiling in LEVELS:
        disclosure({"disclosure_level": level}, ceiling)
        nested = value.get("payload", {}).get("availability")
        if isinstance(nested, dict):
            disclosure(nested, level)
    contract(value, "agent-protocol")
    temporal(value)


def inline_references(value: Any) -> Any:
    """vLLM must not fetch our public schema IDs; embed their frozen local content."""
    if isinstance(value, dict):
        if "$ref" in value and value["$ref"].startswith("https://campusos.dev/contracts/v1/"):
            name = value["$ref"].rsplit("/", 1)[-1].removesuffix(".json")
            return inline_references(SCHEMAS[name])
        return {k: inline_references(v) for k, v in value.items() if k != "$id"}
    if isinstance(value, list):
        return [inline_references(v) for v in value]
    return value
