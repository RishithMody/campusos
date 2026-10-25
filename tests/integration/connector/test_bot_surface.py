"""C1-C4: what a kind=bot credential can reach, probed with valid bodies.

The point of this file is the *method*. An earlier manual probe reported 400 for five
operations and those 400s were nearly mistaken for authorization enforcement -- they were
schema rejections raised before the service layer ran. A 400 says the request was
malformed; only a 403 says the caller was refused. Every case below therefore sends a
body and identifiers the contract accepts, so the status that comes back is about
authority and nothing else.
"""

from datetime import timedelta

import pytest

from backend.common import identifier, now
from backend.protocol.validation import API
from tests.integration.connector.environment import (
    bind,
    create,
    grant,
    link_all,
    read,
    register,
    window_from_now,
)

# Everything a bot may reach. Anything not here must refuse a bot outright.
REACHABLE = {("get", "/health"), ("post", "/channels")}


@pytest.fixture
def scenario(env):
    """Real negotiation, real grant, real channel, real approval -- no placeholder ids."""
    state, window = create(env)
    neg = state["negotiation_id"]
    grant_id = grant(env, neg, "alice", "bob", window)
    channel = register(env).json()["channel_id"]
    link_all(env, channel)
    bind(env, neg, channel)
    viewer = read(env, neg)
    approval = viewer["pending_approvals"][0]["approval_id"]
    envelope = {
        "schema_version": "1.0",
        "message_id": identifier("msg"),
        "trace_id": viewer["trace_id"],
        "issued_at": now().isoformat(),
        "sender": {"agent_id": viewer["viewer"]["agent_id"], "agent_version": "1"},
        "represented_student": {"student_ref": viewer["viewer"]["student_ref"]},
        "scope": {
            "negotiation_id": neg,
            "actions": ["propose"],
            "expires_at": window["end"],
            "max_disclosure_level": "free_busy",
            "granted_by": "standing",
        },
        "disclosure_level": "free_busy",
        "intent": "propose",
        "payload": {"proposed_slot": window},
    }
    availability = {
        "schema_version": "1.0",
        "student_ref": viewer["viewer"]["student_ref"],
        "generated_at": now().isoformat(),
        "timezone": "UTC",
        "window": window,
        "disclosure_level": "free_busy",
        "slots": [{"start": window["start"], "end": window["end"], "state": "free"}],
    }
    return {
        "neg": neg,
        "channel": channel,
        "grant": grant_id,
        "approval": approval,
        "window": window,
        "envelope": envelope,
        "availability": availability,
        "state_version": viewer["state_version"],
    }


def requests_for(env, s):
    """One valid request per operation in the frozen contract, as a bot would send it."""
    neg, channel = s["neg"], s["channel"]
    return {
        ("get", "/health"): ("/v1/health", None),
        ("get", "/me"): ("/v1/me", None),
        ("post", "/me"): ("/v1/me", None),
        ("post", "/me/chat"): ("/v1/me/chat", {"message": "when?", "negotiation_id": neg}),
        ("put", "/me/availability"): ("/v1/me/availability", s["availability"]),
        ("get", "/negotiations"): ("/v1/negotiations", None),
        ("post", "/negotiations"): (
            "/v1/negotiations",
            {
                "invitees": [env.students["bob"].contact_handle],
                "window": window_from_now(days=3),
                "max_rounds": 5,
            },
        ),
        ("get", "/negotiations/{negotiation_id}"): (f"/v1/negotiations/{neg}", None),
        ("post", "/negotiations/{negotiation_id}/messages"): (
            f"/v1/negotiations/{neg}/messages",
            s["envelope"],
        ),
        ("get", "/negotiations/{negotiation_id}/stream"): (f"/v1/negotiations/{neg}/stream", None),
        ("post", "/approvals/{approval_id}"): (
            f"/v1/approvals/{s['approval']}",
            {"decision": "approve", "state_version": s["state_version"]},
        ),
        ("post", "/channels"): (
            "/v1/channels",
            {
                "platform": "discord",
                "platform_channel_id": "5678",
                "max_disclosure_level": "free_busy",
            },
        ),
        ("post", "/channels/{channel_id}/members"): (f"/v1/channels/{channel}/members", None),
        ("post", "/negotiations/{negotiation_id}/channel-bindings"): (
            f"/v1/negotiations/{neg}/channel-bindings",
            {"channel_id": channel},
        ),
        ("get", "/negotiations/{negotiation_id}/channel-bindings"): (
            f"/v1/negotiations/{neg}/channel-bindings",
            None,
        ),
        ("delete", "/negotiations/{negotiation_id}/channel-bindings/{channel_id}"): (
            f"/v1/negotiations/{neg}/channel-bindings/{channel}",
            None,
        ),
        ("get", "/negotiations/{negotiation_id}/channel-summary"): (
            f"/v1/negotiations/{neg}/channel-summary?channel_id={channel}",
            None,
        ),
        ("post", "/grants"): (
            "/v1/grants",
            {
                "negotiation_id": neg,
                "grantee_agent_id": env.students["carol"].agent_id,
                "max_disclosure_level": "free_busy",
                # Grant expiry may not exceed the negotiation window; a body that broke
                # that rule would 400 for a human and mask what the bot's 403 proves.
                "expires_at": s["window"]["end"],
            },
        ),
        ("delete", "/grants/{grant_id}"): (f"/v1/grants/{s['grant']}", None),
    }


