# Nemotron 3.5 Lightning on RTX 5090: binary reasoning benchmark plan

Status: revised after Fable review, 2026-08-11

## Decision and objective

Deploy the official NVFP4 Nemotron 3.5 Lightning checkpoint on the local
32 GB GeForce RTX 5090, validate structured tool calling, then compare the
model's two native reasoning modes on the natural port-to-port benchmark:

1. reasoning off;
2. reasoning on, unbounded (the model-card default).

There will be no finite thinking-budget or low/medium/high sweep. The model
card does not recommend budgets or define effort levels. vLLM's
`thinking_token_budget` forcibly ends a trace at runtime rather than selecting
a model-trained effort mode, and current vLLM has unresolved interactions with
tool calls and speculative decoding. Any future budget experiment is separate,
non-canonical work requiring explicit authorization.

## Authoritative sources and immutable inputs

- NVIDIA vLLM cookbook:
  <https://github.com/NVIDIA-NeMo/Nemotron/blob/main/usage-cookbook/Nemotron-3.5-Lightning/vllm_cookbook.ipynb>
- Official NVFP4 model card:
  <https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4>
- NVIDIA published evaluation recipes:
  <https://github.com/NVIDIA-NeMo/Gym/tree/main/nemotron_recipes/lightning-3.5>
- Fable's evidence review:
  `port-to-port/proj-2026-08-11-nemotron35-lightning/FABLE_REVIEW.md`
- Checkpoint: `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4`, revision
  `e7fa1b0bdaf462c67c7f0bf638addacd89fd3054`.
- Local snapshot:
  `/home/khkramer/.cache/huggingface/hub/models--nvidia--NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4/snapshots/e7fa1b0bdaf462c67c7f0bf638addacd89fd3054`
- Snapshot verification: 52/52 safetensor shards; safetensors total
  21,561,882,284 bytes; full 69-file tree 21,583,776,209 bytes.
- Container image:
  `vllm/vllm-openai@sha256:0a51ea5b4ae2dc5d81890e5173f54203d2a3ae0cfffe51b8fd2afd4391bfd967`
  (vLLM 0.27.1, build commit `6e448d0ea9bf3d88d898b65449ca6dc2aec170ac`).
- License: OpenMDW-1.1.

The checkpoint and image downloads completed successfully. The aiewf-evals
filler campaign completed all 30 slots and released the GPU; no process was
terminated to make the GPU available.

## Model-card-faithful request settings

Keep every variable except the native reasoning toggle fixed:

| Cell | Chat-template control | Temperature | Top-p | Client output cap |
|---|---|---:|---:|---|
| off | `enable_thinking=false` | 1.0 | 0.95 | none |
| on-unbounded | `enable_thinking=true` (or default) | 1.0 | 0.95 | none |

These are the model card and checkpoint `generation_config.json` sampling
settings. NVIDIA's cookbook separately suggests temperature 0.2 for a simple
reasoning-off example, but the model card is authoritative for this project
and using 0.2 only in the off cell would confound the comparison.

Do not send `max_tokens`, `max_completion_tokens`, `thinking_token_budget`,
`reasoning_effort`, or `vllm_xargs.thinking_budget`. NVIDIA's published
agentic evaluation recipes drop the client output cap. This also avoids the
known failure mode where an unbounded reasoning trace consumes a 4096-token
cap before producing a tool call.

Serve with `--reasoning-parser nemotron_v3`,
`--tool-call-parser qwen3_coder`, and `--enable-auto-tool-choice`.

Do not send `force_nonempty_content`: although the current model card mentions
it for coding agents, the pinned checkpoint's `chat_template.jinja` does not
implement that kwarg, and port-to-port is a tool-use simulation rather than a
coding agent. Do not pass an explicit `--reasoning-config`; vLLM derives it
from `nemotron_v3`, while an explicit config has a known double-parsing bug.

## Benchmark invariants

- Use the existing OpenAI-compatible Pipecat service and local base URL so the
  raw `ttfb_ms` (first streamed token) and `decision_ms` (first actionable
  result) semantics match existing rows. The evaluator reports turn p50/p90;
  it does not natively report p95.
- Keep all runs sequential against the one local endpoint.
- Use the current natural prompt version only and assert the recorded
  `task_prompt_version` in every raw artifact.
- Every run gets `--log-json runs/<stem>.json` and a console log. Failed runs
  with raw JSON remain benchmark data and are judged.
- Use `--max-turns 50 --function-call-timeout-secs 20`.
- Log `RUN_START` and `RUN_EXIT`; do not use fail-fast workers.
- Keep the same checkpoint, image digest, server process, context, kernel,
  prompt, and sampling across both cells.

The harness already has the correct binary Nemotron path:
`--openai-no-budget-thinking-toggle` sets
`chat_template_kwargs.enable_thinking`, removes the legacy budget field, and
accepts only `--thinking none|high`. Pass the model-card sampling through
`--openai-params-json`; no Lightning budget implementation is needed.

## Phase 1: final offline verification

1. Recount the pinned snapshot and retain the successful download log.
2. Retain the image pull log, digest, vLLM version, and build commit.
3. Verify from the exact container source that `NemotronHForCausalLM`,
   `modelopt_mixed`, `nemotron_v3`, `qwen3_coder`, MTP, DFlash, and DSpark are
   registered. CPU-only `vllm serve --help` cannot infer a device, so inspect
   source or wait for the GPU.
4. Run the existing regression tests covering the no-budget Nemotron toggle,
   and add a narrowly scoped regression only if the exact model-card sampler
   payload is not already asserted. The payload must contain no finite budget
   or max-token field.

