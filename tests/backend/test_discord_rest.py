"""T7d: the Discord REST verifier, and the bot credential it is verified for.

Covers two defects found by T7c's boundary suite (P1, P2) and the credential that had no
way to exist (B1). The audience number is what channel consent is consented *to*, so a
wrong one is a consent defect, not a reliability one.
"""

import asyncio
import sys

import httpx
import jwt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.channels.discord import VIEW_CHANNEL, DiscordREST
from backend.common import Problem
from backend.db.models import Base, Student
from backend.manage import MAX_BOT_TOKEN_HOURS, bot_token, main

GUILD, CHANNEL, BOT = "123", "456", "900"


def guild_doc(everyone=VIEW_CHANNEL, owner="1"):
    return {"id": GUILD, "owner_id": owner, "roles": [{"id": GUILD, "permissions": str(everyone)}]}


def member_doc(user, roles=()):
    return {"user": {"id": user}, "roles": list(roles)}


def discord(pages, *, channel=..., guild=..., me=..., membership=..., known=(BOT,)):
    """A Discord that serves `pages` to successive member requests."""
    served = iter(pages)

    def handle(request):
        path = request.url.path
        if path.endswith(f"/channels/{CHANNEL}"):
            body = {"guild_id": GUILD, "type": 0} if channel is ... else channel
            return httpx.Response(200, json=body)
        if path.endswith(f"/guilds/{GUILD}"):
            return httpx.Response(200, json=guild_doc() if guild is ... else guild)
        if path.endswith("/users/@me"):
            return httpx.Response(200, json={"id": BOT} if me is ... else me)
        if "/members/" in path:
            if membership is not ...:
                return httpx.Response(200, json=membership)
            user = path.rsplit("/", 1)[-1]
            # Discord 404s an id it does not know; serving every id would let a malformed
            # bot identity look like a valid member.
            if user not in known:
                return httpx.Response(404, json={"message": "Unknown Member"})
            return httpx.Response(200, json=member_doc(user))
        if path.endswith("/members"):
            return httpx.Response(200, json=next(served, []))
        return httpx.Response(404, json={})

    return httpx.MockTransport(handle)


def audience(transport):
    return asyncio.run(DiscordREST("fake-token", transport=transport).audience(CHANNEL, GUILD))


# ------------------------------------------------------------------------------- P1


def test_an_empty_member_page_is_refused_not_counted_as_zero():
    """P1. `[]` is a well-formed list, so the list guard passes and the old code returned 0.

    An undercount was the dangerous direction under the pre-T12 rule, which re-asked for
    consent only when the audience had grown: a room could grow past what anyone agreed to
    without the gate ever closing. The gate now compares audience identity, and a partial
    enumeration is a different set either way, so refusing remains the only correct answer.
    """
    with pytest.raises(Problem) as caught:
        audience(discord([[]]))
    assert caught.value.status == 503


def test_a_page_that_omits_the_bot_is_refused():
    """`context()` already proved this bot can view the room, so its absence is impossible."""
    with pytest.raises(Problem) as caught:
        audience(discord([[member_doc("1"), member_doc("2")]]))
    assert caught.value.status == 503


def test_a_page_that_includes_the_bot_is_counted():
    assert audience(discord([[member_doc(BOT), member_doc("1")]])).size == 2


def test_an_exactly_full_first_page_still_paginates_to_an_empty_second():
    """The regression risk of the P1 fix: an empty page is legitimate *after* a full one."""
    full = [member_doc(BOT)] + [member_doc(str(i)) for i in range(1000, 1999)]
    assert len(full) == 1000
    assert audience(discord([full, []])).size == 1000


def test_members_the_bot_can_see_but_who_cannot_read_are_excluded():
    """The fix must not turn the count into `everyone in the guild`."""
    denied = {"id": "r1", "type": 0, "deny": str(VIEW_CHANNEL), "allow": "0"}

    def handle(request):
        path = request.url.path
        if path.endswith(f"/channels/{CHANNEL}"):
            return httpx.Response(
                200, json={"guild_id": GUILD, "type": 0, "permission_overwrites": [denied]}
            )
        if path.endswith(f"/guilds/{GUILD}"):
            doc = guild_doc()
            doc["roles"].append({"id": "r1", "permissions": "0"})
            return httpx.Response(200, json=doc)
        if path.endswith("/users/@me"):
            return httpx.Response(200, json={"id": BOT})
        if "/members/" in path:
            return httpx.Response(200, json=member_doc(BOT))
        return httpx.Response(200, json=[member_doc(BOT), member_doc("2", roles=["r1"])])

    assert audience(httpx.MockTransport(handle)).size == 1


# ------------------------------------------------------------------------------- P2


