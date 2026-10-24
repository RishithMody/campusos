from dataclasses import dataclass

import jwt

from backend.common import Problem
from backend.config import Settings


@dataclass(frozen=True)
class Identity:
    subject: str
    kind: str
    expires: int
    agent_id: str | None = None
    guild: str | None = None

    def human(self) -> None:
        if self.kind != "human":
            raise Problem(403)


def authenticate(header: str, settings: Settings) -> Identity:
    if not header.startswith("Bearer "):
        raise Problem(401, "Authentication required")
    try:
        claims = jwt.decode(
            header[7:],
            settings.jwt_key,
            algorithms=["HS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "exp", "iat", "iss", "aud", "kind"]},
        )
        if claims["kind"] not in {"human", "agent", "bot"} or not isinstance(claims["sub"], str):
            raise ValueError("invalid principal")
        return Identity(
            claims["sub"],
            claims["kind"],
            claims["exp"],
            claims.get("agent_id"),
            claims.get("guild"),
        )
    except (jwt.PyJWTError, ValueError, TypeError):
        raise Problem(401, "Authentication required") from None
