from datetime import timedelta
from secrets import token_urlsafe
from types import SimpleNamespace

import jwt
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.app import create_app
from backend.channels.discord import Audience
from backend.common import identifier, now
from backend.config import Settings
from backend.db.ephemeral import Ephemeral
from backend.db.models import Base, Student
from backend.inference.mock import MockInference
from tests.live.plugin import LoopSafeRedis, isolated_database, service_urls


class FakeDiscord:
    size = 3

    async def audience(self, channel, guild):
        return Audience(guild, self.size)

    async def member(self, channel, guild, user):
        return user in {"1", "2", "3"}


def live_env(request):
    pg_url, redis_url = service_urls()
    database = isolated_database(pg_url)
    engine, target = next(database)
    request.addfinalizer(database.close)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    settings = Settings(target, redis_url, token_urlsafe(40), "mock")
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
    redis = LoopSafeRedis(redis_url)
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
