"""Review probes; mutations are in memory only. Run with PYTHONPATH=. python ..."""
import inspect
import sys
import textwrap

import httpx
import pytest

import backend.channels.discord as discord
from backend.common import Problem
from tests.integration.connector import test_bot_surface as surface
from tests.integration.connector import test_discord_failclosed as checks
from tests.integration.connector.environment import env


def replace_method(name, old, new):
    source = textwrap.dedent(inspect.getsource(getattr(discord.DiscordREST, name)))
    assert old in source
    namespace = {}
    exec(source.replace(old, new), vars(discord), namespace)
    setattr(discord.DiscordREST, name, namespace[name])


mode = sys.argv[1]
if mode == "controls":
    for method, path in [
        ("post", "/negotiations/{negotiation_id}/channel-bindings"),
        ("post", "/approvals/{approval_id}"),
        ("post", "/negotiations/{negotiation_id}/messages"),
    ]:
        fixture = env.__wrapped__()
        environment = next(fixture)
        try:
            scenario = surface.scenario.__wrapped__(environment)
            url, body = surface.requests_for(environment, scenario)[method, path]
            response = surface.send(environment, method, url, body, environment.headers())
            print(method, path, response.status_code, response.text[:160])
        finally:
            fixture.close()
    original = surface.operations()
    surface.API["paths"]["/review-probe"] = {"patch": {"operationId": "newOperation"}}
    print("PATCH addition detected:", surface.operations() != original)
elif mode in {"m7", "bot-view"}:
    if mode == "m7":
        replace_method("audience", 'if not isinstance(members, list):', 'if False:')
    else:
        replace_method("context", 'if not can_view(membership, server, room):', 'if False:')
    raise SystemExit(pytest.main(["tests/integration/connector", "-q", "-rs"]))
elif mode == "empty-page":
    transport = checks.world([checks.member(checks.BOT), checks.member("1")])
    def handle(request):
        if request.url.path.endswith("/members"):
            return httpx.Response(200, json={})
        return transport.handle_request(request)
    for mutated in (False, True):
        if mutated:
            replace_method("audience", 'if not isinstance(members, list):', 'if False:')
        try:
            result = checks.run(checks.client(httpx.MockTransport(handle)).audience(checks.CHANNEL, checks.GUILD))
            print("M7" if mutated else "baseline", result)
        except Problem as error:
            print("M7" if mutated else "baseline", "Problem", error.status)
