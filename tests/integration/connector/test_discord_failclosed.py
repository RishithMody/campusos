"""Owner requirement 8: Discord audience verification and fail-closed behaviour.

Not one of C1-C9. Added because `DiscordREST` -- the component that decides how many
people can read a room, and therefore what channel consent is consented *to* -- had no
tests at all. `can_view` was pinned against fixtures; the HTTP client around it was not.

Everything here uses `httpx.MockTransport`. No Discord connection, no token.
"""

import asyncio

import httpx
import pytest

from backend.channels.discord import VIEW_CHANNEL, DiscordREST
from backend.common import Problem

GUILD = "123"
CHANNEL = "456"
BOT = "900"
TOKEN = "a-fake-bot-token-that-must-never-be-echoed"  # noqa: S105  pragma: allowlist secret


def world(members, *, channel_type=0, guild_id=GUILD, everyone=VIEW_CHANNEL, status=200, owner="1"):
    """A minimal Discord, serving exactly the four endpoints DiscordREST calls."""
    guild = {
        "id": GUILD,
        "owner_id": owner,
        "roles": [{"id": GUILD, "permissions": str(everyone)}],
    }
    channel = {"guild_id": guild_id, "type": channel_type, "permission_overwrites": []}

    def handle(request):
        path = request.url.path
        if path.endswith(f"/channels/{CHANNEL}"):
            return httpx.Response(status, json=channel)
        if path.endswith(f"/guilds/{GUILD}"):
            return httpx.Response(status, json=guild)
        if path.endswith("/users/@me"):
            return httpx.Response(status, json={"id": BOT})
        if "/members/" in path:
            user = path.rsplit("/", 1)[-1]
            found = next((m for m in members if m["user"]["id"] == user), None)
            if found is None:
                return httpx.Response(404, json={})
            return httpx.Response(status, json=found)
        if path.endswith("/members"):
            after = int(request.url.params.get("after", 0))
            page = [m for m in members if int(m["user"]["id"]) > after][:1000]
            return httpx.Response(status, json=page)
        return httpx.Response(404, json={})

    return httpx.MockTransport(handle)


def member(user, roles=()):
    return {"user": {"id": user}, "roles": list(roles)}


def run(coro):
    return asyncio.run(coro)


def client(transport, token=TOKEN):
    return DiscordREST(token, transport=transport)


def test_audience_counts_only_members_who_can_view():
    people = [member(BOT), member("1"), member("2"), member("3")]
    audience = run(client(world(people)).audience(CHANNEL, GUILD))
    assert audience.size == 4
    assert audience.guild == GUILD


def test_audience_excludes_members_who_cannot_view():
    """@everyone denied VIEW_CHANNEL. The bot owns the guild, so only it can read the room.

    This is the number consent is given against: if it counted members who cannot see the
    channel, the audience-growth re-consent rule would fire on people who can read nothing.
    """
    people = [member(BOT), member("1"), member("2")]
    audience = run(client(world(people, everyone=0, owner=BOT)).audience(CHANNEL, GUILD))
    assert audience.size == 1


def test_audience_paginates_and_deduplicates():
    people = [member(BOT)] + [member(str(i)) for i in range(1000, 2500)]
    audience = run(client(world(people)).audience(CHANNEL, GUILD))
    assert audience.size == len(people)


@pytest.mark.parametrize(
    "name,kwargs",
    [
        ("thread or dm", {"channel_type": 1}),
        ("forum", {"channel_type": 15}),
        ("channel in another guild", {"guild_id": "999"}),
    ],
)
def test_unsupported_channels_fail_closed(name, kwargs):
    people = [member(BOT), member("1")]
    with pytest.raises(Problem) as caught:
        run(client(world(people, **kwargs)).audience(CHANNEL, GUILD))
    assert caught.value.status == 403, name


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500, 503])
def test_a_non_200_from_discord_is_never_treated_as_success(status):
    """The bodies served here are *valid*; only the status code is wrong.

    Written this way on purpose. An earlier version returned an error body as well, so
    the request failed the next check anyway and the test passed even with the status
    check removed -- it proved nothing. Now the status check is the only thing that can
    refuse, so deleting it fails this test.
    """
    people = [member(BOT), member("1")]
    with pytest.raises(Problem) as caught:
        run(client(world(people, status=status)).audience(CHANNEL, GUILD))
    assert caught.value.status == 403


