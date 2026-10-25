import asyncio

import httpx
import pytest
from conftest import availability, create, grants, read
from sqlalchemy import func, select

from backend.db.models import Commitment
from groupchat.api import API
from groupchat.publisher import Publisher


def client(env):
    def handle(request):
        response = env.client.request(
            request.method,
            str(request.url),
            content=request.content,
            headers=dict(request.headers),
        )
        return httpx.Response(response.status_code, content=response.content)

    token = env.headers("bot", "bot")["Authorization"].removeprefix("Bearer ")
    return API("http://localhost/v1", token, transport=httpx.MockTransport(handle))


def consent(env, neg, action, decision="approve", who="alice"):
    state = read(env, neg, who)
    approval = next(a for a in state["pending_approvals"] if a["action"] == action)
    response = env.client.post(
        f"/v1/approvals/{approval['approval_id']}",
        headers=env.headers(who),
        json={"decision": decision, "state_version": approval["state_version"]},
    )
    assert response.status_code == 200, response.text


def bind(env, neg, channel):
    for who in ("alice", "bob", "carol"):
        assert (
            env.client.post(f"/v1/channels/{channel}/members", headers=env.headers(who)).status_code
            == 204
        )
    assert (
        env.client.post(
            f"/v1/negotiations/{neg}/channel-bindings",
            headers=env.headers(),
            json={"channel_id": channel},
        ).status_code
        == 201
    )


@pytest.mark.parametrize("no_overlap", [False, True])
def test_three_students_real_backend_mock_inference(env, no_overlap):
    async def scenario():
        api = client(env)
        messages = []

        async def send(text):
            messages.append(text)

        try:
            state, window = create(env)
            neg = state["negotiation_id"]
            channel = await api.register(1234)
            bind(env, neg, channel)
            assert not await Publisher(api).update(neg, channel, send)
            assert not messages
            for who in ("alice", "bob", "carol"):
                consent(env, neg, "post_to_channel", who=who)
            # A refused publisher is spent, exactly as the bot's watcher is: it breaks
            # out of its loop on the first False. Resuming is a new publisher.
            publisher = Publisher(api)
            assert await publisher.update(neg, channel, send)
            assert messages == ["Collecting availability from 3 people."]
            grants(env, state, window)
            for i, who in enumerate(("alice", "bob", "carol")):
                availability(env, state, window, who, offset=i, busy=no_overlap and who == "carol")
            current = read(env, neg)
            if no_overlap:
                assert current["status"] == "failed"
                assert not await publisher.update(neg, channel, send)
                assert messages[-1] == "No time works for everyone in this window."
            else:
                assert current["status"] == "awaiting_approval"
                assert current["proposals"][0]["slot"]["start"]
                assert await publisher.update(neg, channel, send)
                for who in ("alice", "bob"):
                    consent(env, neg, "commit_slot", who=who)
                with env.sessions() as session:
                    assert session.scalar(select(func.count()).select_from(Commitment)) == 0
                assert await publisher.update(neg, channel, send)
                assert messages[-1] == "Waiting on everyone to confirm."
                consent(env, neg, "commit_slot", who="carol")
                assert not await publisher.update(neg, channel, send)
                assert messages[-1].startswith("Locked in: ")
                with env.sessions() as session:
                    assert session.scalar(select(func.count()).select_from(Commitment)) == 3
            assert all("alice" not in m and "therapy" not in m for m in messages)
        finally:
            await api.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("change", ["decline", "withdraw", "growth"])
def test_consent_denial_posts_nothing(env, change):
    async def scenario():
        api = client(env)
        messages = []

        async def send(text):
            messages.append(text)

        try:
            state, _ = create(env)
            neg = state["negotiation_id"]
            channel = await api.register(1234)
            bind(env, neg, channel)
            publisher = Publisher(api)
            if change == "decline":
                consent(env, neg, "post_to_channel", decision="decline")
            else:
                for who in ("alice", "bob", "carol"):
                    consent(env, neg, "post_to_channel", who=who)
                assert await publisher.update(neg, channel, send)
                messages.clear()
                if change == "withdraw":
                    assert (
                        env.client.delete(
                            f"/v1/negotiations/{neg}/channel-bindings/{channel}",
                            headers=env.headers("bob"),
                        ).status_code
                        == 204
                    )
                else:
                    env.discord.viewers.add("99")
            assert not await publisher.update(neg, channel, send)
            assert messages == []
            if change == "growth":
                for who in ("alice", "bob", "carol"):
                    consent(env, neg, "post_to_channel", who=who)
                assert await Publisher(api).update(neg, channel, send)
                assert len(messages) == 1
        finally:
            await api.close()

    asyncio.run(scenario())


def withdraw(env, neg, channel, who="bob"):
    response = env.client.delete(
        f"/v1/negotiations/{neg}/channel-bindings/{channel}", headers=env.headers(who)
    )
    assert response.status_code == 204, response.text


def test_consent_revoked_between_authorization_and_send(env):
    """The window no architecture closes: authorized here, posted in Discord.

    `send` withdraws consent before the message lands, which is the worst ordering
    available -- the post is already in flight when the binding dies. What must hold is
    not that the post never happens; it is that the post is one the room was already
    consented to receive, that nothing further is published, and that the publisher does
    not have to be told twice.
    """

    async def scenario():
        api = client(env)
        messages = []
        try:
            state, _ = create(env)
            neg = state["negotiation_id"]
            channel = await api.register(1234)
            bind(env, neg, channel)
            for who in ("alice", "bob", "carol"):
                consent(env, neg, "post_to_channel", who=who)

            async def send(text):
                # Revocation commits while this message is on its way to Discord.
                withdraw(env, neg, channel)
                messages.append(text)

            publisher = Publisher(api)
            assert await publisher.update(neg, channel, send)
            assert messages == ["Collecting availability from 3 people."]

            # Nothing more is published, by this publisher or a fresh one.
            assert not await publisher.update(neg, channel, send)
            assert not await Publisher(api).update(neg, channel, send)
            assert len(messages) == 1
        finally:
            await api.close()

    asyncio.run(scenario())


def test_a_refused_publisher_stops_asking_as_well_as_stops_posting(env):
    """The stop is local, not advisory: a caller that ignores False still publishes nothing.

    Checked by counting requests, because a publisher that kept polling would keep a
    withdrawn negotiation's summary one authorization away from the room.
    """

    async def scenario():
        paths = []

        def handle(request):
            paths.append(request.url.path)
            response = env.client.request(
                request.method,
                str(request.url),
                content=request.content,
                headers=dict(request.headers),
            )
            return httpx.Response(response.status_code, content=response.content)

        token = env.headers("bot", "bot")["Authorization"].removeprefix("Bearer ")
        api = API("http://localhost/v1", token, transport=httpx.MockTransport(handle))
        messages = []

        async def send(text):
            messages.append(text)

        try:
            state, _ = create(env)
            neg = state["negotiation_id"]
            channel = await api.register(1234)
            bind(env, neg, channel)
            for who in ("alice", "bob", "carol"):
                consent(env, neg, "post_to_channel", who=who)
            publisher = Publisher(api)
            assert await publisher.update(neg, channel, send)
            withdraw(env, neg, channel)
            paths.clear()
            assert not await publisher.update(neg, channel, send)
            refused = len(paths)
            assert refused == 1
            for _ in range(5):
                assert not await publisher.update(neg, channel, send)
            assert len(paths) == refused, paths
            assert messages == ["Collecting availability from 3 people."]
        finally:
            await api.close()

    asyncio.run(scenario())