def send(env, method, url, body, headers):
    kwargs = {"headers": headers}
    if body is not None:
        kwargs["json"] = body
    return getattr(env.client, method)(url, **kwargs)


def operations():
    return {
        (method, path)
        for path, definition in API["paths"].items()
        for method in definition
        if method in {"get", "post", "put", "delete"}
    }


@pytest.mark.authz
def test_every_frozen_operation_is_covered(env, scenario):
    """If a new endpoint is added to the contract, this suite must classify it."""
    assert set(requests_for(env, scenario)) == operations()


@pytest.mark.authz
def test_bot_surface_is_exactly_health_and_channel_registration(env, scenario):
    """C1-C4 as one sweep: the whole contract, probed with one bot credential."""
    reached, refused = set(), {}
    for (method, path), (url, body) in requests_for(env, scenario).items():
        response = send(env, method, url, body, env.headers("bot", "bot"))
        if response.status_code < 400:
            reached.add((method, path))
        else:
            refused[(method, path)] = response.status_code
    assert reached == REACHABLE
    # Not merely "an error": every refusal is an authorization refusal, never a 400.
    assert set(refused.values()) == {403}, refused


@pytest.mark.authz
@pytest.mark.parametrize(
    "case,method,path",
    [
        ("C1", "get", "/negotiations/{negotiation_id}"),
        ("C2", "post", "/negotiations/{negotiation_id}/channel-bindings"),
        ("C3", "get", "/negotiations/{negotiation_id}/channel-bindings"),
        ("C4", "put", "/me/availability"),
        ("C4", "post", "/approvals/{approval_id}"),
        ("C4", "post", "/grants"),
    ],
)
def test_named_cases(env, scenario, case, method, path):
    """The six operations C1-C4 name individually, so a failure reports its case id."""
    url, body = requests_for(env, scenario)[(method, path)]
    assert send(env, method, url, body, env.headers("bot", "bot")).status_code == 403, case


@pytest.mark.authz
def test_the_same_requests_succeed_for_a_human(env, scenario):
    """Proves the 403s above are about the credential, not about a broken request."""
    for method, path in [
        ("get", "/negotiations/{negotiation_id}"),
        ("get", "/negotiations/{negotiation_id}/channel-bindings"),
        ("put", "/me/availability"),
        ("post", "/grants"),
    ]:
        url, body = requests_for(env, scenario)[(method, path)]
        response = send(env, method, url, body, env.headers())
        assert response.status_code < 400, (path, response.status_code, response.text)


@pytest.mark.authz
def test_a_bot_cannot_impersonate_a_student(env, scenario):
    """Owner requirement 7. kind=bot is refused even when sub names a real student."""
    for who in ("alice", "bob"):
        assert env.client.get("/v1/me", headers=env.headers(who, "bot")).status_code == 403
        assert (
            env.client.get(
                f"/v1/negotiations/{scenario['neg']}", headers=env.headers(who, "bot")
            ).status_code
            == 403
        )


@pytest.mark.authz
def test_a_bot_subject_cannot_become_human_by_claiming_it(env):
    """Swapping kind to human does not help: no Student row exists for the bot subject."""
    assert env.client.get("/v1/me", headers=env.headers("bot", "human")).status_code == 403


@pytest.mark.authz
@pytest.mark.parametrize(
    "name,header",
    [
        ("no header", {}),
        ("not bearer", {"Authorization": "Bot abc"}),
        ("garbage", {"Authorization": "Bearer not-a-jwt"}),
        ("empty token", {"Authorization": "Bearer "}),
    ],
)
def test_malformed_credentials_are_unauthorized(env, name, header):
    """Owner requirement 10. Malformed credentials never reach authorization."""
    assert env.client.post("/v1/channels", headers=header, json={}).status_code == 401, name


@pytest.mark.authz
def test_expired_wrong_key_and_wrong_issuer_credentials(env):
    """Owner requirement 10, continued -- all 401, none reaching the channel logic."""
    body = {
        "platform": "discord",
        "platform_channel_id": "4321",
        "max_disclosure_level": "free_busy",
    }
    expired = env.headers(
        "bot", "bot", exp=now() - timedelta(seconds=1), iat=now() - timedelta(hours=2)
    )
    wrong_key = env.headers("bot", "bot", key="x" * 48)
    wrong_issuer = env.headers("bot", "bot", iss="somebody-else")
    wrong_audience = env.headers("bot", "bot", aud="somebody-else")
    for name, headers in [
        ("expired", expired),
        ("wrong key", wrong_key),
        ("wrong issuer", wrong_issuer),
        ("wrong audience", wrong_audience),
    ]:
        assert env.client.post("/v1/channels", headers=headers, json=body).status_code == 401, name


@pytest.mark.authz
def test_a_bot_without_a_guild_claim_cannot_register(env):
    """The guild binding is what scopes a bot credential to one server."""
    response = env.client.post(
        "/v1/channels",
        headers=env.headers("bot", "bot", guild=None),
        json={
            "platform": "discord",
            "platform_channel_id": "9999",
            "max_disclosure_level": "free_busy",
        },
    )
    assert response.status_code == 403
