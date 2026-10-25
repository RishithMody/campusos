"""C5-C7: the consent gate a connector sees, and who owns a registered channel."""

import pytest

from tests.integration.connector.environment import (
    bind,
    create,
    decide,
    link_all,
    read,
    register,
)


def summary_url(neg, channel):
    return f"/v1/negotiations/{neg}/channel-summary?channel_id={channel}"


def confirmed_channel(env, platform="1234"):
    """A channel linked by everyone and bound to a fresh negotiation, not yet decided."""
    state, _ = create(env)
    neg = state["negotiation_id"]
    channel = register(env, platform_channel=platform).json()["channel_id"]
    link_all(env, channel)
    bind(env, neg, channel)
    return neg, channel


@pytest.mark.privacy
@pytest.mark.authz
def test_c5_every_unconsented_state_is_byte_identical(env):
    """C5. Five reasons to refuse, one indistinguishable answer.

    A bot that could tell `declined` from `pending` could report a private no into the
    room the decision was about. The bodies must match byte for byte, not merely share
    a status code.
    """
    bot = env.headers("bot", "bot")
    responses = {}

    # absent -- registered, never bound to this negotiation
    state, _ = create(env)
    channel = register(env, platform_channel="1000").json()["channel_id"]
    responses["absent"] = env.client.get(summary_url(state["negotiation_id"], channel), headers=bot)

    # pending_consent -- bound, nobody has answered
    neg, channel = confirmed_channel(env, platform="1001")
    responses["pending_consent"] = env.client.get(summary_url(neg, channel), headers=bot)

    # declined -- one participant said no
    neg, channel = confirmed_channel(env, platform="1002")
    decide(env, neg, "carol", "decline")
    responses["declined"] = env.client.get(summary_url(neg, channel), headers=bot)

    # withdrawn -- everyone approved, then one withdrew
    neg, channel = confirmed_channel(env, platform="1003")
    for who in ("alice", "bob", "carol"):
        decide(env, neg, who)
    assert env.client.get(summary_url(neg, channel), headers=bot).status_code == 200
    assert (
        env.client.delete(
            f"/v1/negotiations/{neg}/channel-bindings/{channel}", headers=env.headers("bob")
        ).status_code
        == 204
    )
    responses["withdrawn"] = env.client.get(summary_url(neg, channel), headers=bot)

    # pending_reconsent -- confirmed, then the room grew
    neg, channel = confirmed_channel(env, platform="1004")
    for who in ("alice", "bob", "carol"):
        decide(env, neg, who)
    assert env.client.get(summary_url(neg, channel), headers=bot).status_code == 200
    env.discord.size = 4
    responses["pending_reconsent"] = env.client.get(summary_url(neg, channel), headers=bot)

    assert set(responses) == {
        "absent",
        "pending_consent",
        "declined",
        "withdrawn",
        "pending_reconsent",
    }
    assert {name: r.status_code for name, r in responses.items()} == dict.fromkeys(responses, 403)
    bodies = {name: r.content for name, r in responses.items()}
    assert len(set(bodies.values())) == 1, bodies
    # Nothing in the refusal hints at which state produced it.
    body = next(iter(bodies.values())).decode()
    for leak in ("declin", "withdraw", "pending", "reconsent", "consent"):
        assert leak not in body.lower(), body


@pytest.mark.privacy
@pytest.mark.parametrize(
    "level,expected", [("none", 201), ("free_busy", 201), ("category", 400), ("full", 400)]
)
def test_c6_channel_disclosure_level_is_capped_by_the_schema(env, level, expected):
    """C6. `category` and `full` say *why* someone is busy; a room is the wrong audience.

    Rejected by the frozen schema, so neither the backend nor a connector can opt in.
    """
    response = register(env, platform_channel=f"20{len(level)}", level=level)
    assert response.status_code == expected, response.text


@pytest.mark.authz
def test_c7_a_different_bot_subject_cannot_take_over_a_channel(env):
    """C7. `channel.bot` is pinned at registration; re-registration by another subject fails."""
    first = register(env, subject="bot", platform_channel="3001")
    assert first.status_code == 201
    again = register(env, subject="bot", platform_channel="3001")
    assert again.status_code == 201
    assert again.json()["channel_id"] == first.json()["channel_id"]
    stolen = register(env, subject="otherbot", platform_channel="3001")
    assert stolen.status_code == 403


@pytest.mark.authz
def test_c7_summary_is_readable_only_by_the_registering_subject_and_guild(env):
    """Subject stability matters operationally: re-issuing with a new `sub` orphans channels."""
    neg, channel = confirmed_channel(env, platform="3002")
    for who in ("alice", "bob", "carol"):
        decide(env, neg, who)
    url = summary_url(neg, channel)
    assert env.client.get(url, headers=env.headers("bot", "bot")).status_code == 200
    assert env.client.get(url, headers=env.headers("otherbot", "bot")).status_code == 403
    assert env.client.get(url, headers=env.headers("bot", "bot", guild="999")).status_code == 403
    assert env.client.get(url, headers=env.headers()).status_code == 403


@pytest.mark.authz
def test_binding_requires_a_verified_channel_identity(env):
    """Owner requirement 6. Consent to post is reachable only after identity binding."""
    state, _ = create(env)
    neg = state["negotiation_id"]
    channel = register(env, platform_channel="3003").json()["channel_id"]
    unlinked = env.client.post(
        f"/v1/negotiations/{neg}/channel-bindings",
        headers=env.headers(),
        json={"channel_id": channel},
    )
    assert unlinked.status_code == 403
    link_all(env, channel, names=("alice",))
    assert (
        env.client.post(
            f"/v1/negotiations/{neg}/channel-bindings",
            headers=env.headers(),
            json={"channel_id": channel},
        ).status_code
        == 201
    )


@pytest.mark.authz
def test_a_student_discord_knows_nothing_about_cannot_link(env):
    """`outsider` has a stored discord_id that is not a member of the room."""
    channel = register(env, platform_channel="3004").json()["channel_id"]
    response = env.client.post(f"/v1/channels/{channel}/members", headers=env.headers("outsider"))
    assert response.status_code == 403


@pytest.mark.privacy
def test_a_confirmed_summary_carries_no_names_or_prose(env):
    """What the connector is finally allowed to read, checked for the obvious leaks."""
    neg, channel = confirmed_channel(env, platform="3005")
    for who in ("alice", "bob", "carol"):
        decide(env, neg, who)
    response = env.client.get(summary_url(neg, channel), headers=env.headers("bot", "bot"))
    assert response.status_code == 200
    body = response.json()
    assert set(body) <= {
        "negotiation_id",
        "status",
        "round",
        "max_rounds",
        "template_id",
        "participant_count",
        "agreed_slot",
        "timezone",
    }
    for name in ("alice", "bob", "carol", "outsider"):
        assert name not in response.text
    state = read(env, neg)
    assert state["viewer"]["student_ref"] not in response.text
