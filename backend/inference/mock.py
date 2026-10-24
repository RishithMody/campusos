import asyncio
import json
from time import perf_counter

from jsonschema import Draft202012Validator, ValidationError

from backend.inference.base import (
    CompletionRequest,
    CompletionResponse,
    HealthReport,
    InferenceError,
    InferenceSchemaError,
    InferenceTimeout,
    Usage,
    check_request,
)
from backend.protocol.validation import REGISTRY


class MockInference:
    """Deterministic fixture-driven model; candidate is already privacy-filtered."""

    def __init__(self, delay: float = 0.01, failure: type[InferenceError] | None = None):
        self.delay = delay
        self.failure = failure

    async def health(self) -> HealthReport:
        return HealthReport(self.failure is None, "mock-v1", "mock")

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        check_request(request)
        started = perf_counter()
        if self.failure:
            raise self.failure("Simulated inference failure")
        if self.delay > request.timeout_s:
            raise InferenceTimeout("Inference deadline exceeded")
        await asyncio.sleep(self.delay)
        parsed = None
        text = "I can help coordinate a time. Any commitment requires your confirmation."
        if request.response_schema is None:
            try:
                context = json.loads(request.messages[-1]["content"])
                if context.get("status") in {
                    "gathering",
                    "negotiating",
                    "awaiting_approval",
                    "converged",
                    "failed",
                    "expired",
                    "cancelled",
                }:
                    text = f"Your negotiation is {context['status']} after {int(context['round'])} rounds. Confirm decisions in your approval list."
            except (ValueError, KeyError, TypeError, AttributeError):
                pass
        if request.response_schema is not None:
            for _attempt in range(3):
                try:
                    parsed = json.loads(request.messages[-1]["content"])["candidate"]
                    Draft202012Validator(request.response_schema, registry=REGISTRY).validate(
                        parsed
                    )
                    break
                except (ValueError, KeyError, ValidationError):
                    parsed = None
            if parsed is None:
                raise InferenceSchemaError("No schema-valid candidate")
            text = json.dumps(parsed)
        return CompletionResponse(
            text,
            parsed,
            "stop",
            Usage(
                max(1, sum(len(m["content"]) for m in request.messages) // 4),
                max(1, len(text) // 4),
            ),
            "mock-v1",
            (perf_counter() - started) * 1000,
        )
