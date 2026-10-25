"""Real local dependency failures; external Discord and inference remain mocked."""

import asyncio
import os
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest
from redis import Redis
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from starlette.requests import Request

from backend.auth import authenticate
from backend.db.models import Commitment, Negotiation
from backend.inference.base import InferenceTimeout, InferenceUnavailable
from tests.backend.conftest import availability, create, grants, read, ready


def stream_for(env, neg):
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": f"/v1/negotiations/{neg}/stream",
            "query_string": b"",
            "headers": [],
            "path_params": {"negotiation_id": neg},
        },
        receive,
    )
    request.state.identity = authenticate(env.headers()["Authorization"], env.settings)
    route = next(r for r in env.app.routes if r.path.endswith("/stream"))
    return route.endpoint(request)


def control(service, action):
    if os.environ.get("CAMPUSOS_LIVE_DESTRUCTIVE") != "1":
        pytest.skip("Set CAMPUSOS_LIVE_DESTRUCTIVE=1 for isolated-service stop/restart tests")
    pg_url = make_url(os.environ["CAMPUSOS_TEST_POSTGRES_URL"])
    redis_url = make_url(os.environ["CAMPUSOS_TEST_REDIS_URL"])
    assert pg_url.host == redis_url.host == "127.0.0.1"
    assert pg_url.port == 55439 and redis_url.port == 56389
    if os.environ.get("CAMPUSOS_LIVE_NATIVE") == "1":
        if service == "postgres":
            directory = "/private/tmp/campusos-t7a-pg"
            assert Path(directory, "PG_VERSION").is_file()
            args = [shutil.which("pg_ctl"), "-D", directory]
            if action == "stop":
                args += ["stop", "-m", "immediate", "-w"]
            else:
                args += [
                    "-l",
                    "/private/tmp/campusos-t7a-pg.log",
                    "-o",
                    "-h 127.0.0.1 -p 55439 -k /private/tmp",
                    "start",
                    "-w",
                ]
        elif action == "stop":
            with Redis.from_url(os.environ["CAMPUSOS_TEST_REDIS_URL"]) as client:
                client.shutdown(nosave=True)
            return
        else:
            args = [
                shutil.which("redis-server"),
                "--bind",
                "127.0.0.1",
                "--port",
                "56389",
                "--save",
                "",
                "--appendonly",
                "no",
                "--daemonize",
                "yes",
                "--pidfile",
                "/private/tmp/campusos-t7a-redis.pid",
                "--logfile",
                "/private/tmp/campusos-t7a-redis.log",
            ]
    else:
        args = [shutil.which("docker"), "compose", "-f", "docker-compose.yml", action, service]
    subprocess.run(args, check=True, capture_output=True, timeout=30)  # noqa: S603


def snapshot(env, neg):
    with env.sessions() as session:
        return deepcopy(session.get(Negotiation, neg).data)


@pytest.mark.parametrize("failure", [InferenceTimeout, InferenceUnavailable])
def test_inference_failure_escalates_without_commit(env, failure):
    state, window = create(env)
    grants(env, state, window)
    env.inference.failure = failure
    for who in ("alice", "bob", "carol"):
        availability(env, state, window, who)
    state = read(env, state["negotiation_id"])
    assert state["status"] == "failed"
    assert state["outcome"]["requires_human_approval"] is True
    with env.sessions() as session:
        assert session.scalar(select(Commitment)) is None


def test_connection_killed_mid_transaction_rolls_back(env):
    state, _ = create(env)
    neg = state["negotiation_id"]
    original = snapshot(env, neg)
    with env.sessions() as session:
        row = session.get(Negotiation, neg)
        row.data = {**row.data, "private_probe": "must_not_commit"}
        session.flush()
        pid = session.scalar(text("SELECT pg_backend_pid()"))
        with env.sessions.begin() as killer:
            assert killer.scalar(text("SELECT pg_terminate_backend(:pid)"), {"pid": pid})
        with pytest.raises(OperationalError):
            session.commit()
    assert snapshot(env, neg) == original
    assert read(env, neg)["status"] == "gathering"


