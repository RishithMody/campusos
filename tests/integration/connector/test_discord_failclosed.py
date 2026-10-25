"""Owner requirement 8: Discord audience verification and fail-closed behaviour.

Not one of C1-C9. Added because `DiscordREST` -- the component that decides how many
people can read a room, and therefore what channel consent is consented *to* -- had no
tests at all. `can_view` was pinned against fixtures; the HTTP client around it was not.

Everything here uses `httpx.MockTransport`. No Discord connection, no token.

Two cases exist because review attempt 1 found the mutants they kill. An audience that
is wrong *downwards* was the dangerous direction under the audience-growth re-consent
rule those cases were written against: a room could quietly grow past what anyone
consented to. T12 replaced that rule with an audience-identity comparison, and the cases
still hold -- a miscounted room is a misidentified room.
"""

import asyncio

import httpx
import pytest

from backend.channels.discord import VIEW_CHANNEL, DiscordREST
from backend.common import Problem

UNSET = object()
GUILD = "123"
CHANNEL = "456"
BOT = "900"
TOKEN = "a-fake-bot-token-that-must-never-be-echoed"  # noqa: S105  pragma: allowlist secret


def world(
    members,
    *,
    channel_type=0,
    guild_id=GUILD,
    everyone=VIEW_CHANNEL,
    status=200,
    owner="1",
    roles=(),
    overwrites=(),
    channel_document=None,
    members_page=UNSET,
):
    """A minimal Discord, serving exactly the four endpoints DiscordREST calls."""
    guild = {
        "id": GUILD,
        "owner_id": owner,
        "roles": [{"id": GUILD, "permissions": str(everyone)}, *roles],
    }
    channel = {
        "guild_id": guild_id,
        "type": channel_type,
        "permission_overwrites": list(overwrites),
    }
    if channel_document is not None:
        channel = channel_document

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
            if members_page is not UNSET:
                return httpx.Response(status, json=members_page)
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


# ------------------------------------------------------------------ counting correctly


def test_audience_counts_only_members_who_can_view():
    people = [member(BOT), member("1"), member("2"), member("3")]
    audience = run(client(world(people)).audience(CHANNEL, GUILD))
    assert audience.size == 4
    assert audience.guild == GUILD


def test_audience_excludes_members_denied_by_a_role_overwrite():
    """The bot can view; one member's role is denied. The count must drop to the readers."""
    denied = [{"id": "r1", "type": 0, "deny": str(VIEW_CHANNEL), "allow": "0"}]
    people = [member(BOT), member("2", roles=["r1"]), member("3")]
    audience = run(
        client(world(people, roles=[{"id": "r1", "permissions": "0"}], overwrites=denied)).audience(
            CHANNEL, GUILD
        )
    )
    assert audience.size == 2


def test_audience_pages_beyond_one_request_and_deduplicates():
    people = [member(BOT)] + [member(str(i)) for i in range(1000, 2500)]
    audience = run(client(world(people)).audience(CHANNEL, GUILD))
    assert audience.size == len(people)
    # The same id served twice must be counted once; the implementation uses a set.
    duplicated = people + [member("1000")]
    assert run(client(world(duplicated)).audience(CHANNEL, GUILD)).size == len(people)


# ---------------------------------------------------------------------- failing closed


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


def test_a_bot_that_is_a_member_but_cannot_view_the_channel_is_refused():
    """Review finding 4. Every response is 200 and the bot's membership exists.

    The only thing that can refuse here is the bot's own VIEW_CHANNEL check. The previous
    version of this test supplied no bot membership at all, so a 404 refused first and
    removing the permission check left the whole suite green.
    """
    people = [member(BOT), member("1")]
    with pytest.raises(Problem) as caught:
        run(client(world(people, everyone=0)).audience(CHANNEL, GUILD))
    assert caught.value.status == 403


def test_a_bot_that_is_not_a_member_at_all_is_refused():
    """Kept separate from the case above: a missing member is not a denied member."""
    people = [member("1")]
    with pytest.raises(Problem) as caught:
        run(client(world(people)).audience(CHANNEL, GUILD))
    assert caught.value.status == 403


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


