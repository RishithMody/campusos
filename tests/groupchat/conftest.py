from datetime import timedelta
from secrets import token_urlsafe
from types import SimpleNamespace

import fakeredis.aioredis
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import create_app
from backend.channels.discord import Audience, fingerprint
from backend.common import identifier, now
from backend.config import Settings
from backend.db.ephemeral import Ephemeral
from backend.db.models import Base, Student
from backend.inference.mock import MockInference


class FakeDiscord:
    """`viewers` is mutable so a test can grow, shrink or swap the room.

    Identity, not a count: a fake that only tracked a size could not reproduce the
    same-size membership swap, which is exactly the case the real gate exists for.
    `member` keeps its own fixed set, so changing the audience does not change who is
    allowed to link a channel.
    """

    def __init__(self):
        self.viewers = {"1", "2", "3"}
        self.linkable = {"1", "2", "3"}

    @property
    def size(self):
        return len(self.viewers)

    async def audience(self, channel, guild):
        return Audience(
            guild, len(self.viewers), fingerprint=fingerprint(channel, guild, self.viewers)
        )

    async def member(self, channel, guild, user):
        return user in self.linkable


@pytest.fixture
def env():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    settings = Settings("sqlite://", "redis://localhost", token_urlsafe(40), "mock")
    students = {}
    with sessions.begin() as session:
        for i, name in enumerate(("alice", "bob", "carol", "outsider"), 1):
            student = Student(
                id=name,
                agent_id=identifier("agt"),
                contact_handle=identifier("cnt"),
                ceiling="free_busy",
                discord_id=str(i),
            )
            session.add(student)
            students[name] = student
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    ephemeral = Ephemeral(redis, ttl=1)
    inference = MockInference(delay=0)
    discord = FakeDiscord()
    app = create_app(
        settings, sessions=sessions, ephemeral=ephemeral, inference=inference, discord=discord
    )
    with TestClient(app) as client:

        def headers(who="alice", kind="human", **claims):
            data = {
                "sub": who,
                "kind": kind,
                "exp": now() + timedelta(hours=1),
                "iat": now(),
                "iss": settings.jwt_issuer,
                "aud": settings.jwt_audience,
            }
            if kind == "agent":
                data["agent_id"] = students[who].agent_id
            if kind == "bot":
                data["guild"] = "123"
            data.update(claims)
            return {
                "Authorization": "Bearer " + jwt.encode(data, settings.jwt_key, algorithm="HS256")
            }

        yield SimpleNamespace(
            client=client,
            headers=headers,
            sessions=sessions,
            students=students,
            inference=inference,
            redis=redis,
            ephemeral=ephemeral,
            settings=settings,
            discord=discord,
            app=app,
        )
    engine.dispose()


def create(env, max_rounds=5):
    start = (now() + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0)
    body = {
        "invitees": [env.students[name].contact_handle for name in ("bob", "carol")],
        "window": {"start": start.isoformat(), "end": (start + timedelta(hours=5)).isoformat()},
        "max_rounds": max_rounds,
        "min_duration_minutes": 60,
    }
    response = env.client.post("/v1/negotiations", json=body, headers=env.headers())
    assert response.status_code == 201, response.text
    return response.json(), body["window"]


def read(env, neg, who="alice"):
    response = env.client.get(f"/v1/negotiations/{neg}", headers=env.headers(who))
    assert response.status_code == 200, response.text
    return response.json()


def grants(env, state, window):
    values = []
    for who in ("alice", "bob", "carol"):
        for other in ("alice", "bob", "carol"):
            if who == other:
                continue
            response = env.client.post(
                "/v1/grants",
                headers=env.headers(who),
                json={
                    "negotiation_id": state["negotiation_id"],
                    "grantee_agent_id": env.students[other].agent_id,
                    "max_disclosure_level": "free_busy",
                    "expires_at": window["end"],
                },
            )
            assert response.status_code == 201, response.text
            values.append((who, other, response.json()["grant_id"]))
    return values


def availability(env, state, window, who, offset=0, busy=False):
    from backend.common import instant

    own = read(env, state["negotiation_id"], who)
    start = instant(window["start"]) + timedelta(hours=offset)
    body = {
        "schema_version": "1.0",
        "student_ref": own["viewer"]["student_ref"],
        "generated_at": now().isoformat(),
        "timezone": "UTC",
        "window": window,
        "disclosure_level": "free_busy",
        "slots": [
            {"start": start.isoformat(), "end": window["end"], "state": "busy" if busy else "free"}
        ],
    }
    response = env.client.put("/v1/me/availability", headers=env.headers(who), json=body)
    assert response.status_code == 204, response.text
    return body


def ready(env, max_rounds=5):
    state, window = create(env, max_rounds)
    grant_ids = grants(env, state, window)
    for i, who in enumerate(("alice", "bob", "carol")):
        availability(env, state, window, who, offset=i)
    return read(env, state["negotiation_id"]), window, grant_ids