def test_a_bot_that_cannot_see_the_channel_is_refused():
    """The bot's own view permission is checked before any audience is computed."""
    people = [member("1")]  # the bot is not a member at all
    with pytest.raises(Problem) as caught:
        run(client(world(people)).audience(CHANNEL, GUILD))
    assert caught.value.status in {403, 503}


@pytest.mark.parametrize("channel,guild", [("abc", GUILD), (CHANNEL, "abc"), ("", "")])
def test_non_numeric_identifiers_are_refused_without_calling_discord(channel, guild):
    calls = []

    def handle(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={})

    with pytest.raises(Problem) as caught:
        run(client(httpx.MockTransport(handle)).audience(channel, guild))
    assert caught.value.status == 403
    assert calls == []


def test_a_missing_token_fails_closed_rather_than_skipping_verification():
    """An unconfigured backend must not silently treat every room as verified."""
    with pytest.raises(Problem) as caught:
        run(client(world([member(BOT)]), token="").audience(CHANNEL, GUILD))
    assert caught.value.status == 503


def test_a_malformed_member_page_fails_closed():
    def handle(request):
        path = request.url.path
        if path.endswith("/members"):
            return httpx.Response(200, json={"not": "a list"})
        if path.endswith(f"/channels/{CHANNEL}"):
            return httpx.Response(200, json={"guild_id": GUILD, "type": 0})
        if path.endswith(f"/guilds/{GUILD}"):
            return httpx.Response(
                200,
                json={
                    "id": GUILD,
                    "owner_id": "1",
                    "roles": [{"id": GUILD, "permissions": str(VIEW_CHANNEL)}],
                },
            )
        if path.endswith("/users/@me"):
            return httpx.Response(200, json={"id": BOT})
        return httpx.Response(200, json=member(BOT))

    with pytest.raises(Problem) as caught:
        run(client(httpx.MockTransport(handle)).audience(CHANNEL, GUILD))
    assert caught.value.status == 503


def test_transport_failure_fails_closed():
    def handle(request):
        raise httpx.ConnectError("no route to host")

    with pytest.raises(Problem) as caught:
        run(client(httpx.MockTransport(handle)).audience(CHANNEL, GUILD))
    assert caught.value.status == 503


def test_invalid_json_fails_closed():
    def handle(request):
        return httpx.Response(200, text="<html>cloudflare</html>")

    with pytest.raises(Problem) as caught:
        run(client(httpx.MockTransport(handle)).audience(CHANNEL, GUILD))
    assert caught.value.status == 503


def test_member_checks_the_asked_about_user_not_the_bot():
    people = [member(BOT), member("1")]
    rest = client(world(people))
    assert run(rest.member(CHANNEL, GUILD, "1")) is True
    with pytest.raises(Problem):
        run(rest.member(CHANNEL, GUILD, "2"))  # unknown member: 404 -> fails closed


def test_member_rejects_a_non_numeric_user_without_calling_discord():
    calls = []

    def handle(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={})

    assert run(client(httpx.MockTransport(handle)).member(CHANNEL, GUILD, "' OR 1=1")) is False
    assert calls == []


def test_the_bot_token_never_appears_in_a_raised_problem():
    """A 503 reaches the client; it must not carry the credential with it."""
    for kwargs in ({"status": 500}, {"channel_type": 1}):
        with pytest.raises(Problem) as caught:
            run(client(world([member(BOT)], **kwargs)).audience(CHANNEL, GUILD))
        assert TOKEN not in caught.value.title
        assert TOKEN not in str(caught.value)
