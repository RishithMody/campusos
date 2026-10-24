from copy import deepcopy
from datetime import timedelta

import pytest
from conftest import availability, create, grants, read, ready
from sqlalchemy import select

from backend.common import Problem, identifier, now
from backend.db.models import Audit, Commitment, Negotiation
from backend.inference.base import InferenceUnavailable
from backend.privacy.service import own_calendar
from backend.protocol.validation import API, contract


def test_every_endpoint_requires_auth(env):
    for path, methods in API["paths"].items():
        for method in methods:
            if method in {"get", "post", "put", "delete"}:
                response = env.client.request(method, "/v1" + path)
                assert response.status_code == 401
                assert response.headers["content-type"].startswith("application/problem+json")
    assert env.client.get("/v1/health", headers=env.headers()).json()["status"] == "ok"


def test_identity_and_handle_rotation(env):
    old = env.client.get("/v1/me", headers=env.headers()).json()
    new = env.client.post("/v1/me", headers=env.headers()).json()
    assert old != new
    assert env.client.get("/v1/me", headers=env.headers("bob")).json() != new
    assert (
        env.client.get(
            "/v1/me", headers=env.headers(kind="agent", agent_id=env.students["bob"].agent_id)
        ).status_code
        == 403
    )


def test_three_student_conflict_and_versioned_human_approval(env):
    state, _, _ = ready(env)
    assert state["status"] == "awaiting_approval"
    assert state["round"] == 3
    stale = None
    for who in ("alice", "bob", "carol"):
        state = read(env, state["negotiation_id"], who)
        contract(state, "negotiation-state")
        approval = state["pending_approvals"][0]
        if stale is None:
            stale = approval["state_version"]
        else:
            response = env.client.post(
                f"/v1/approvals/{approval['approval_id']}",
                headers=env.headers(who),
                json={"decision": "approve", "state_version": stale},
            )
            assert response.status_code == 409
        response = env.client.post(
            f"/v1/approvals/{approval['approval_id']}",
            headers=env.headers(who, "agent"),
            json={"decision": "approve", "state_version": approval["state_version"]},
        )
        assert response.status_code == 403
        response = env.client.post(
            f"/v1/approvals/{approval['approval_id']}",
            headers=env.headers(who),
            json={"decision": "approve", "state_version": approval["state_version"]},
        )
        assert response.status_code == 200, response.text
        state = response.json()
        assert not state["viewer"]["awaiting_me"]
        assert state["pending_approvals"] == []
        contract(state, "negotiation-state")
    assert state["status"] == "converged"
    assert all(v["vote"] == "accept" for v in state["proposals"][-1]["votes"])
    with env.sessions() as session:
        assert len(list(session.scalars(select(Commitment)))) == 3
    listing = env.client.get("/v1/negotiations?status=converged", headers=env.headers()).json()
    assert len(listing["negotiations"]) == 1


def test_failure_to_converge_and_inference_unavailable(env):
    state, window = create(env, max_rounds=1)
    grants(env, state, window)
    for i, who in enumerate(("alice", "bob", "carol")):
        availability(env, state, window, who, offset=i)
    result = read(env, state["negotiation_id"])
    assert result["status"] == "failed"
    assert result["outcome"] == {"kind": "max_rounds_exceeded", "requires_human_approval": True}
    env.inference.failure = InferenceUnavailable
    state, window = create(env)
    grants(env, state, window)
    for who in ("alice", "bob", "carol"):
        availability(env, state, window, who)
    assert read(env, state["negotiation_id"])["outcome"]["requires_human_approval"]


def test_no_overlap(env):
    state, window = create(env)
    grants(env, state, window)
    for who in ("alice", "bob", "carol"):
        availability(env, state, window, who, busy=who == "carol")
    result = read(env, state["negotiation_id"])
    assert result["status"] == "failed"
    assert result["outcome"]["kind"] == "no_overlap"


def test_direct_calendar_forged_identity_and_idor(env):
    with env.sessions() as session:
        with pytest.raises(Problem) as error:
            own_calendar(session, "alice", "bob")
        assert error.value.status == 403
    state, window = create(env)
    body = availability(env, state, window, "bob")
    response = env.client.put("/v1/me/availability", headers=env.headers(), json=body)
    assert response.status_code == 403
    response = env.client.get(
        f"/v1/negotiations/{state['negotiation_id']}", headers=env.headers("outsider")
    )
    assert response.status_code == 403
    assert "bob" not in response.text
    assert (
        env.client.post("/v1/me", headers=env.headers(), json={"user_id": "bob"}).status_code == 400
    )


def test_pseudonyms_are_negotiation_local(env):
    one, _ = create(env)
    two, _ = create(env)
    assert {p["student_ref"] for p in one["participants"]}.isdisjoint(
        {p["student_ref"] for p in two["participants"]}
    )


def test_missing_grants_do_not_run_or_disclose(env):
    state, window = create(env)
    for who in ("alice", "bob", "carol"):
        availability(env, state, window, who)
    state = read(env, state["negotiation_id"])
    assert state["status"] == "gathering"
    assert state["transcript"] == []


