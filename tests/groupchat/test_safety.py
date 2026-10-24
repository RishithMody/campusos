import asyncio
import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord
import httpx
import pytest

from groupchat.api import API, APIError, base_url
from groupchat.bot import Bot
from groupchat.publisher import Publisher
from groupchat.render import SCHEMA, TEMPLATES, render
from groupchat.student import decide

NEG = "neg_1234567890abcdef"
CHN = "chn_12345678"
SUMMARY = {
    "negotiation_id": NEG,
    "status": "gathering",
    "round": 0,
    "max_rounds": 5,
    "template_id": "gathering_availability",
    "participant_count": 3,
}


@pytest.mark.parametrize(
    "field,value",
    [
        ("text", "therapy @everyone"),
        ("participant_count", "therapy"),
        ("participant_count", True),
        ("template_id", "custom"),
        ("participants", ["private name"]),
        ("availability", {"label": "therapy"}),
        ("status", "converged"),
        ("round", 21),
        ("negotiation_id", "neg_ffffffffffffffff"),
    ],
)
def test_injected_summary_is_never_rendered(field, value):
    data = {**SUMMARY, field: value}
    with pytest.raises(ValueError):
        render(data, NEG)


def test_templates_match_frozen_contract():
    assert set(TEMPLATES) == set(SCHEMA["properties"]["template_id"]["enum"])
    assert render(SUMMARY, NEG) == "Collecting availability from 3 people."
    data = {
        **SUMMARY,
        "status": "converged",
        "template_id": "converged",
        "timezone": "America/Phoenix",
        "agreed_slot": {"start": "2026-10-25T19:00:00Z", "end": "2026-10-25T20:00:00Z"},
    }
    assert render(data, NEG) == "Locked in: 2026-10-25 12:00 MST – 2026-10-25 13:00 MST."
    data["agreed_slot"]["label"] = "therapy"
    with pytest.raises(ValueError):
        render(data, NEG)


@pytest.mark.parametrize("mode", ["403", "500", "timeout", "malformed", "unknown", "extra"])
def test_outage_and_invalid_payloads_fail_closed(mode, caplog):
    async def scenario():
        paths = []

        def handle(request):
            paths.append(request.url.path)
            if mode == "timeout":
                raise httpx.ReadTimeout("private therapy secret")
            if mode in {"403", "500"}:
                return httpx.Response(int(mode), json={"detail": "private therapy secret"})
            if mode == "malformed":
                return httpx.Response(200, text="private therapy secret")
            data = copy.deepcopy(SUMMARY)
            data["template_id" if mode == "unknown" else "label"] = "private therapy secret"
            return httpx.Response(200, json=data)

        api = API("http://localhost/v1", "fake", transport=httpx.MockTransport(handle))
        send = AsyncMock()
        try:
            assert not await Publisher(api).update(NEG, CHN, send)
            send.assert_not_called()
            assert paths == [f"/v1/negotiations/{NEG}/channel-summary"]
            assert "therapy" not in caplog.text and "secret" not in caplog.text
        finally:
            await api.close()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/v1",
        "https://a:8443/v1",
        "https://a/v1?key=x",
        "https://user:secret@a/v1",
        "https://a/other",
    ],
)
def test_no_insecure_or_credential_urls(url):
    with pytest.raises(ValueError):
        base_url(url)


def test_human_decision_shows_preview_and_never_retries_stale(capsys):
    async def scenario():
        api = AsyncMock()
        preview = {
            "approval_id": "apr_12345678",
            "state_version": 7,
            "discloses": {"summary": "Release to 3 channel accounts"},
        }
        api.request.side_effect = [{"pending_approvals": [preview]}, APIError(409)]

        def answer(prompt):
            assert "Release to 3 channel accounts" in capsys.readouterr().out
            return "approve"

        with patch("builtins.input", answer), pytest.raises(APIError):
            await decide(api, NEG, "apr_12345678")
        assert api.request.call_count == 2
        assert api.request.call_args.args[2] == {"decision": "approve", "state_version": 7}

    asyncio.run(scenario())


def test_no_decision_on_cancel():
    async def scenario():
        api = AsyncMock()
        api.request.return_value = {"pending_approvals": [{"approval_id": "apr_12345678"}]}
        with patch("builtins.input", return_value=""):
            await decide(api, NEG, "apr_12345678")
        assert api.request.call_count == 1

    asyncio.run(scenario())


def test_bot_commands_exist_without_connecting():
    async def scenario():
        api = API("http://localhost/v1", "fake")
        bot = Bot(api, 123)
        assert {c.name for c in bot.tree.get_commands()} == {"schedule", "watch"}
        assert not bot.intents.message_content
        await bot.close()

    asyncio.run(scenario())


def test_schedule_registration_and_unavailable_response_are_ephemeral():
    async def scenario():
        api = AsyncMock()
        api.register.return_value = CHN
        bot = Bot(api, 123)
        room = AsyncMock(spec=discord.TextChannel)
        room.id = 1234
        interaction = SimpleNamespace(
            guild_id=123, channel=room, response=AsyncMock(), followup=AsyncMock()
        )
        await bot.schedule(interaction)
        api.register.assert_awaited_once_with(1234)
        assert CHN in interaction.followup.send.call_args.args[0]
        assert interaction.followup.send.call_args.kwargs["ephemeral"] is True
        room.send.assert_not_called()
        api.register.side_effect = APIError(503)
        await bot.schedule(interaction)
        assert "unavailable" in interaction.followup.send.call_args.args[0]
        room.send.assert_not_called()
        await bot.close()

    asyncio.run(scenario())


def test_watch_checks_summary_and_disables_mentions():
    async def scenario():
        api = AsyncMock()
        api.register.return_value = CHN
        api.summary.side_effect = [SUMMARY, APIError(403)]
        bot = Bot(api, 123)
        room = AsyncMock(spec=discord.TextChannel)
        room.id = 1234
        interaction = SimpleNamespace(
            guild_id=123, channel=room, response=AsyncMock(), followup=AsyncMock()
        )
        with patch("groupchat.bot.asyncio.sleep", new=AsyncMock()):
            await bot.watch(interaction, NEG)
            await bot.watches[1234]
        room.send.assert_awaited_once()
        assert room.send.call_args.args == ("Collecting availability from 3 people.",)
        mentions = room.send.call_args.kwargs["allowed_mentions"]
        assert not mentions.everyone and not mentions.users and not mentions.roles
        assert api.summary.await_count == 2
        await bot.close()

    asyncio.run(scenario())


def test_redirect_does_not_forward_credentials():
    async def scenario():
        calls = []

        def handle(request):
            calls.append(request)
            return httpx.Response(302, headers={"location": "https://other.example/v1"})

        api = API("https://api.example/v1", "fake", transport=httpx.MockTransport(handle))
        try:
            with pytest.raises(APIError):
                await api.summary(NEG, CHN)
            assert len(calls) == 1
        finally:
            await api.close()

    asyncio.run(scenario())
