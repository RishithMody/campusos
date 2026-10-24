from datetime import UTC, datetime
from secrets import token_hex
from typing import Any


def identifier(prefix: str) -> str:
    return f"{prefix}_{token_hex(12)}"


def now() -> datetime:
    return datetime.now(UTC)


def timestamp() -> str:
    return now().isoformat()


def instant(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timezone required")
    return result


class Problem(Exception):
    def __init__(self, status: int, title: str = "Request not permitted"):
        self.status = status
        self.title = title

    def payload(self) -> dict[str, Any]:
        return {"type": "about:blank", "title": self.title, "status": self.status}