@pytest.mark.parametrize("document", [[1, 2, 3], "nope", 7, None, True])
def test_a_non_object_channel_document_fails_closed(document):
    """P2. This used to escape as AttributeError from `room.get(...)`, i.e. a 500."""
    with pytest.raises(Problem) as caught:
        audience(discord([[member_doc(BOT)]], channel=document))
    assert caught.value.status == 503


@pytest.mark.parametrize("field", ["guild", "me", "membership"])
def test_a_non_object_in_any_other_document_fails_closed(field):
    with pytest.raises(Problem) as caught:
        audience(discord([[member_doc(BOT)]], **{field: "not an object"}))
    assert caught.value.status == 503


@pytest.mark.parametrize("identity", [{"id": 900}, {"id": "abc"}, {}, {"id": None}, {"id": "../"}])
def test_an_unusable_bot_identity_fails_closed(identity):
    """The bot's own id is interpolated into a URL path; it has to be a snowflake.

    Asserts 503 specifically. Without the check the id reaches the URL, Discord 404s it,
    and the caller gets 403 -- still closed, but it reports "you may not" for what is
    actually "we could not tell", and it puts an unvalidated value in a request path.
    """
    with pytest.raises(Problem) as caught:
        audience(discord([[member_doc(BOT)]], me=identity))
    assert caught.value.status == 503


def test_member_lookup_also_rejects_a_non_object():
    rest = DiscordREST("fake-token", transport=discord([], membership="not an object"))
    with pytest.raises(Problem) as caught:
        asyncio.run(rest.member(CHANNEL, GUILD, "1"))
    assert caught.value.status == 503


# ------------------------------------------------------------- B1: the bot credential


def test_an_issued_bot_token_is_accepted_and_bound_to_its_guild(env):
    token = bot_token(env.settings, "campusos-discord-bot", "123", 12)
    headers = {"Authorization": "Bearer " + token}
    response = env.client.post(
        "/v1/channels",
        headers=headers,
        json={
            "platform": "discord",
            "platform_channel_id": "4242",
            "max_disclosure_level": "free_busy",
        },
    )
    assert response.status_code == 201, response.text
    claims = jwt.decode(
        token,
        env.settings.jwt_key,
        algorithms=["HS256"],
        audience=env.settings.jwt_audience,
        issuer=env.settings.jwt_issuer,
    )
    assert claims["kind"] == "bot"
    assert claims["guild"] == "123"
    assert claims["exp"] > claims["iat"]


def test_an_issued_bot_token_cannot_act_as_a_student(env):
    """The credential this command creates must not be able to approve anything."""
    headers = {"Authorization": "Bearer " + bot_token(env.settings, "a-bot", "123", 1)}
    assert env.client.get("/v1/me", headers=headers).status_code == 403
    assert env.client.get("/v1/negotiations", headers=headers).status_code == 403


def test_a_bot_token_for_another_students_subject_is_still_only_a_bot(env):
    """Naming a student in `sub` must not promote the credential."""
    headers = {"Authorization": "Bearer " + bot_token(env.settings, "alice", "123", 1)}
    assert env.client.get("/v1/me", headers=headers).status_code == 403


@pytest.mark.parametrize(
    "guild,hours",
    [("not-a-snowflake", 12), ("", 12), ("123", 0), ("123", -1), ("123", MAX_BOT_TOKEN_HOURS + 1)],
)
def test_malformed_issuance_requests_are_refused(env, guild, hours):
    with pytest.raises(ValueError):
        bot_token(env.settings, "a-bot", guild, hours)


def test_issue_bot_refuses_a_subject_that_is_a_provisioned_student(tmp_path, monkeypatch, capsys):
    """One subject must not mean two principals, even though the kind check would catch it."""
    url = f"sqlite:///{tmp_path}/accounts.db"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with sessionmaker(engine)() as session:
        session.add(Student(id="alice", agent_id="agt_x", contact_handle="cnt_x"))
        session.commit()
    engine.dispose()
    for key, value in {
        "CAMPUSOS_INFERENCE_MODE": "mock",
        "CAMPUSOS_DATABASE_URL": url,
        "CAMPUSOS_REDIS_URL": "redis://localhost",
        "CAMPUSOS_JWT_KEY": "k" * 40,
    }.items():
        monkeypatch.setenv(key, value)

    monkeypatch.setattr(sys, "argv", ["manage", "issue-bot", "alice", "--guild", "123"])
    with pytest.raises(ValueError, match="provisioned student"):
        main()

    monkeypatch.setattr(sys, "argv", ["manage", "issue-bot", "campusos-bot", "--guild", "123"])
    main()
    printed = capsys.readouterr().out.strip().splitlines()
    claims = jwt.decode(
        printed[0], "k" * 40, algorithms=["HS256"], audience="campusos-api", issuer="campusos"
    )
    assert claims == {
        **claims,
        "sub": "campusos-bot",
        "kind": "bot",
        "guild": "123",
    }
    assert "Never commit it" in printed[-1]
