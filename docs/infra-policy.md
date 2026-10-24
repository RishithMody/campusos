# Infrastructure execution policy — H200 cluster

**Binding on every agent and every human operator.** The GPU Infrastructure Engineer and the
ML Engineer must read this in full before any remote action.

## The separation

| Where | What runs there |
|---|---|
| **Local Mac** | All coding agents. All editing, testing, linting, mock-mode runs, Docker builds. |
| **2× H200 cluster** | vLLM inference, model evaluation, synthetic-data experiments at scale, LoRA training, GPU benchmarking. |

Coding agents **never** need the cluster. Anything that cannot be developed against a mock is
scoped wrong. This is not only a cost rule: it keeps the demo runnable when the cluster is
unavailable, which on a hackathon weekend it will be.

---

## 1. Explicit approval is required before any GPU execution

**Writing** scripts, configs, and Dockerfiles needs no approval.
**Executing** anything against the H200s always does.

No agent may connect to the cluster, start inference, run a benchmark, or begin training
without a **human-signed approval token** in its assignment file:

```markdown
| **GPU approval** | GRANTED 2026-10-25 by Rishith · scope: vLLM serve Qwen3-8B, 1 GPU · budget: 4 GPU-hours · expires 2026-10-26T00:00Z |
```

Rules for the token:

- Only the human writes it. **No agent self-approves, and no agent approves on the human's
  behalf** — including the Orchestrator, which may only *draft* a request.
- It must name a **scope** (what will run) and a **budget** (GPU-hours) and an **expiry**.
- It covers one activity. Approval to serve inference is not approval to train.
- `NONE` or absent means **stop and ask**. An expired token means stop and ask.

Training is the most expensive action in this project. The default answer is no.

## 2. Access

- Connect over **SSH** using the operator's existing `~/.ssh/config` host alias, or an approved
  remote job interface (e.g. a Slurm-style submission script) if the cluster provides one.
- **Never store SSH keys, private keys, passwords, or tokens in Git.** The `pre-commit` hook
  blocks `*.pem`, `id_rsa`, `.env`, and credential files, but the hook is a backstop, not
  permission to try.
- Credentials and hostnames come from the operator's environment and SSH config. Scripts take
  the host as a **parameter or environment variable** with no default — never a hardcoded
  hostname, and never a hostname with an embedded secret.
- Agents run locally. An agent that wants something run on the cluster writes the exact command
  into its handoff for the human to execute or approve. Do not improvise a remote shell.

## 3. Logs and checkpoints

- Remote job logs stream to a file on the cluster and are **fetched back** to
  `infra/logs/<job-id>/` or `ml/runs/<run>/logs/` so results survive the session.
- Checkpoints stay on the cluster or in object storage. **Never commit weights,
  checkpoints, or large datasets.** Commit the config, the git commit hash, the dataset hash,
  and the metrics — enough to reproduce, nothing heavy.
- Every run records: command, config, git commit, dataset hash, start/end time, GPU-hours used.
  A run without its config is not a result.

## 4. Scheduling — no competing workloads

Two GPUs, several possible workloads, and a shared machine.

- **Before starting anything, check what is already running:** `nvidia-smi`, and the process
  list. An agent that launches onto a busy GPU can OOM someone else's job.
- **Never run training while a live inference workload is serving the demo.** Demo inference
  always wins. If a rehearsal or judging session is possible, training does not start.
- Declare intent before taking a GPU: record it in `docs/agents/status.md` (via the
  Orchestrator) so the other agents and the human can see the cluster is in use.
- Prefer **one GPU for inference, one for experiments** over sharing a single GPU between a
  latency-sensitive and a throughput-heavy workload.
- Always implement **graceful teardown**. A killed vLLM process can leave a wedged GPU that
  needs a reset, which costs far more time than stopping cleanly. Verify stop/restart leaves
  no orphaned process.

## 5. vLLM configuration limits

Known-bad configuration on this hardware, learned the expensive way:

- **`--max-num-seqs` must not exceed 256.** `512` has caused GPU wedging on these H200s and is
  forbidden. Default to 256 and lower it if you see instability.
- Set `--gpu-memory-utilization` explicitly; leave headroom rather than claiming all VRAM.
- Make tensor-parallel size explicit and committed, not inferred.
- All serving flags live in **committed config** under `infra/`, never typed ad hoc into a
  shell. A config nobody can find again is not reproducible.

## 6. Never expose inference publicly

- Bind vLLM to **localhost or a private interface only.** Never `0.0.0.0` on a routable
  interface.
- Reach it through an **SSH tunnel**. No public ingress, no ngrok-style tunnel to the open
  internet, no security-group hole "just for the demo".
- Require **authentication** in front of the endpoint. An unauthenticated vLLM server on a
  university network is an open compute resource and a security incident.
- Rate-limit and set sane token caps. An open or unbounded endpoint will be found and abused.

## 7. CI never touches the GPUs

GitHub Actions runs on free-tier runners with **no GPU access and no cluster credentials.**
Every test in CI runs against mocks. If a test needs a GPU, it is not a CI test — mark it
`@pytest.mark.gpu` and exclude it (`-m 'not gpu'`).

---

## Checklist before any remote command

- [ ] A current, unexpired, human-signed approval token covers **this exact activity**
- [ ] I checked what is already running on the GPUs
- [ ] No live inference workload will be disrupted
- [ ] The command is recorded, with its config, so the run is reproducible
- [ ] Logs will be fetched back to the repo
- [ ] No credential, key, or hostname-with-secret will be committed
- [ ] `max_num_seqs` ≤ 256 if this is a vLLM launch
- [ ] The endpoint will not be publicly reachable

Any unchecked box means **stop and ask the human.**
