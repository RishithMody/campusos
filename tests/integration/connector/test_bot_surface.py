"""C1-C4: what a kind=bot credential can reach, probed with valid bodies.

The point of this file is the *method*. An earlier manual probe reported 400 for five
operations and those 400s were nearly mistaken for authorization enforcement -- they were
schema rejections raised before the service layer ran. A 400 says the request was
malformed; only a 403 says the caller was refused.

So every operation below is defined once, as a builder that arranges a scenario in which
the *authorized* principal genuinely succeeds. The same builder is then driven twice:
once with the credential that should work, once with a bot credential. The two runs differ
only in the token, which is the only way a 403 can be attributed to the credential rather
than to the request, the resource, or the state of the negotiation.

Attempt 1 of this suite asserted success for only four operations. Review found that the
C2 request returned 409 (already bound) and message submission returned 403 (a missing
participant grant) -- both would have passed the bot sweep for the wrong reason.
"""

from datetime import timedelta

import pytest

from backend.common import identifier, now
from backend.protocol.validation import API
from tests.integration.connector.environment import (
    all_grants,
    bind,
    create,
    grant,
    link_all,
    read,
    register,
    window_from_now,
)

# Every HTTP method OpenAPI 3.1 allows in a path item. Enumerating only the four we
# happen to use would let a PATCH added to the contract escape this suite unnoticed.
HTTP_METHODS = frozenset({"get", "put", "post", "delete", "options", "head", "patch", "trace"})
PATH_ITEM_KEYS = frozenset({"$ref", "summary", "description", "servers", "parameters"})

BUILDERS = {}


def operations(paths=None):
    """Operations in an OpenAPI paths object, independent of what the app registers."""
    paths = API["paths"] if paths is None else paths
    return {
        (method, path) for path, item in paths.items() for method in item if method in HTTP_METHODS
    }


def builder(method, path, principal, ok):
    """Register one operation: who may call it, and the exact status that means success."""

    def register_builder(fn):
        BUILDERS[(method, path)] = (principal, ok, fn)
        return fn

    return register_builder


def send(env, method, url, body, headers):
    if url.endswith("/stream"):
        # Bounded on purpose: read the status line and close without draining the stream.
        with env.client.stream("GET", url, headers=headers) as response:
            return response.status_code
    kwargs = {"headers": headers}
    if body is not None:
        kwargs["json"] = body
    return getattr(env.client, method)(url, **kwargs).status_code


# --------------------------------------------------------------------------- builders
# Each arranges its own scenario. Setup uses whichever principal is entitled to perform
# it; only the final request under test varies by credential.


@builder("get", "/health", "public", 200)
def _health(env):
    return "/v1/health", None


@builder("get", "/me", "human", 200)
def _me(env):
    return "/v1/me", None


@builder("post", "/me", "human", 200)
def _rotate_handle(env):
    return "/v1/me", None


@builder("post", "/me/chat", "human", 200)
def _chat(env):
    state, _ = create(env)
    return "/v1/me/chat", {
        "message": "when are we meeting?",
        "negotiation_id": state["negotiation_id"],
    }


@builder("put", "/me/availability", "human", 204)
def _availability(env):
    state, window = create(env)
    viewer = read(env, state["negotiation_id"])
    return "/v1/me/availability", {
        "schema_version": "1.0",
        "student_ref": viewer["viewer"]["student_ref"],
        "generated_at": now().isoformat(),
        "timezone": "UTC",
        "window": window,
        "disclosure_level": "free_busy",
        "slots": [{"start": window["start"], "end": window["end"], "state": "free"}],
    }


@builder("get", "/negotiations", "human", 200)
def _list_negotiations(env):
    create(env)
    return "/v1/negotiations", None


@builder("post", "/negotiations", "human", 201)
def _create_negotiation(env):
    return "/v1/negotiations", {
        "invitees": [env.students["bob"].contact_handle],
        "window": window_from_now(days=3),
        "max_rounds": 5,
    }


