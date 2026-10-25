"""Explicitly substitute the env fixture without editing either owning suite."""

import os
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


class LoopSafeRedis:
    """Real Redis connections scoped to the calling loop, including pub/sub lifetime.

    TestClient and direct async route tests use different event loops. No pool or
    socket crosses between them. No Redis operation is simulated or swallowed.
    """

    def __init__(self, url):
        self.url = url

    def connect(self):
        return Redis.from_url(self.url, decode_responses=True, socket_timeout=2)

    def __getattr__(self, name):
        async def call(*args, **kwargs):
            async with self.connect() as client:
                return await getattr(client, name)(*args, **kwargs)

        return call

    @asynccontextmanager
    async def pipeline(self, **kwargs):
        async with self.connect() as client, client.pipeline(**kwargs) as pipeline:
            yield pipeline

    @asynccontextmanager
    async def pubsub(self):
        async with self.connect() as client, client.pubsub() as subscription:
            yield subscription


def service_urls():
    pg = os.environ.get("CAMPUSOS_TEST_POSTGRES_URL")
    redis = os.environ.get("CAMPUSOS_TEST_REDIS_URL")
    if not pg or not redis:
        pytest.fail(
            "Live opt-in requires both CAMPUSOS_TEST_POSTGRES_URL and CAMPUSOS_TEST_REDIS_URL"
        )
    for value in (pg, redis):
        if make_url(value).host not in {"localhost", "127.0.0.1", "::1"}:
            pytest.fail("T7a only permits disposable loopback services")
    return pg, redis


def pytest_collection_modifyitems(config, items):
    if os.environ.get("CAMPUSOS_LIVE") != "1":
        return
    service_urls()
    from tests.live.environment import live_env

    for item in items:
        for definition in item._fixtureinfo.name2fixturedefs.get("env", ()):
            definition.func = live_env
            definition.argnames = ("request",)


def isolated_database(url):
    """Generator whose finalizer drops only its own randomly named database."""
    admin = create_engine(url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    name = "t7a_" + uuid4().hex
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    target = admin.url.set(database=name)
    engine = create_engine(target, pool_pre_ping=True)
    try:
        yield engine, target.render_as_string(hide_password=False)
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()
