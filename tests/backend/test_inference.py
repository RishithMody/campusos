import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from backend.inference.base import (
    CompletionRequest,
    InferenceRejected,
    InferenceSchemaError,
    InferenceTimeout,
    InferenceUnavailable,
)
from backend.inference.mock import MockInference
from backend.inference.vllm_client import VLLMClient
from backend.protocol.validation import SCHEMAS, contract


def request():
    candidate = json.loads(Path("contracts/examples/agent-protocol/valid-propose.json").read_text())
    return CompletionRequest(
        [{"role": "user", "content": json.dumps({"candidate": candidate})}],
        1000,
        0.0,
        42,
        SCHEMAS["agent-protocol.schema"],
        "trc_test",
        2,
    )


@pytest.mark.asyncio
async def test_mock_determinism_schema_usage_and_health():
    client = MockInference(delay=0)
    one, two = await client.complete(request()), await client.complete(request())
    assert one.text == two.text
    contract(one.parsed, "agent-protocol")
    assert one.usage.prompt_tokens > 0 and one.usage.completion_tokens > 0
    assert one.latency_ms >= 0
    assert (await client.health()).healthy


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [InferenceTimeout, InferenceUnavailable, InferenceSchemaError, InferenceRejected]
)
async def test_mock_injected_failures(error):
    with pytest.raises(error):
        await MockInference(delay=0, failure=error).complete(request())
    assert not (await MockInference(failure=error).health()).healthy


@pytest.mark.asyncio
async def test_request_bounds_and_mock_schema_failure():
    client = MockInference(delay=0)
    with pytest.raises(InferenceRejected):
        await client.complete(replace(request(), max_tokens=0))
    with pytest.raises(InferenceTimeout):
        await MockInference(delay=1).complete(replace(request(), timeout_s=0.1))
    with pytest.raises(InferenceSchemaError):
        await client.complete(replace(request(), messages=[{"role": "user", "content": "{}"}]))


@pytest.mark.asyncio
async def test_vllm_wire_and_schema_retries():
    calls = []
    candidate = json.loads(request().messages[0]["content"])["candidate"]

    def handler(req):
        calls.append(req)
        assert req.headers["authorization"] == "Bearer fixture"
        if req.url.path.endswith("models"):
            return httpx.Response(200, json={"data": [{"id": "test-model"}]})
        body = json.loads(req.content)
        assert body["temperature"] == 0.0 and body["seed"] == 42
        text = json.dumps(candidate) if len(calls) == 3 else "invalid"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 100},
            },
        )

    client = VLLMClient(
        "https://inference.invalid/v1", "fixture", "test-model", httpx.MockTransport(handler)
    )
    result = await client.complete(request())
    assert len(calls) == 3 and result.parsed == candidate
    assert (await client.health()).healthy


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,error",
    [
        (503, InferenceUnavailable),
        (429, InferenceUnavailable),
        (400, InferenceRejected),
        (401, InferenceRejected),
    ],
)
async def test_vllm_http_failure_mapping(status, error):
    client = VLLMClient(
        "https://inference.invalid/v1",
        "fixture",
        "test-model",
        httpx.MockTransport(lambda _: httpx.Response(status)),
    )
    with pytest.raises(error):
        await client.complete(request())
    assert not (await client.health()).healthy


@pytest.mark.asyncio
async def test_vllm_transport_and_exhaustion():
    calls = []

    def invalid(req):
        calls.append(req)
        return httpx.Response(200, json={})

    client = VLLMClient(
        "https://inference.invalid/v1", "fixture", "test-model", httpx.MockTransport(invalid)
    )
    with pytest.raises(InferenceSchemaError):
        await client.complete(request())
    assert len(calls) == 3

    def timeout(req):
        raise httpx.ReadTimeout("untrusted secret", request=req)

    client.transport = httpx.MockTransport(timeout)
    with pytest.raises(InferenceTimeout, match="deadline"):
        await client.complete(request())
    assert not (await client.health()).healthy
