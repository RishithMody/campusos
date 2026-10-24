import asyncio
from copy import deepcopy
from datetime import timedelta

import pytest
from conftest import create, grants, read
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from test_api import proposal

from backend.app import create_app
from backend.common import now
from backend.config import Settings
from backend.db.models import Negotiation


@pytest.mark.parametrize(
    "scope,payload", [(None, {}), ([], {}), ("forged", {}), ({}, []), ({}, "private")]
)
def test_malformed_protocol_never_500(env, scope, payload):
    state, window = create(env)
    body = proposal(env, state, window)
    body.update(scope=scope, payload=payload)
    response = env.client.post(
        f"/v1/negotiations/{state['negotiation_id']}/messages", headers=env.headers(), json=body
    )
    assert response.status_code == 400
    assert "private" not in response.text


def test_expired_and_forged_tokens(env):
    assert (
        env.client.get("/v1/me", headers=env.headers(exp=now() - timedelta(seconds=1))).status_code
        == 401
    )
    header = env.headers()
    header["Authorization"] = header["Authorization"][:-10] + "bad-token"
    assert env.client.get("/v1/me", headers=header).status_code == 401
    assert env.client.get("/v1/me", headers=env.headers(aud="another-app")).status_code == 401


def test_redis_down_mutation_fails_closed(env, monkeypatch):
    async def down():
        raise RedisConnectionError("secret connection URL")

    monkeypatch.setattr(env.redis, "ping", down)
    response = env.client.post("/v1/me", headers=env.headers())
    assert response.status_code == 503
    assert "secret" not in response.text


def test_database_failure_is_sanitized(env):
    class BrokenSessions:
        def begin(self):
            raise OperationalError("private student SQL", {}, Exception("secret password"))

    from fastapi.testclient import TestClient

    app = create_app(
        env.settings,
        sessions=BrokenSessions(),
        ephemeral=env.ephemeral,
        inference=env.inference,
        discord=env.discord,
    )
    with TestClient(app) as client:
        response = client.get("/v1/me", headers=env.headers())
    assert response.status_code == 503
    assert "private" not in response.text and "password" not in response.text


@pytest.mark.parametrize("mode", [None, "", "auto", "MOCK"])
def test_inference_selection_requires_explicit_valid_value(monkeypatch, mode):
    if mode is None:
        monkeypatch.delenv("CAMPUSOS_INFERENCE_MODE", raising=False)
    else:
        monkeypatch.setenv("CAMPUSOS_INFERENCE_MODE", mode)
    with pytest.raises(ValueError, match="explicitly"):
        Settings.from_env()


@pytest.mark.asyncio
async def test_redis_ttl_and_no_calendar_payload(env):
    await env.ephemeral.publish("neg_test", 3)
    assert await env.redis.get("session:neg_test") == "3"
    assert 0 < await env.redis.ttl("session:neg_test") <= 1
    await asyncio.sleep(1.05)
    assert await env.redis.get("session:neg_test") is None


def test_expired_grant_blocks_messages(env):
    from backend.db.models import Grant

    state, window = create(env)
    ids = grants(env, state, window)
    with env.sessions.begin() as session:
        grant = session.get(Grant, ids[0][2])
        grant.expires = (now() - timedelta(seconds=1)).isoformat()
    response = env.client.post(
        f"/v1/negotiations/{state['negotiation_id']}/messages",
        headers=env.headers(),
        json=proposal(env, state, window),
    )
    assert response.status_code == 403
    assert read(env, state["negotiation_id"])["transcript"] == []


def test_rejected_request_does_not_mutate_durable_state(env):
    state, window = create(env)
    grants(env, state, window)
    before = read(env, state["negotiation_id"])
    bad = proposal(env, state, window)
    bad["represented_student"]["student_ref"] = before["participants"][1]["student_ref"]
    response = env.client.post(
        f"/v1/negotiations/{state['negotiation_id']}/messages", headers=env.headers(), json=bad
    )
    assert response.status_code == 403
    with env.sessions() as session:
        data = deepcopy(session.scalar(select(Negotiation)).data)
    assert data["state_version"] == before["state_version"] and data["messages"] == []


def test_availability_cannot_disclose_outside_negotiation_window(env):
    from conftest import availability

    from backend.common import instant

    state, window = create(env)
    body = availability(env, state, window, "alice")
    body["slots"][0]["start"] = (instant(window["start"]) - timedelta(hours=1)).isoformat()
    assert (
        env.client.put("/v1/me/availability", headers=env.headers(), json=body).status_code == 400
    )
    body["window"]["start"] = body["slots"][0]["start"]
    assert (
        env.client.put("/v1/me/availability", headers=env.headers(), json=body).status_code == 400
    )
