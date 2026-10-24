import json
from copy import deepcopy
from pathlib import Path

import pytest
from conftest import create, grants, read
from starlette.requests import Request
from test_api import proposal

from backend.auth import authenticate
from backend.common import Problem
from backend.db.models import Grant, Negotiation
from backend.protocol.validation import contract


@pytest.mark.parametrize(
    "fixture", sorted(Path("contracts/examples").glob("*/*.json")), ids=lambda p: p.name
)
def test_published_contract_examples(fixture):
    payload = json.loads(fixture.read_text())
    if fixture.name.startswith("invalid-"):
        with pytest.raises(Problem):
            contract(payload, fixture.parent.name)
    else:
        contract(payload, fixture.parent.name)


@pytest.mark.asyncio
async def test_actual_stream_closes_on_grant_revocation(env):
    state, window = create(env)
    ids = grants(env, state, window)
    neg = state["negotiation_id"]
    response = env.client.post(
        f"/v1/negotiations/{neg}/messages", headers=env.headers(), json=proposal(env, state, window)
    )
    assert response.status_code == 202

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": f"/v1/negotiations/{neg}/stream",
            "query_string": b"",
            "headers": [],
            "path_params": {"negotiation_id": neg},
        },
        receive,
    )
    request.state.identity = authenticate(env.headers("bob")["Authorization"], env.settings)
    route = next(r for r in env.app.routes if r.path.endswith("/stream"))
    stream = await route.endpoint(request)
    first = await anext(stream.body_iterator)
    assert first.startswith("event: state\n")
    assert "therapy" not in first
    grant_id = next(g for owner, other, g in ids if owner == "alice" and other == "bob")
    with env.sessions.begin() as session:
        session.get(Grant, grant_id).revoked = True
    second = await anext(stream.body_iterator)
    assert second.startswith("event: error\n")
    assert '"status": 403' in second
    with pytest.raises(StopAsyncIteration):
        await anext(stream.body_iterator)


def test_existing_high_disclosure_transcript_is_filtered_on_actual_egress(env):
    state, window = create(env)
    grants(env, state, window)
    msg = proposal(env, state, window)
    msg["disclosure_level"] = "full"
    msg["scope"]["max_disclosure_level"] = "full"
    msg["payload"]["availability"] = {
        "schema_version": "1.0",
        "student_ref": state["viewer"]["student_ref"],
        "generated_at": msg["issued_at"],
        "timezone": "UTC",
        "window": window,
        "disclosure_level": "full",
        "slots": [{**window, "state": "busy", "category": "personal", "label": "therapy"}],
    }
    with env.sessions.begin() as session:
        row = session.get(Negotiation, state["negotiation_id"])
        data = deepcopy(row.data)
        data["messages"].append({"owner": "alice", "envelope": msg})
        row.data = data
    response = read(env, state["negotiation_id"], "bob")
    entry = response["transcript"][0]
    assert entry["disclosure_level"] == "free_busy"
    assert entry["disclosed"]["availability"]["slots"] == [{**window, "state": "busy"}]
    assert "therapy" not in str(response) and "personal" not in str(response)
