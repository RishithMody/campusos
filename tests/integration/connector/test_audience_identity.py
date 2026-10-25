"""What a channel binding is consented *to*, and what counts as a change to it.

A headcount cannot tell one audience of four from a different audience of four. Before
`Audience.fingerprint` existed, `channel_summary` compared `audience.size` against the
size recorded at consent, so:

  * a room that swapped one member for another kept its count, and a person who was
    never in the consented audience could read the summary; and
  * the recorded count was only ever *raised*, so a room could shrink and then regrow
    with different people in it and still never re-consent.

Both are reproducible against the pre-fix code; see `docs/agents/reviews/T12/`. Every
case here drives the real consent gate end to end over HTTP, with the fingerprint
computed the way the real adapter computes it. The `fingerprint` cases drive the real
`DiscordREST` against `httpx.MockTransport`. No Discord connection, no token.
"""

import pytest

from backend.channels.discord import Audience, fingerprint
from backend.common import Problem
from tests.integration.connector.environment import decide
from tests.integration.connector.test_consent_gate import confirmed_channel, summary_url
from tests.integration.connector.test_discord_failclosed import (
    BOT,
    CHANNEL,
    GUILD,
    client,
    member,
    run,
    world,
)


def consented(env, platform):
    """A confirmed binding: everyone linked, bound, and approved at the current audience."""
    neg, channel = confirmed_channel(env, platform=platform)
    for who in ("alice", "bob", "carol"):
        decide(env, neg, who)
    url = summary_url(neg, channel)
    assert env.client.get(url, headers=env.headers("bot", "bot")).status_code == 200
    return neg, channel, url


def status(env, neg, channel):
    body = env.client.get(f"/v1/negotiations/{neg}/channel-bindings", headers=env.headers()).json()
    return next(b for b in body["bindings"] if b["channel_id"] == channel)


# --------------------------------------------------------------- the six audience changes


@pytest.mark.privacy
@pytest.mark.authz
def test_audience_growth_requires_renewed_consent(env):
    neg, channel, url = consented(env, "4001")
    env.discord.viewers.add("99")
    assert env.client.get(url, headers=env.headers("bot", "bot")).status_code == 403
    assert status(env, neg, channel)["status"] == "pending_reconsent"


@pytest.mark.privacy
@pytest.mark.authz
def test_audience_shrinkage_requires_renewed_consent(env):
    """Harmless on its own -- but a recorded audience that is never lowered is how the
    room regrows to its old size with different people in it."""
    neg, channel, url = consented(env, "4002")
    env.discord.viewers.remove("3")
    assert env.client.get(url, headers=env.headers("bot", "bot")).status_code == 403
    assert status(env, neg, channel)["status"] == "pending_reconsent"


@pytest.mark.privacy
@pytest.mark.authz
def test_same_size_member_replacement_requires_renewed_consent(env):
    """The reported finding. One member leaves, one joins, the count does not move."""
    neg, channel, url = consented(env, "4003")
    before = status(env, neg, channel)["audience_size_at_consent"]
    env.discord.viewers.remove("3")
    env.discord.viewers.add("99")
    assert env.discord.size == before
    assert env.client.get(url, headers=env.headers("bot", "bot")).status_code == 403
    after = status(env, neg, channel)
    assert after["status"] == "pending_reconsent"
    assert after["audience_size_at_consent"] == before
    # And it serves again only once every participant has agreed to the new audience.
    for who in ("alice", "bob", "carol"):
        decide(env, neg, who)
    assert env.client.get(url, headers=env.headers("bot", "bot")).status_code == 200


@pytest.mark.privacy
@pytest.mark.authz
def test_a_shrink_then_regrow_to_the_consented_size_still_requires_consent(env):
    """The second pre-fix bypass: the comparison was one-directional."""
    neg, channel, url = consented(env, "4004")
    bot = env.headers("bot", "bot")
    env.discord.viewers -= {"2", "3"}
    assert env.client.get(url, headers=bot).status_code == 403
    env.discord.viewers |= {"98", "99"}
    assert env.discord.size == 3
    assert env.client.get(url, headers=bot).status_code == 403
    assert status(env, neg, channel)["status"] == "pending_reconsent"


