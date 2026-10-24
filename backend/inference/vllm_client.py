import json
from time import perf_counter
from typing import Any

import httpx
from jsonschema import Draft202012Validator, ValidationError

from backend.inference.base import (
    CompletionRequest,
    CompletionResponse,
    HealthReport,
    InferenceRejected,
    InferenceSchemaError,
    InferenceTimeout,
    InferenceUnavailable,
    Usage,
    check_request,
)
from backend.protocol.validation import REGISTRY, inline_references


class VLLMClient:
    def __init__(self, url: str, key: str, model: str, transport: Any = None):
        self.url = url.rstrip("/")
        self.key = key
        self.model = model
        self.transport = transport

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.url + "/",
            headers={"Authorization": f"Bearer {self.key}"},
            transport=self.transport,
            follow_redirects=False,
        )

    async def health(self) -> HealthReport:
        try:
            async with self.client() as client:
                response = await client.get("models", timeout=2)
                healthy = response.status_code == 200 and any(
                    x.get("id") == self.model for x in response.json().get("data", [])
                )
            return HealthReport(healthy, self.model, "available" if healthy else "unavailable")
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            return HealthReport(False, self.model, "unavailable")

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        check_request(request)
        started = perf_counter()
        body: dict[str, Any] = {
            "model": self.model,
            "messages": request.messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "seed": request.seed,
        }
        if request.response_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "schema": inline_references(request.response_schema),
                },
            }
        try:
            async with self.client() as client:
                for _attempt in range(3):
                    remaining = request.timeout_s - (perf_counter() - started)
                    if remaining <= 0:
                        raise InferenceTimeout("Inference deadline exceeded")
                    response = await client.post("chat/completions", json=body, timeout=remaining)
                    if response.status_code >= 500 or response.status_code == 429:
                        raise InferenceUnavailable("Inference unavailable")
                    if response.status_code != 200:
                        raise InferenceRejected("Inference rejected request")
                    try:
                        data = response.json()
                        choice = data["choices"][0]
                        text = choice["message"]["content"]
                        parsed = json.loads(text) if request.response_schema is not None else None
                        if request.response_schema is not None:
                            Draft202012Validator(
                                request.response_schema, registry=REGISTRY
                            ).validate(parsed)
                        usage = Usage(
                            int(data["usage"]["prompt_tokens"]),
                            int(data["usage"]["completion_tokens"]),
                        )
                        finish = choice["finish_reason"]
                        if finish not in {"stop", "length"}:
                            raise ValueError("invalid finish reason")
                        return CompletionResponse(
                            text,
                            parsed,
                            finish,
                            usage,
                            self.model,
                            (perf_counter() - started) * 1000,
                        )
                    except (ValueError, KeyError, TypeError, IndexError, ValidationError):
                        continue
        except httpx.TimeoutException:
            raise InferenceTimeout("Inference deadline exceeded") from None
        except httpx.HTTPError:
            raise InferenceUnavailable("Inference unavailable") from None
        raise InferenceSchemaError("Inference output invalid after three attempts")