@pytest.mark.skipif(
    os.environ.get("CAMPUSOS_LIVE_DESTRUCTIVE") != "1",
    reason="Set CAMPUSOS_LIVE_DESTRUCTIVE=1 for dedicated service restarts",
)
def test_postgres_server_restart_preserves_negotiation(env):
    state, _, _ = ready(env)
    neg = state["negotiation_id"]
    original = snapshot(env, neg)
    control("postgres", "stop")
    try:
        response = env.client.get(f"/v1/negotiations/{neg}", headers=env.headers())
        assert response.status_code == 503
        assert response.json()["title"] == "Durable state unavailable"
        assert neg not in response.text
    finally:
        control("postgres", "start")
    assert snapshot(env, neg) == original
    assert read(env, neg)["status"] == "awaiting_approval"


@pytest.mark.skipif(
    os.environ.get("CAMPUSOS_LIVE_DESTRUCTIVE") != "1",
    reason="Set CAMPUSOS_LIVE_DESTRUCTIVE=1 for dedicated service restarts",
)
@pytest.mark.asyncio
async def test_redis_outage_stream_terminal_and_reconnect(env):
    state, _, _ = ready(env)
    neg = state["negotiation_id"]
    original = snapshot(env, neg)
    stream = await stream_for(env, neg)
    assert (await anext(stream.body_iterator)).startswith("event: state")
    # Start subscription before interrupting the service, as for an active SSE client.
    pending = asyncio.create_task(anext(stream.body_iterator))
    await asyncio.sleep(0.15)
    await asyncio.to_thread(control, "redis", "stop")
    try:
        approval = state["pending_approvals"][0]
        response = env.client.post(
            f"/v1/approvals/{approval['approval_id']}",
            headers=env.headers(),
            json={"decision": "approve", "state_version": approval["state_version"]},
        )
        assert response.status_code == 503
        assert response.json()["title"] == "State notifications unavailable"
        error = await asyncio.wait_for(pending, timeout=10)
        assert error.startswith("event: error") and '"status": 503' in error
        assert neg not in error
        assert snapshot(env, neg) == original
    finally:
        await asyncio.to_thread(control, "redis", "start")
        await stream.body_iterator.aclose()
    recovered = await stream_for(env, neg)
    assert (await anext(recovered.body_iterator)).startswith("event: state")
    await recovered.body_iterator.aclose()
    assert env.client.post("/v1/me", headers=env.headers()).status_code == 200


@pytest.mark.asyncio
async def test_real_pooled_redis_pubsub_ttl_and_payload(env):
    # Exercise an ordinary real pool on ONE loop as production does. The suite
    # adapter above exists only for tests crossing TestClient/pytest loop boundaries.
    from redis.asyncio import Redis as AsyncRedis

    from backend.common import identifier
    from backend.db.ephemeral import Ephemeral

    neg = identifier("neg")
    async with AsyncRedis.from_url(env.settings.redis_url, decode_responses=True) as client:
        ephemeral = Ephemeral(client, ttl=1)
        async with client.pubsub() as subscription:
            await subscription.subscribe(f"updates:{neg}")
            await subscription.get_message(timeout=1)
            await ephemeral.publish(neg, 7)
            message = await subscription.get_message(ignore_subscribe_messages=True, timeout=1)
            assert message["data"] == "7"
            assert await client.get(f"session:{neg}") == "7"
            assert 0 < await client.ttl(f"session:{neg}") <= 1
            await asyncio.sleep(1.1)
            assert await client.get(f"session:{neg}") is None


def test_human_consent_boundary_is_the_trusted_issuer_claim(env):
    state, _, _ = ready(env)
    approval = state["pending_approvals"][0]
    endpoint = f"/v1/approvals/{approval['approval_id']}"
    body = {"decision": "approve", "state_version": approval["state_version"]}
    assert (
        env.client.post(endpoint, headers=env.headers(kind="agent"), json=body).status_code == 403
    )
    # A trusted issuer can assert human kind without any ceremony in this harness.
    # The API trusts that assertion: this documents the existing issuer boundary.
    assert (
        env.client.post(endpoint, headers=env.headers(kind="human"), json=body).status_code == 200
    )
    with env.sessions() as session:
        assert session.scalar(select(Commitment)) is None
