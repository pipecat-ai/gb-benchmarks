# Nemotron 3.5 Lightning SGLang recovery plan

Updated: 2026-08-11 after three vLLM long-context engine failures.

## Sources and pins

- NVIDIA SGLang cookbook at NVIDIA-NeMo/Nemotron commit
  `bf199a92e07b66e1215f48deb630bbe9a6758bd3`:
  `usage-cookbook/Nemotron-3.5-Lightning/sglang_cookbook.ipynb`.
- Model snapshot:
  `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4` revision
  `e7fa1b0bdaf462c67c7f0bf638addacd89fd3054`.
- Pull NVIDIA's cookbook image tag
  `lmsysorg/sglang:dev-nemotron3-5-lightning`, then pin the resolved digest in
  the launch script and logs.

The NVIDIA notebook is written for one H100 80 GB. The RTX 5090 is listed as
supported by the model card, but NVIDIA does not publish a 5090-specific
SGLang command. Hardware accommodations below must therefore be explicit and
must not change request sampling or reasoning behavior.

## Base launch

Begin with NVIDIA's non-speculative SGLang recipe:

- `--mamba-ssm-dtype float16`;
- `--mem-fraction-static 0.85`;
- `--cuda-graph-max-bs-decode 16`;
- `--reasoning-parser nemotron_3`;
- `--tool-call-parser qwen3_coder`;
- served name `nemotron-3.5-lightning`, host `127.0.0.1`, port 8000.

Preserve the notebook's Docker runtime flags: `SYS_NICE`, host IPC/network,
16 GiB shared memory, unlimited memlock, 64 MiB stack, and
`SAFETENSORS_FAST_GPU=1`.

Add only two benchmark-specific constraints on the first launch:

- `--context-length 65536`, matching the requested medium/long benchmark
  context and the vLLM comparison. This is load-bearing on 32 GB because the
  checkpoint otherwise advertises its full 1,048,576-token context;
- `--max-running-requests 1`, because runs on one endpoint must be sequential
  and the 5090 has 32 GB VRAM.

Before launch, verify the pinned image's `Nemotron3Detector` recognizes this
checkpoint's `<think>` / `</think>` markers; the earlier similarly named
`dev-nemotron3-5-lighting` image does not.

Do not force KV-cache dtype, quantization, MoE runner, attention backend,
Mamba backend, radix-cache strategy, or prefill chunk sizes. Verify SGLang's
resolved values in the log. Do not add multimodal GPU-pool flags unless the
dedicated cookbook image actually reserves such a pool for this text model.

If admission fails for memory, preserve the complete log. Change one
serve-time memory control at a time, preferring a lower static-memory fraction
or decode graph batch cap before reducing the 65,536-token context. Label any
such launch as a 5090 adaptation rather than NVIDIA's exact H100 recipe.

## Request controls

For both benchmark cells send:

- `temperature=1.0`;
- `top_p=0.95`;
- no finite client `max_tokens`;
- no reasoning-budget field.

Reasoning is a binary native toggle:

- off: `chat_template_kwargs.enable_thinking=false`;
- on-unbounded: default thinking or
  `chat_template_kwargs.enable_thinking=true`.

For tool calls, also send
`chat_template_kwargs.force_nonempty_content=true`, as the NVIDIA SGLang
cookbook explicitly requires this when reasoning and tool parsing are used
together. The harness must apply it in both modes so the only experimental
difference is `enable_thinking`.

The notebook's two-pass `ThinkingBudgetClient` is not used. It implements a
client-side cap by stopping and resuming generation, which is outside this
binary native comparison.

## Admission and soak

Before counted runs require:

1. `/v1/models` reports the expected served name.
2. A streamed reasoning-off response has content and no reasoning trace.
3. A streamed reasoning-on response has parsed reasoning and final content;
   content contains no literal `</think>` or `<tool_call>` markers.
4. Both modes produce structured tool calls with valid JSON arguments using
   `force_nonempty_content=true`.
5. A multi-turn tool-history smoke succeeds.
6. A full port-to-port thinking-on run reaches a terminal artifact without
   engine death.
7. Five sequential thinking-on soak runs remain healthy, since all three vLLM
   failures appeared only after long accumulated prompts.

Every benchmark smoke/soak run gets `--log-json` and a console log. Use
`--max-turns 50`, `--function-call-timeout-secs 20`, and the explicit
900-second pipeline idle timeout. A failed run with JSON remains data.

## Counted comparison and judging

After admission, collect fresh prompt-consistent batches sequentially on the
single endpoint:

- 25 reasoning-off runs;
- 25 reasoning-on/unbounded runs.

Use the same server process, sampling values, no-cap policy, and benchmark
settings for both cells. Health-gate between runs and stop the worker if the
server becomes unavailable so connection-error artifacts are not mistaken
for model results.

Judge every raw JSON artifact with `evaluate_runs.py`, Claude Sonnet 4.6, and
the LLM report-accuracy judge. Report task completion, judge score, terminal
reason, latency distributions, completion-token distributions, and any
`finish_reason=length` events separately for the two modes.

Only after the base binary result is stable should speculative decoding be
tested. NVIDIA's SGLang defaults are MTP (5 steps, 6 draft tokens), DFlash
block size 4, and DSpark block size 3; those are separate deployments and not
part of this initial reasoning comparison.
