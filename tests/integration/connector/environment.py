"""Harness for the connector-boundary suite.

Deliberately a copy of the backend fixture rather than an import of it, exactly as
`tests/live/environment.py` is. A test about a trust boundary should not fail because
another suite changed its fixture, and the duplication is the established idiom here.

Everything is in-process: SQLite, fakeredis, mock inference, a fake Discord. No
network, no credentials, no Discord connection.
"""

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
from backend.channels.discord import Audience
from backend.common import identifier, now
from backend.config import Settings
from backend.db.ephemeral import Ephemeral
from backend.db.models import Base, Student
from backend.inference.mock import MockInference

STUDENTS = ("alice", "bob", "carol", "outsider")


class FakeDiscord:
    """Audience size is mutable so a test can grow the room and trip re-consent."""

    size = 3

    async def audience(self, channel, guild):
        return Audience(guild, self.size)

    async def member(self, channel, guild, user):
        return user in {"1", "2", "3"}


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
        for i, name in enumerate(STUDENTS, 1):
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
    discord = FakeDiscord()
    app = create_app(
        settings,
        sessions=sessions,
        ephemeral=Ephemeral(redis, ttl=1),
        inference=MockInference(delay=0),
        discord=discord,
    )
    with TestClient(app) as client:

        def headers(who="alice", kind="human", key=None, **claims):
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
            token = jwt.encode(data, key or settings.jwt_key, algorithm="HS256")
            return {"Authorization": "Bearer " + token}

        yield SimpleNamespace(
            client=client,
            headers=headers,
            sessions=sessions,
            students=students,
            settings=settings,
            discord=discord,
            app=app,
        )
    engine.dispose()


def window_from_now(hours=5, days=2):
    start = (now() + timedelta(days=days)).replace(hour=10, minute=0, second=0, microsecond=0)
    return {"start": start.isoformat(), "end": (start + timedelta(hours=hours)).isoformat()}


def create(env, who="alice", invitees=("bob", "carol")):
    window = window_from_now()
    body = {
        "invitees": [env.students[name].contact_handle for name in invitees],
        "window": window,
        "max_rounds": 5,
        "min_duration_minutes": 60,
    }
    response = env.client.post("/v1/negotiations", json=body, headers=env.headers(who))
    assert response.status_code == 201, response.text
    return response.json(), window


def read(env, neg, who="alice"):
    response = env.client.get(f"/v1/negotiations/{neg}", headers=env.headers(who))
    assert response.status_code == 200, response.text
    return response.json()


def grant(env, neg, owner, grantee, window):
    response = env.client.post(
        "/v1/grants",
        headers=env.headers(owner),
        json={
            "negotiation_id": neg,
            "grantee_agent_id": env.students[grantee].agent_id,
            "max_disclosure_level": "free_busy",
            "expires_at": window["end"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["grant_id"]


def register(env, subject="bot", platform_channel="1234", level="free_busy", guild="123"):
    return env.client.post(
        "/v1/channels",
        headers=env.headers(subject, "bot", guild=guild),
        json={
            "platform": "discord",
            "platform_channel_id": platform_channel,
            "max_disclosure_level": level,
        },
    )


def bind(env, neg, channel, who="alice"):
    response = env.client.post(
        f"/v1/negotiations/{neg}/channel-bindings",
        headers=env.headers(who),
        json={"channel_id": channel},
    )
    assert response.status_code == 201, response.text
    return response.json()


def link_all(env, channel, names=("alice", "bob", "carol")):
    for name in names:
        response = env.client.post(f"/v1/channels/{channel}/members", headers=env.headers(name))
        assert response.status_code == 204, response.text


def decide(env, neg, who, decision="approve", action="post_to_channel"):
    state = read(env, neg, who)
    approval = next(a for a in state["pending_approvals"] if a["action"] == action)
    response = env.client.post(
        f"/v1/approvals/{approval['approval_id']}",
        headers=env.headers(who),
        json={"decision": decision, "state_version": state["state_version"]},
    )
    assert response.status_code == 200, response.text
    return approval["approval_id"]
