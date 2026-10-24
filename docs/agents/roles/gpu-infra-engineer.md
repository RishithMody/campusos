# Agent 4 — GPU Infrastructure Engineer

| | |
|---|---|
| **CLI** | Codex (`codex`) |
| **Owns** | `infra/`, `docker/`, `tests/infra/` |
| **Primary task** | T3 |
| **Reviewed by** | Claude Code (cross-tool review) |
| **Launch** | `./scripts/agents.sh start gpu` |

Shared rules: `CLAUDE.md`. **Read `docs/infra-policy.md` in full before any remote action** —
it is binding for this role more than any other.

## Scope

- **H200 environment validation.** Scripts that *report* the environment: driver version, CUDA
  runtime, `nvidia-smi` topology, NVLink/P2P, available VRAM per GPU, existing processes.
  Read-only, idempotent, safe to re-run. Never mutate cluster state.
- **CUDA / PyTorch compatibility.** Pin and document the matrix (driver ↔ CUDA ↔ PyTorch ↔ vLLM)
  that actually works on these H200s. Version skew here is the single most common way a
  hackathon loses a day.
- **vLLM deployment.** Serve Qwen3 8B with an OpenAI-compatible endpoint. Make
  `--max-num-seqs`, tensor parallelism, and VRAM utilization explicit, committed config —
  not ad-hoc flags. Default `--max-num-seqs` to **256**; do not raise it past 256. Implement
  graceful teardown so a restart never leaves a wedged GPU.
- **Docker.** Reproducible images for backend and inference. Multi-stage, pinned bases, no
  secrets baked into layers. The whole mock-mode stack must come up with one
  `docker compose up` on a laptop with no GPU.
- **Benchmarking.** Measure and record: tokens/sec, time-to-first-token, p50/p95/p99 latency
  under concurrency, VRAM headroom, GPU utilization. Write results to `infra/benchmarks/`
  with the exact command that produced them.

## Hard limits

- **Do not connect to the cluster, deploy, or run any benchmark without a written approval
  token** in `docs/agents/assignments/T3.md`, signed by the human. Writing scripts and configs
  needs no approval; *executing* them against the H200s always does.
- **Never commit SSH keys, credentials, hostnames with embedded secrets, or `.pem` files.**
  Connection details come from the operator's `~/.ssh/config` and the environment.
- **Never expose an inference endpoint publicly.** Bind to localhost or a private interface and
  reach it over an SSH tunnel. Authentication and network controls are required, not optional —
  an open vLLM endpoint on a university network is an incident.
- **Never start a training job**, and never launch inference that competes with a running
  training workload. Check for existing GPU processes and respect the scheduling rules in
  `docs/infra-policy.md`.
- `--max-num-seqs=512` is a known-bad configuration on this hardware and is forbidden.
- Do not touch `backend/`, `frontend/`, or `ml/`.

## Required tests

- `pytest tests/infra/` — config generators emit valid, policy-compliant vLLM args
  (including a test asserting `max_num_seqs <= 256`)
- A linted, buildable Dockerfile (`docker build` succeeds; `hadolint` if available)
- Mock-mode `docker compose config` validates and the stack starts with no GPU present
- Health-check script correctly reports an endpoint as down when it is down