@pytest.mark.privacy
def test_an_unchanged_audience_never_demands_re_consent(env):
    """The gate has to be quiet when nothing happened, or it is worthless in a demo."""
    neg, channel, url = consented(env, "4005")
    bot = env.headers("bot", "bot")
    for _ in range(5):
        assert env.client.get(url, headers=bot).status_code == 200
    assert status(env, neg, channel)["status"] == "confirmed"
    # Re-deriving the same set in a different order is the same audience.
    env.discord.viewers = {"3", "1", "2"}
    assert env.client.get(url, headers=bot).status_code == 200


@pytest.mark.privacy
@pytest.mark.authz
def test_incomplete_member_enumeration_serves_no_summary(env):
    """An audience that cannot be enumerated is not an audience anyone consented to.

    `DiscordREST` already refuses to return a partial count. This pins the service half:
    an adapter that raises, or one that counts a room it cannot identify, must not fall
    through to serving the summary.
    """
    neg, channel, url = consented(env, "4006")
    bot = env.headers("bot", "bot")

    async def unavailable(channel_id, guild):
        raise Problem(503, "Channel verification unavailable")

    env.discord.audience = unavailable
    assert env.client.get(url, headers=bot).status_code == 503

    async def counted_but_unidentified(channel_id, guild):
        return Audience(guild, 3)

    env.discord.audience = counted_but_unidentified
    assert env.client.get(url, headers=bot).status_code == 503
    assert status(env, neg, channel)["status"] == "confirmed"


@pytest.mark.privacy
@pytest.mark.authz
def test_revoked_consent_outlives_an_unchanged_audience(env):
    """Withdrawal is not an audience question: the room can be identical and still refuse."""
    neg, channel, url = consented(env, "4007")
    assert (
        env.client.delete(
            f"/v1/negotiations/{neg}/channel-bindings/{channel}", headers=env.headers("bob")
        ).status_code
        == 204
    )
    bot = env.headers("bot", "bot")
    assert env.client.get(url, headers=bot).status_code == 403
    assert status(env, neg, channel)["status"] == "withdrawn"
    # Re-deriving the consented audience exactly does not resurrect the binding.
    env.discord.viewers = {"1", "2", "3"}
    assert env.client.get(url, headers=bot).status_code == 403
    assert status(env, neg, channel)["status"] == "withdrawn"


# ------------------------------------------------------- the fingerprint itself


def test_the_same_audience_always_digests_the_same_way():
    people = [member(BOT), member("1"), member("2")]
    first = run(client(world(people)).audience(CHANNEL, GUILD))
    again = run(client(world(list(reversed(people)))).audience(CHANNEL, GUILD))
    assert first.fingerprint and first.fingerprint == again.fingerprint
    assert first.size == again.size == 3


def test_a_same_size_swap_changes_the_digest():
    before = run(client(world([member(BOT), member("1"), member("3")])).audience(CHANNEL, GUILD))
    after = run(client(world([member(BOT), member("1"), member("77")])).audience(CHANNEL, GUILD))
    assert before.size == after.size
    assert before.fingerprint != after.fingerprint


def test_a_digest_from_one_room_means_nothing_in_another():
    """Scoped, so a recorded fingerprint cannot be transplanted between channels."""
    viewers = {"1", "2", "3"}
    assert fingerprint("456", GUILD, viewers) != fingerprint("457", GUILD, viewers)
    assert fingerprint("456", "123", viewers) != fingerprint("456", "124", viewers)


def test_no_two_member_sets_collide_through_concatenation():
    """Lengths are prefixed; without that, {"1","23"} and {"12","3"} digest alike."""
    assert fingerprint(CHANNEL, GUILD, {"1", "23"}) != fingerprint(CHANNEL, GUILD, {"12", "3"})


@pytest.mark.privacy
def test_the_audience_identity_never_leaves_the_backend(env):
    """Requirement 7. Not in the binding, not in the summary, and no raw account id either.

    `ChannelBinding` is `additionalProperties: false` in the frozen contract, so a leak
    into the binding view would also fail response validation -- this pins it anyway,
    because that is a property of the schema and not of this code.
    """
    neg, channel, url = consented(env, "4008")
    digest = fingerprint("1234", "123", env.discord.viewers)
    summary = env.client.get(url, headers=env.headers("bot", "bot"))
    assert summary.status_code == 200
    binding = env.client.get(f"/v1/negotiations/{neg}/channel-bindings", headers=env.headers()).text
    for body in (summary.text, binding):
        assert digest not in body
        # `audience_size_at_consent` is a contract field; the internal key is not.
        assert '"audience"' not in body
        for viewer in env.discord.viewers:
            assert f'"{viewer}"' not in body