def test_decline_cancels_and_expiry(env):
    state, _, _ = ready(env)
    approval = state["pending_approvals"][0]
    response = env.client.post(
        f"/v1/approvals/{approval['approval_id']}",
        headers=env.headers(),
        json={"decision": "decline", "state_version": state["state_version"]},
    )
    assert response.json()["status"] == "cancelled"
    state, _ = create(env)
    with env.sessions.begin() as session:
        row = session.get(Negotiation, state["negotiation_id"])
        data = deepcopy(row.data)
        data["window"]["end"] = (now() - timedelta(seconds=1)).isoformat()
        row.data = data
    assert read(env, state["negotiation_id"])["status"] == "expired"


def proposal(env, state, window):
    return {
        "schema_version": "1.0",
        "message_id": identifier("msg"),
        "trace_id": state["trace_id"],
        "issued_at": now().isoformat(),
        "sender": {"agent_id": state["viewer"]["agent_id"], "agent_version": "1"},
        "represented_student": {"student_ref": state["viewer"]["student_ref"]},
        "scope": {
            "negotiation_id": state["negotiation_id"],
            "actions": ["propose"],
            "expires_at": window["end"],
            "max_disclosure_level": "free_busy",
            "granted_by": "standing",
        },
        "disclosure_level": "free_busy",
        "intent": "propose",
        "payload": {"proposed_slot": window, "note_for_own_student": "therapy private secret"},
    }


def test_protocol_errors_and_actual_outbound_privacy(env):
    state, window = create(env)
    ids = grants(env, state, window)
    body = proposal(env, state, window)
    url = f"/v1/negotiations/{state['negotiation_id']}/messages"
    assert env.client.post(url, headers=env.headers(), json={}).status_code == 400
    bad = deepcopy(body)
    bad["scope"]["expires_at"] = (now() - timedelta(seconds=1)).isoformat()
    assert env.client.post(url, headers=env.headers(), json=bad).status_code == 403
    bad = deepcopy(body)
    bad["disclosure_level"] = "full"
    assert env.client.post(url, headers=env.headers(), json=bad).status_code == 422
    response = env.client.post(url, headers=env.headers(), json=body)
    assert response.status_code == 202, response.text
    outbound = read(env, state["negotiation_id"], "bob")
    assert len(outbound["transcript"]) == 1
    assert "therapy" not in str(outbound)
    assert "note_for_own_student" not in str(outbound)
    assert env.client.post(url, headers=env.headers(), json=body).status_code == 409
    grant_id = next(g for owner, other, g in ids if owner == "alice" and other == "bob")
    assert (
        env.client.delete(f"/v1/grants/{grant_id}", headers=env.headers("bob")).status_code == 403
    )
    assert env.client.delete(f"/v1/grants/{grant_id}", headers=env.headers()).status_code == 204
    assert read(env, state["negotiation_id"], "bob")["transcript"] == []
    with env.sessions() as session:
        actions = {a.action for a in session.scalars(select(Audit))}
        assert {"grant_created", "cross_student_disclosure", "grant_revoked"} <= actions


def test_overdisclosing_availability_rejected(env):
    state, window = create(env)
    body = availability(env, state, window, "alice")
    body["slots"][0]["label"] = "therapy"
    response = env.client.put("/v1/me/availability", headers=env.headers(), json=body)
    assert response.status_code == 422
    assert "therapy" not in response.text


def test_chat_framing_and_terminal_failure(env):
    response = env.client.post("/v1/me/chat", headers=env.headers(), json={"message": "help"})
    assert "event: delta\n" in response.text and "event: done\n" in response.text
    env.inference.failure = InferenceUnavailable
    response = env.client.post("/v1/me/chat", headers=env.headers(), json={"message": "help"})
    assert "event: error\n" in response.text and "event: done\n" not in response.text


def test_agent_accept_requires_recorded_human_approval(env):
    state, window, _ = ready(env)
    msg = proposal(env, state, window)
    msg.update(intent="accept", in_reply_to=state["transcript"][-1]["message_id"])
    msg["scope"].update(actions=["accept"], granted_by="per_negotiation")
    msg["payload"] = {"proposed_slot": state["proposals"][-1]["slot"]}
    url = f"/v1/negotiations/{state['negotiation_id']}/messages"
    assert env.client.post(url, headers=env.headers(kind="agent"), json=msg).status_code == 403
    approval = state["pending_approvals"][0]
    assert (
        env.client.post(
            f"/v1/approvals/{approval['approval_id']}",
            headers=env.headers(),
            json={"decision": "approve", "state_version": state["state_version"]},
        ).status_code
        == 200
    )
    response = env.client.post(url, headers=env.headers(kind="agent"), json=msg)
    assert response.status_code == 202, response.text
    assert response.json()["status"] == "awaiting_approval"
    assert response.json()["transcript"][-1]["intent"] == "accept"


def test_private_notes_only_in_own_chat_and_never_in_model_prompt(env):
    state, window = create(env)
    grants(env, state, window)
    response = env.client.post(
        f"/v1/negotiations/{state['negotiation_id']}/messages",
        headers=env.headers(),
        json=proposal(env, state, window),
    )
    assert response.status_code == 202
    sent = []
    original = env.inference.complete

    async def capture(request):
        sent.append(request)
        return await original(request)

    env.inference.complete = capture
    body = {
        "message": "why did you decline my therapy appointment?",
        "negotiation_id": state["negotiation_id"],
    }
    own = env.client.post("/v1/me/chat", headers=env.headers(), json=body)
    other = env.client.post("/v1/me/chat", headers=env.headers("bob"), json=body)
    assert "therapy private secret" in own.text
    assert "therapy" not in other.text
    assert all("therapy" not in str(r.messages) for r in sent)