@builder("get", "/negotiations/{negotiation_id}", "human", 200)
def _read_negotiation(env):
    state, _ = create(env)
    return f"/v1/negotiations/{state['negotiation_id']}", None


@builder("post", "/negotiations/{negotiation_id}/messages", "human", 202)
def _submit_message(env):
    state, window = create(env)
    neg = state["negotiation_id"]
    # Every pair, not just alice -> bob: submit checks authority for each participant.
    all_grants(env, neg, window)
    viewer = read(env, neg)
    return f"/v1/negotiations/{neg}/messages", {
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


@builder("get", "/negotiations/{negotiation_id}/stream", "human", 200)
def _stream(env):
    state, _ = create(env)
    return f"/v1/negotiations/{state['negotiation_id']}/stream", None


@builder("post", "/approvals/{approval_id}", "human", 200)
def _decide_approval(env):
    state, _ = create(env)
    neg = state["negotiation_id"]
    channel = register(env, platform_channel="7001").json()["channel_id"]
    link_all(env, channel)
    bind(env, neg, channel)
    viewer = read(env, neg)
    approval = next(a for a in viewer["pending_approvals"] if a["action"] == "post_to_channel")
    return f"/v1/approvals/{approval['approval_id']}", {
        "decision": "approve",
        "state_version": viewer["state_version"],
    }


@builder("post", "/channels", "bot", 201)
def _register_channel(env):
    return "/v1/channels", {
        "platform": "discord",
        "platform_channel_id": "7002",
        "max_disclosure_level": "free_busy",
    }


@builder("post", "/channels/{channel_id}/members", "human", 204)
def _link_member(env):
    channel = register(env, platform_channel="7003").json()["channel_id"]
    return f"/v1/channels/{channel}/members", None


@builder("post", "/negotiations/{negotiation_id}/channel-bindings", "human", 201)
def _request_binding(env):
    state, _ = create(env)
    channel = register(env, platform_channel="7004").json()["channel_id"]
    link_all(env, channel)
    # Deliberately NOT bound: binding an already-bound channel is 409, which would make
    # this control prove nothing. This was review finding 1.
    return f"/v1/negotiations/{state['negotiation_id']}/channel-bindings", {"channel_id": channel}


@builder("get", "/negotiations/{negotiation_id}/channel-bindings", "human", 200)
def _list_bindings(env):
    state, _ = create(env)
    return f"/v1/negotiations/{state['negotiation_id']}/channel-bindings", None


@builder("delete", "/negotiations/{negotiation_id}/channel-bindings/{channel_id}", "human", 204)
def _withdraw_binding(env):
    state, _ = create(env)
    neg = state["negotiation_id"]
    channel = register(env, platform_channel="7005").json()["channel_id"]
    link_all(env, channel)
    bind(env, neg, channel)
    return f"/v1/negotiations/{neg}/channel-bindings/{channel}", None


@builder("get", "/negotiations/{negotiation_id}/channel-summary", "bot", 200)
def _channel_summary(env):
    state, _ = create(env)
    neg = state["negotiation_id"]
    channel = register(env, platform_channel="7006").json()["channel_id"]
    link_all(env, channel)
    bind(env, neg, channel)
    for who in ("alice", "bob", "carol"):
        viewer = read(env, neg, who)
        approval = next(a for a in viewer["pending_approvals"] if a["action"] == "post_to_channel")
        env.client.post(
            f"/v1/approvals/{approval['approval_id']}",
            headers=env.headers(who),
            json={"decision": "approve", "state_version": viewer["state_version"]},
        )
    return f"/v1/negotiations/{neg}/channel-summary?channel_id={channel}", None


@builder("post", "/grants", "human", 201)
def _create_grant(env):
    state, window = create(env)
    return "/v1/grants", {
        "negotiation_id": state["negotiation_id"],
        "grantee_agent_id": env.students["bob"].agent_id,
        "max_disclosure_level": "free_busy",
        # Expiry may not exceed the negotiation window, or a human gets 400 and the
        # bot's 403 proves nothing.
        "expires_at": window["end"],
    }


@builder("delete", "/grants/{grant_id}", "human", 204)
def _revoke_grant(env):
    state, window = create(env)
    grant_id = grant(env, state["negotiation_id"], "alice", "bob", window)
    return f"/v1/grants/{grant_id}", None


# ----------------------------------------------------------------------------- tests

HUMAN_ONLY = sorted(
    (method, path) for (method, path), (principal, _, _) in BUILDERS.items() if principal == "human"
)
ALL_OPERATIONS = sorted(BUILDERS)


def ident(op):
    return f"{op[0].upper()} {op[1]}"


@pytest.mark.authz
def test_every_frozen_operation_has_a_builder(env):
    """If an operation is added to the contract, this suite must classify it."""
    assert set(BUILDERS) == operations()


@pytest.mark.authz
def test_path_items_contain_nothing_this_suite_would_skip():
    """Guards the enumerator itself: an unrecognised key would be silently dropped."""
    for path, item in API["paths"].items():
        assert set(item) <= HTTP_METHODS | PATH_ITEM_KEYS, path


@pytest.mark.authz
@pytest.mark.parametrize("method", sorted(HTTP_METHODS))
def test_an_added_operation_of_any_method_is_not_silently_ignored(method):
    """Review finding 2: the enumerator covered only get/post/put/delete.

    A PATCH added to the contract was invisible, so the coverage equality check would
    still have passed while an unclassified operation existed.
    """
    synthetic = {"/synthetic": {method: {}, "parameters": []}}
    assert operations(synthetic) == {(method, "/synthetic")}
    assert (method, "/synthetic") not in BUILDERS


@pytest.mark.authz
@pytest.mark.parametrize("op", ALL_OPERATIONS, ids=ident)
def test_the_authorized_principal_succeeds(env, op):
    """Every operation, performed by whoever is entitled to -- exact status, not `< 400`.

    Without this, a bot's 403 could mean the request was never valid for anyone.
    """
    principal, expected, build = BUILDERS[op]
    url, body = build(env)
    headers = {
        "public": env.headers("bot", "bot"),
        "human": env.headers(),
        "bot": env.headers("bot", "bot"),
    }[principal]
    assert send(env, op[0], url, body, headers) == expected


@pytest.mark.authz
@pytest.mark.parametrize("subject", ["bot", "alice"])
@pytest.mark.parametrize("op", HUMAN_ONLY, ids=ident)
def test_a_bot_credential_is_refused_on_every_human_operation(env, op, subject):
    """C1-C4. The identical scenario and request, differing only in the credential.

    `subject="alice"` matters: the bot subject has no Student row, so a 403 could come
    from the missing row rather than from kind enforcement. Naming a real student rules
    that out. This was part of review finding 1.
    """
    _, _, build = BUILDERS[op]
    url, body = build(env)
    assert send(env, op[0], url, body, env.headers(subject, "bot")) == 403


@pytest.mark.authz
def test_the_reachable_set_is_exactly_health_and_channel_registration(env):
    """The summary claim, stated once: two operations, and only two."""
    assert {op for op, (principal, _, _) in BUILDERS.items() if principal != "human"} == {
        ("get", "/health"),
        ("post", "/channels"),
        ("get", "/negotiations/{negotiation_id}/channel-summary"),
    }
    # The third is bot-authorized only behind confirmed consent; C5 and C7 pin that gate.


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
    cases = {
        "expired": env.headers(
            "bot", "bot", exp=now() - timedelta(seconds=1), iat=now() - timedelta(hours=2)
        ),
        "wrong key": env.headers("bot", "bot", key="x" * 48),
        "wrong issuer": env.headers("bot", "bot", iss="somebody-else"),
        "wrong audience": env.headers("bot", "bot", aud="somebody-else"),
    }
    for name, headers in cases.items():
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
