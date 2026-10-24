# Inference interface (v1)

**Status:** frozen contract. T2 (backend) and T4 (ML) both code against this; T3 (GPU infra)
implements the vLLM side. Changes go through the Orchestrator.

The one rule: **the mock and vLLM are behaviourally substitutable.** Phase 1 of this project is
three agents negotiating with no GPU at all, and the demo must survive the cluster being
unavailable mid-presentation. So calling code must never branch on which implementation it has:
same Protocol, same return shapes, the same four exceptions raised in the same situations.

Substitutable is not *indistinguishable*. They report different model names and different
latencies, and T4's benchmark depends on being able to tell them apart — a mock that hid its
own latency would make the benchmark meaningless. An earlier draft of this file demanded
indistinguishability "by timing", which contradicted both the latency field two sections below
and T3's assignment. Behaviour is the contract; timing and model name are observations.

## The interface

```python
class InferenceClient(Protocol):
    async def complete(self, request: CompletionRequest) -> CompletionResponse: ...
    async def health(self) -> HealthReport: ...
```

Callers depend on this Protocol only. No caller imports a concrete client, constructs a URL, or
reads an inference environment variable: the client is injected. A hardcoded endpoint anywhere
above this boundary is a bug.

### CompletionRequest

| Field | Type | Notes |
|---|---|---|
| `messages` | `list[Message]` | `Message = {role: "system"\|"user"\|"assistant", content: str}` |
| `max_tokens` | `int` | Required. No implicit default — an unbounded generation is a cost and latency risk. |
| `temperature` | `float` | Required, `0.0`–`2.0`. State it; do not inherit a server default. |
| `seed` | `int \| None` | Set it for anything that must be reproducible. T4's evaluation always sets it. |
| `response_schema` | `dict \| None` | JSON Schema. When present the response **must** be valid against it. |
| `trace_id` | `str` | Propagated into logs so a generation can be tied to its negotiation. |
| `timeout_s` | `float` | Required. The caller owns the deadline, not the server. |

### CompletionResponse

| Field | Type | Notes |
|---|---|---|
| `text` | `str` | The completion. |
| `parsed` | `dict \| None` | Populated when `response_schema` was given and parsing succeeded. |
| `finish_reason` | `"stop" \| "length" \| "schema_retry_exhausted" \| "timeout"` | |
| `usage` | `Usage` | `{prompt_tokens, completion_tokens}`. The mock reports plausible counts, not zeros. |
| `model` | `str` | e.g. `qwen3-8b` or `mock-v1`. For logging only — **never** branch on it. |
| `latency_ms` | `float` | Measured, not estimated. |

### HealthReport

`{healthy: bool, model: str, detail: str}`. A down endpoint reports `healthy=False`; it does not
raise. T3's health-check test asserts exactly this.

## Errors

One exception hierarchy, raised identically by both implementations:

| Exception | When | Retryable |
|---|---|---|
| `InferenceTimeout` | Deadline passed | yes |
| `InferenceUnavailable` | Cannot reach the backend, or it is unhealthy | yes |
| `InferenceSchemaError` | Output never matched `response_schema` after retries | no |
| `InferenceRejected` | Request malformed or over a hard limit | no |

A caller that handles these four handles every implementation. Callers must degrade, not crash:
if inference is unavailable mid-negotiation, the negotiation **escalates to the human** rather
than guessing. That is a product behaviour, not an error path.

## Structured output

When `response_schema` is set, the client retries internally up to **3** times, then raises
`InferenceSchemaError`. Both implementations validate before returning, so a caller never has to
re-validate. Negotiation messages are generated this way against
`agent-protocol.schema.json` — the model proposes, the schema disposes.

## Privacy obligations at this boundary

- **Never put raw calendar entries, event titles, locations, names or emails in a prompt.** The
  prompt receives the already-disclosure-filtered availability envelope, nothing richer. Filter
  before the prompt, not after the completion.
- Log `trace_id`, token counts and latency. **Never log prompt or completion text** in any
  default configuration: these contain student schedule data.
- The mock must be as privacy-safe as the real one; it is used in CI, where output is retained.

## The mock

Lives behind the same Protocol and ships with the backend. It is what development and CI
**select** — `CAMPUSOS_INFERENCE_MODE=mock`, set explicitly in
`.github/workflows/integration.yml` — and it is *not* a default: there is no default, and an
unset value is a startup error. The difference matters, because "the mock is the default" is
how a benchmark ends up silently measuring the mock. It must be:

- **Deterministic** for a given `seed`. T4's reproducibility depends on it.
- **Schema-correct**: when `response_schema` is set, it returns conforming output.
- **Capable of failing on demand**, so timeout, unavailability and schema-exhaustion paths are
  testable without a GPU.
- **Plausibly slow** — a configurable small delay. A zero-latency mock hides race conditions that
  then appear for the first time on stage.

## Who implements which half

T3's file ownership does not include `backend/`, so T3 cannot own a module that lives there.
The split:

| Piece | Path | Owner |
|---|---|---|
| `InferenceClient` Protocol, request/response types, exceptions | `backend/inference/base.py` | **T2** |
| `MockInference` | `backend/inference/mock.py` | **T2** |
| vLLM adapter — the client that speaks to the server | `backend/inference/vllm_client.py` | **T2** |
| The vLLM server — config, launch, binding, teardown, benchmark | `infra/vllm/` | **T3** |

T3 owns **serving**, not the adapter. T3 fixes the endpoint contract the adapter codes against
(URL shape, model name, timeouts, health semantics) and records it in its handoff; T2 writes the
Python. T4 imports only from `backend/inference/base.py` and never reaches past it into either
implementation.

## The vLLM server (T3)

OpenAI-compatible API, Qwen3 8B, from committed config. Binding, `max_num_seqs ≤ 256`, teardown
and benchmark requirements are T3's, in `docs/task-graph.md` and `docs/infra-policy.md`.

**It is never the public internet-facing host.** Cubbie's sandbox cannot reach an SSH-tunnelled
endpoint, so if a Skill ever needs the platform it calls a CPU-only API gateway that holds the
disclosure logic, and that gateway reaches inference privately. See `docs/adr/0001`.

Selection is by environment: **`CAMPUSOS_INFERENCE_MODE=mock|vllm`**. There is **no default**.
Unset, empty or unrecognised is a startup error, not a silent fallback — "the benchmark was
secretly on the mock" is a result-invalidating failure for T4, and a default is exactly how that
happens. `.github/workflows/integration.yml` already sets this name, so the contract matches CI
rather than asking CI to change.

An earlier draft of this file said both "`mock` is the default" and "a missing value is a startup
error", which cannot both be true. The startup error wins.
