from dataclasses import dataclass
from typing import Any, Literal, Protocol, TypedDict


class Message(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class CompletionRequest:
    messages: list[Message]
    max_tokens: int
    temperature: float
    seed: int | None
    response_schema: dict[str, Any] | None
    trace_id: str
    timeout_s: float


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int


@dataclass(frozen=True)
class CompletionResponse:
    text: str
    parsed: dict[str, Any] | None
    finish_reason: Literal["stop", "length", "schema_retry_exhausted", "timeout"]
    usage: Usage
    model: str
    latency_ms: float


@dataclass(frozen=True)
class HealthReport:
    healthy: bool
    model: str
    detail: str


class InferenceError(Exception):
    pass


class InferenceTimeout(InferenceError):
    pass


class InferenceUnavailable(InferenceError):
    pass


class InferenceSchemaError(InferenceError):
    pass


class InferenceRejected(InferenceError):
    pass


class InferenceClient(Protocol):
    async def complete(self, request: CompletionRequest) -> CompletionResponse: ...
    async def health(self) -> HealthReport: ...


def check_request(request: CompletionRequest) -> None:
    if (
        not request.messages
        or not 1 <= request.max_tokens <= 4096
        or not 0 <= request.temperature <= 2
        or not 0 < request.timeout_s <= 120
        or sum(len(m["content"]) for m in request.messages) > 100_000
        or any(m["role"] not in {"system", "user", "assistant"} for m in request.messages)
    ):
        raise InferenceRejected("Invalid completion request")