## Phase 2: launch the base server

Reconfirm immediately before launch that there is no GPU compute process and
port 8000 is free. Launch by image digest and local snapshot path, capturing
the full server console log.

Use NVIDIA's documented consumer-Blackwell kernel path first:

- `--moe-backend marlin`; leave the linear backend on its checkpoint/platform
  selection rather than forcing Humming;
- `--kv-cache-dtype fp8`, and verify the effective dtype in the log;
- `--max-model-len 65536`;
- `--max-num-seqs 1` and `--max-num-batched-tokens 32768` for this sequential
  benchmark;
- prefix caching and async scheduling;
- `--mamba-backend flashinfer`;
- `--mamba-cache-mode align`;
- FP16 Mamba SSM cache, stochastic rounding, and 5 Philox rounds;
- the reasoning/tool parsers and automatic tool choice;
- served name `nemotron-3.5-lightning`, host `127.0.0.1`, port 8000.

Do not pass `--mamba-ssu-algorithm`: NVIDIA removed it from the current model
card while the release-day cookbook still contains the older flag.

The 65,536-token starting context is realistic on 32 GB: weights occupy about
20.08 GiB; the default 0.9 utilization budget is about 28.66 GiB; only 6 of 52
layers use attention, keeping the FP8 KV cache small at one sequence. If the
server OOMs, preserve the log and diagnose GPU-memory utilization and batched
prefill before reducing context to 32,768.

Do not lead with `flashinfer_b12x`. It is an opt-in native SM120 NVFP4 path,
but NVIDIA does not use it in a Lightning recipe and vLLM has an open SM120
illegal-memory-access report under a similar configuration. It can be a later,
separately labeled performance experiment cross-checked against Marlin output.

## Phase 3: correctness admission

Before any counted run, require:

1. `/health` and `/v1/models` succeed and return the expected served name.
2. A reasoning-off streamed response has final content and no reasoning trace.
3. A reasoning-on streamed response has parsed reasoning and final content,
   without an output cap.
4. Reasoning-off and reasoning-on streaming tool calls both contain valid JSON
   arguments and are parsed as structured tool calls.
5. A short multi-turn tool loop remains valid after assistant/tool history;
   confirm prior reasoning is not replayed incorrectly.
6. One full natural port-to-port smoke in each mode completes without malformed
   calls, empty responses, NaNs, parser leakage, truncation, or OOM. Save JSON
   and console logs for both smokes.

If reasoning-off cannot reliably call tools, report that as a native-mode
limitation rather than patching prompts or silently enabling thinking. If the
on-unbounded smoke runs away without acting, preserve it as evidence and stop
before launching 25 repetitions.

## Phase 4: canonical binary comparison

After clean smokes, run 25 natural-prompt repetitions for `off`, then 25 for
`on-unbounded`, sequentially, with one unique UTC batch timestamp. Use the
existing harness path and no client output cap. Conceptual command controls:

```text
--provider openai
--model nemotron-3.5-lightning
--openai-base-url http://127.0.0.1:8000/v1
--openai-no-budget-thinking-toggle
--openai-params-json {"temperature":1.0,"top_p":0.95}
--task-variant natural
--thinking none|high
--max-turns 50
--function-call-timeout-secs 20
--log-json runs/<stem>.json
```

Do not pass `--max-tokens` or `--thinking-budget`.

Judge every raw JSON with `evaluate_runs.py`, LLM report-accuracy judge, and
`claude-sonnet-4-6`. Summarize completion rate, overall score, TTFB and
decision-latency p50/p90, wall time, turns, malformed calls, empty responses,
termination reasons, per-turn completion tokens, and every
`finish_reason=length` occurrence. Inspect every failure rather than excluding
it. Run stems use the harness vocabulary `none` and `high`; batch notes define
`high` as native reasoning on, unbounded, with no client output cap.

This batch remains off-leaderboard until its artifacts and summary are
reviewed; updating canonical leaderboard files is a separate explicit step.

## Phase 5: speculative decoding after the binary base result

Do not mix speculative decoding into the canonical off/on comparison.

1. Test built-in MTP at 3 speculative tokens on a fixed replay set.
2. If memory permits, download and test DSpark at 3; NVIDIA recommends DSpark
   for DGX Spark and low-concurrency data-centre workloads.
3. Test DFlash only if it offers a plausible latency/acceptance advantage.
4. Compare correctness, accepted tokens, TTFB, actionable-decision latency,
   and end-to-end completion time against the Marlin base server.

Because this plan has no finite thinking budgets, DSpark/DFlash's vLLM V2
runner incompatibility with `thinking_token_budget` is irrelevant. Still run
both native reasoning modes in every speculative smoke and do not promote a
speculative configuration unless its outputs match the base server's
correctness envelope. DSpark forces vLLM's V2 runner; if that runner rejects
the NemotronH hybrid architecture, preserve the hard launch error and stop the
DSpark experiment rather than changing unrelated server controls.

## Stop conditions

Stop and preserve logs rather than improvising if any of these occurs:

- checkpoint revision or image digest differs from the recorded pin;
- CUDA/SM120 kernel compilation, Xid, or illegal-memory-access errors;
- model load exceeds VRAM;
- final content is empty, reasoning leaks into tool arguments, or tool-call
  JSON is malformed;
- on-unbounded repeatedly reasons without producing an action;
- another project reclaims the GPU;
- prompt revision, server configuration, sampler, or parser changes mid-batch.
