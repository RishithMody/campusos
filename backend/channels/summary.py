"""Closed channel vocabulary. This module never imports inference code."""

from typing import Any

from backend.common import Problem
from backend.protocol.validation import API, validate

TEMPLATES = {
    "gathering": "gathering_availability",
    "negotiating": "proposal_on_table",
    "awaiting_approval": "awaiting_approvals",
    "converged": "converged",
    "expired": "expired",
    "cancelled": "cancelled",
}


def summary(data: dict[str, Any], timezone: str) -> dict[str, Any]:
    status = data["status"]
    if status == "failed":
        template = {
            "no_overlap": "failed_no_overlap",
            "max_rounds_exceeded": "failed_max_rounds",
        }.get(data["outcome"]["kind"])
    else:
        template = TEMPLATES.get(status)
    if template is None:
        raise Problem(403)
    result = {
        "negotiation_id": data["negotiation_id"],
        "status": status,
        "round": data["round"],
        "max_rounds": data["max_rounds"],
        "template_id": template,
        "participant_count": len(data["members"]),
    }
    if status == "converged":
        result.update(agreed_slot=data["outcome"]["agreed_slot"], timezone=timezone)
    validate(result, API["components"]["schemas"]["ChannelSummary"])
    return result
