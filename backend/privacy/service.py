from copy import deepcopy
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.common import Problem, identifier, instant, now, timestamp
from backend.db.models import Audit, Commitment, Grant, Student
from backend.protocol.validation import LEVELS, contract


def audit(session: Session, actor: str, action: str, resource: str, detail: str = "") -> None:
    session.add(
        Audit(
            id=identifier("aud"),
            at=timestamp(),
            actor=actor,
            action=action,
            resource=resource,
            detail=detail,
        )
    )


def granted(session: Session, owner: str, agent: str, negotiation: str) -> str:
    grants = session.scalars(
        select(Grant).where(
            Grant.owner == owner,
            Grant.agent == agent,
            Grant.negotiation == negotiation,
            Grant.revoked.is_(False),
        )
    ).all()
    levels = [g.level for g in grants if instant(g.expires) > now()]
    if not levels:
        raise Problem(403)
    return max(levels, key=LEVELS.index)


def own_calendar(session: Session, caller: str, subject: str) -> list[dict[str, Any]]:
    # Raw calendar rows NEVER cross student boundaries, including under a full grant.
    if caller != subject:
        raise Problem(403)
    return [
        deepcopy(row.data)
        for row in session.scalars(select(Commitment).where(Commitment.owner == caller))
    ]


def envelope(value: dict[str, Any], ceiling: str, *, prompt: bool = False) -> dict[str, Any]:
    result = deepcopy(value)
    level = min((value["disclosure_level"], ceiling), key=LEVELS.index)
    # Even an explicitly granted full label must never enter a model prompt.
    if prompt:
        level = min((level, "free_busy"), key=LEVELS.index)
    result["disclosure_level"] = level
    redactions = result.get("redactions", 0)
    if level == "none":
        redactions += len(result["slots"])
        result["slots"] = []
        result.pop("constraints", None)
    else:
        for slot in result["slots"]:
            for field in ("label", "category"):
                if field in slot and (
                    level == "free_busy" or (level == "category" and field == "label")
                ):
                    slot.pop(field)
                    redactions += 1
    result["redactions"] = redactions
    contract(result, "availability")
    return result


def outbound(
    session: Session,
    data: dict[str, Any],
    source: str,
    recipient: str,
    negotiation: str,
    payload: dict[str, Any],
    level: str,
) -> tuple[dict[str, Any], str]:
    result = deepcopy(payload)
    result.pop("note_for_own_student", None)
    if source != recipient:
        student = session.get(Student, recipient)
        if student is None:
            raise Problem(403)
        ceiling = granted(session, source, student.agent_id, negotiation)
        level = min((level, ceiling), key=LEVELS.index)
        audit(session, recipient, "cross_student_disclosure", negotiation, level)
    if "availability" in result:
        result["availability"] = envelope(result["availability"], level)
    return result, level