# -------------------------------------------------------------- malformed member pages


@pytest.mark.parametrize(
    "name,page",
    [
        ("empty object", {}),
        ("empty string", ""),
        ("object with keys", {"not": "a list"}),
        ("json null", None),
        ("integer", 7),
        ("list of strings", ["alice", "bob"]),
    ],
)
def test_a_malformed_member_page_fails_closed(name, page):
    """Review finding 3, and the reason the suite needed it.

    `{}` is the dangerous one. A non-empty object raises `TypeError` deeper in and is
    converted to a 503 by the surrounding handler, so the explicit list check looks
    redundant. An **empty** object iterates zero times, reaches `len(members) < 1000`,
    and returns a perfectly well-formed audience of **size 0** -- an undercount, which
    can never trip the re-consent rule. That made the guard load-bearing, and the
    `equivalent mutant` claim in attempt 1 wrong.
    """
    with pytest.raises(Problem) as caught:
        run(client(world([member(BOT)], members_page=page)).audience(CHANNEL, GUILD))
    assert caught.value.status == 503, name


def test_an_audience_of_zero_is_never_returned():
    """P1, fixed in T7d. Stated as a property, independent of how the page was malformed.

    `context()` has already proved this bot is a member who can view the room, so a count
    that does not include it is arithmetically impossible and means the enumeration was
    incomplete. This mattered doubly before T12, when `channel_summary` re-asked for consent
    only if the audience had *grown*: an undercount could never close the gate. The gate now
    compares audience identity, so a partial enumeration would instead read as a membership
    change and demand re-consent for a room that never changed. Refusing is still the only
    correct answer -- a set that is missing members is not the room's audience either way.

    Until T7d this was a strict xfail recording an open defect. It is now an ordinary
    assertion. Note the fixed behaviour is to **refuse**, not to return a corrected count
    -- there is nothing to correct it to.
    """
    for page in ({}, "", [], None, [member("1")]):
        try:
            size = run(
                client(world([member(BOT)], members_page=page)).audience(CHANNEL, GUILD)
            ).size
        except Problem as refused:
            assert refused.status == 503, page
            continue
        assert size > 0, page


def test_a_stalled_pagination_cursor_fails_closed():
    """A full page whose cursor never advances must stop, not loop or undercount."""
    page = [member(str(i)) for i in range(1000, 2000)]

    def handle(request):
        path = request.url.path
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
        if "/members/" in path:
            return httpx.Response(200, json=member(BOT))
        return httpx.Response(200, json=page)  # always the same 1000, cursor never moves

    with pytest.raises(Problem) as caught:
        run(client(httpx.MockTransport(handle)).audience(CHANNEL, GUILD))
    assert caught.value.status == 503


def test_a_malformed_channel_document_produces_no_audience():
    """Known defect, recorded rather than fixed -- production is out of scope here.

    A 200 whose body is not an object escapes as `AttributeError` from `room.get(...)`
    instead of the service's `Problem(503)`, so it would surface as a 500. No audience is
    produced either way, so consent cannot be computed from a bad answer. Accepts both
    outcomes so that fixing production does not break this test.
    """
    for document in ([1, 2, 3], "nope", 7):
        with pytest.raises((Problem, AttributeError)):
            run(client(world([member(BOT)], channel_document=document)).audience(CHANNEL, GUILD))


# --------------------------------------------------------------------- member() checks


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


def test_member_is_false_for_a_member_who_cannot_see_the_channel():
    """A guild member is not the same as a channel reader; linking must use the latter."""
    denied = [{"id": "r1", "type": 0, "deny": str(VIEW_CHANNEL), "allow": "0"}]
    people = [member(BOT), member("2", roles=["r1"])]
    rest = client(world(people, roles=[{"id": "r1", "permissions": "0"}], overwrites=denied))
    assert run(rest.member(CHANNEL, GUILD, "2")) is False


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
