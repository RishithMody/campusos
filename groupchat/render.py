"""Render only frozen ChannelSummary templates, never participant state or prose."""

from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml
from jsonschema import Draft202012Validator, FormatChecker

CONTRACT = Path(__file__).resolve().parents[1] / "contracts/api.openapi.yaml"
SCHEMA = yaml.safe_load(CONTRACT.read_text())["components"]["schemas"]["ChannelSummary"]
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
TEMPLATES = {
    "gathering_availability": "Collecting availability from {participant_count} people.",
    "proposal_on_table": "There's a time on the table -- round {round} of {max_rounds}.",
    "awaiting_approvals": "Waiting on everyone to confirm.",
    "converged": "Locked in: {agreed_slot}.",
    "failed_no_overlap": "No time works for everyone in this window.",
    "failed_max_rounds": "No time found in {max_rounds} rounds -- over to you.",
    "expired": "This one timed out.",
    "cancelled": "Someone withdrew, so this is off.",
    "consent_withdrawn": "I've been asked to stop posting about this one.",
}
STATUS = {
    "gathering_availability": "gathering",
    "proposal_on_table": "negotiating",
    "awaiting_approvals": "awaiting_approval",
    "converged": "converged",
    "failed_no_overlap": "failed",
    "failed_max_rounds": "failed",
    "expired": "expired",
    "cancelled": "cancelled",
}


def render(data: Any, negotiation: str) -> str:
    """Reject malformed/extra fields; this is contract validation, not disclosure policy."""
    if not VALIDATOR.is_valid(data) or data["negotiation_id"] != negotiation:
        raise ValueError("Invalid channel summary.")
    template = data["template_id"]
    # Withdrawal is communicated by a uniform 403, never a public announcement.
    if template not in STATUS or data["status"] != STATUS[template]:
        raise ValueError("Unsupported channel summary.")
    if data["round"] > data["max_rounds"]:
        raise ValueError("Invalid round.")
    slots = {key: data[key] for key in ("participant_count", "round", "max_rounds")}
    if template == "converged":
        zone = ZoneInfo(data["timezone"])
        start, end = (
            datetime.fromisoformat(data["agreed_slot"][key].replace("Z", "+00:00"))
            for key in ("start", "end")
        )
        if end <= start:
            raise ValueError("Invalid interval.")
        slots["agreed_slot"] = (
            f"{start.astimezone(zone):%Y-%m-%d %H:%M %Z} – {end.astimezone(zone):%Y-%m-%d %H:%M %Z}"
        )
    elif "agreed_slot" in data or "timezone" in data:
        raise ValueError("Unexpected interval.")
    return TEMPLATES[template].format(**slots)
