import ast
from pathlib import Path

import pytest
from conftest import create, read

from backend.channels.discord import ADMINISTRATOR, VIEW_CHANNEL, can_view
from backend.channels.summary import summary
from backend.protocol.validation import API, validate


def bind(env):
    state, _ = create(env)
    response = env.client.post(
        "/v1/channels",
        headers=env.headers("bot", "bot"),
        json={
            "platform": "discord",
            "platform_channel_id": "1234",
            "max_disclosure_level": "free_busy",
        },
    )
    assert response.status_code == 201, response.text
    channel = response.json()["channel_id"]
    assert not response.json()["confirmed"]
    assert (
        env.client.post(
            f"/v1/channels/{channel}/members", headers=env.headers("bot", "bot")
        ).status_code
        == 403
    )
    assert (
        env.client.post(f"/v1/channels/{channel}/members", headers=env.headers()).status_code == 204
    )
    response = env.client.post(
        f"/v1/negotiations/{state['negotiation_id']}/channel-bindings",
        headers=env.headers(),
        json={"channel_id": channel},
    )
    assert response.status_code == 201, response.text
    return state["negotiation_id"], channel


def decide(env, neg, who, decision="approve"):
    state = read(env, neg, who)
    approval = next(a for a in state["pending_approvals"] if a["action"] == "post_to_channel")
    response = env.client.post(
        f"/v1/approvals/{approval['approval_id']}",
        headers=env.headers(who),
        json={"decision": decision, "state_version": state["state_version"]},
    )
    assert response.status_code == 200, response.text


def test_channel_consent_reconsent_and_withdrawal(env):
    neg, channel = bind(env)
    url = f"/v1/negotiations/{neg}/channel-summary?channel_id={channel}"
    assert env.client.get(url, headers=env.headers("bot", "bot")).status_code == 403
    for who in ("alice", "bob", "carol"):
        decide(env, neg, who)
    response = env.client.get(url, headers=env.headers("bot", "bot"))
    assert response.status_code == 200, response.text
    assert response.json()["template_id"] == "gathering_availability"
    assert "alice" not in response.text
    assert env.client.get(url, headers=env.headers()).status_code == 403
    assert env.client.get(url, headers=env.headers("otherbot", "bot")).status_code == 403
    env.discord.size = 4
    assert env.client.get(url, headers=env.headers("bot", "bot")).status_code == 403
    bindings = env.client.get(
        f"/v1/negotiations/{neg}/channel-bindings", headers=env.headers()
    ).json()
    assert bindings["bindings"][0]["status"] == "pending_reconsent"
    for who in ("alice", "bob", "carol"):
        decide(env, neg, who)
    assert env.client.get(url, headers=env.headers("bot", "bot")).status_code == 200
    assert (
        env.client.delete(
            f"/v1/negotiations/{neg}/channel-bindings/{channel}", headers=env.headers("bob")
        ).status_code
        == 204
    )
    assert env.client.get(url, headers=env.headers("bot", "bot")).status_code == 403


def test_declined_and_pending_are_indistinguishable_to_bot(env):
    neg, channel = bind(env)
    url = f"/v1/negotiations/{neg}/channel-summary?channel_id={channel}"
    before = env.client.get(url, headers=env.headers("bot", "bot"))
    decide(env, neg, "carol", "decline")
    after = env.client.get(url, headers=env.headers("bot", "bot"))
    assert before.status_code == after.status_code == 403
    assert before.content == after.content


@pytest.mark.parametrize(
    "status,kind",
    [
        ("gathering", None),
        ("negotiating", None),
        ("awaiting_approval", None),
        ("converged", "agreed"),
        ("failed", "no_overlap"),
        ("failed", "max_rounds_exceeded"),
        ("expired", "timed_out"),
        ("cancelled", "withdrawn"),
    ],
)
def test_all_channel_states_closed_vocabulary(env, status, kind):
    state, window = create(env)
    data = {
        **state,
        "status": status,
        "members": {"alice": {}, "bob": {}, "carol": {}},
        "outcome": {"kind": kind, "agreed_slot": window},
        "private_text": "therapy",
    }
    result = summary(data, "UTC")
    validate(result, API["components"]["schemas"]["ChannelSummary"])
    assert "therapy" not in str(result)
    assert set(result) <= {
        "negotiation_id",
        "status",
        "round",
        "max_rounds",
        "template_id",
        "participant_count",
        "agreed_slot",
        "timezone",
    }
    assert (
        result["template_id"]
        in API["components"]["schemas"]["ChannelSummary"]["properties"]["template_id"]["enum"]
    )


def test_summary_has_no_inference_dependency():
    tree = ast.parse(Path("backend/channels/summary.py").read_text())
    imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any("inference" in (module or "") for module in imports)


def test_discord_overwrite_order():
    guild = {
        "id": "1",
        "owner_id": "9",
        "roles": [
            {"id": "1", "permissions": str(VIEW_CHANNEL)},
            {"id": "2", "permissions": "0"},
            {"id": "3", "permissions": str(ADMINISTRATOR)},
        ],
    }
    member = {"user": {"id": "5"}, "roles": ["2"]}
    room = {
        "permission_overwrites": [{"id": "1", "type": 0, "deny": str(VIEW_CHANNEL), "allow": "0"}]
    }
    assert not can_view(member, guild, room)
    room["permission_overwrites"].append(
        {"id": "2", "type": 0, "deny": "0", "allow": str(VIEW_CHANNEL)}
    )
    assert can_view(member, guild, room)
    room["permission_overwrites"].append(
        {"id": "5", "type": 1, "deny": str(VIEW_CHANNEL), "allow": "0"}
    )
    assert not can_view(member, guild, room)
    member["roles"].append("3")
    assert can_view(member, guild, room)


def test_obsolete_channel_approval_cannot_confirm_new_audience(env):
    neg, channel = bind(env)
    old = read(env, neg, "bob")["pending_approvals"][0]
    assert (
        env.client.delete(
            f"/v1/negotiations/{neg}/channel-bindings/{channel}", headers=env.headers()
        ).status_code
        == 204
    )
    assert read(env, neg, "bob")["pending_approvals"] == []
    env.discord.size = 10
    response = env.client.post(
        f"/v1/negotiations/{neg}/channel-bindings",
        headers=env.headers(),
        json={"channel_id": channel},
    )
    assert response.status_code == 201
    current = read(env, neg, "bob")
    assert "10 channel accounts" in current["pending_approvals"][0]["discloses"]["summary"]
    response = env.client.post(
        f"/v1/approvals/{old['approval_id']}",
        headers=env.headers("bob"),
        json={"decision": "approve", "state_version": current["state_version"]},
    )
    assert response.status_code == 409
