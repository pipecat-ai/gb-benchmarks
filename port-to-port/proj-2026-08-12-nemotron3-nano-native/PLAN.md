# Nemotron 3 Nano native-thinking rerun on RTX 5090

## Objective

Replace the serving-stack-confounded Nano comparison with a clean port-to-port
measurement of NVIDIA's official text-only NVFP4 checkpoint on the same local
RTX 5090 and pinned SGLang stack used for Nemotron 3.5 Lightning. Compare only
the model's native binary reasoning modes; do not impose a synthetic thinking
budget.

## Pinned inputs

- Model: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4`, Hugging Face revision
  `ce1b118ae66ec705d02c241525192832eb045fd3`.
- Local checkpoint:
  `/home/khkramer/src/nemotron-3-nano-5090/artifacts/checkpoints/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4`.
  The five local weight shards and model configuration files have been matched
  to the pinned upstream revision by SHA-256/Xet ETag.
- SGLang image:
  `lmsysorg/sglang@sha256:a04d9a1a7ffe371b05230aecab001d4ba2bfa0e5c137bc56409ecc4cbc3ac864`
  (HEAD `d59c1ddf70ee17fcc41c053ed38bd60bc6cc28cc`). This is a patched,
  dirty dev image; the immutable image digest, not HEAD alone, identifies the
  serving code. Save its status and full binary diff with the run evidence.
- NVIDIA references:
  [model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4)
  and [SGLang cookbook](https://github.com/NVIDIA-NeMo/Nemotron/blob/bf199a92e07b66e1215f48deb630bbe9a6758bd3/usage-cookbook/Nemotron-3-Nano/sglang_cookbook.ipynb).

## Serving configuration

Start only after the current Lightning filler campaign releases the GPU. Follow
NVIDIA's Nano SGLang recipe for the model/tool path, but use the newer
model-aware parser shipped and documented by the pinned SGLang image:

```text
--trust-remote-code
--attention-backend flashinfer
--reasoning-parser nemotron_3
--tool-call-parser qwen3_coder
--served-model-name nemotron-3-nano-30b-nvfp4
```

The pinned NVIDIA notebook says `deepseek-r1`, while the model card's vLLM
example says `nano_v3`. `nano_v3` is not registered in this SGLang image, and
its current Nano documentation/tests use `nemotron_3`; unlike `deepseek-r1`, it
correctly keys parsing off `enable_thinking` in both modes.

Apply these benchmark-local controls for the single 32 GB GPU; they are not
NVIDIA cookbook defaults. The initial 65,536-token smoke failed when a
thinking-on request reached 60,262 input tokens plus the 10,000-token output
ceiling. Use the checkpoint's native context limit instead:

```text
--max-running-requests 1
--context-length 262144
--mem-fraction-static 0.85
--kv-cache-dtype auto
```

Keep RadixAttention enabled and speculative decoding off. `auto` must resolve
the checkpoint's FP8 KV declaration to `fp8_e4m3`; retain FP32 temporal Mamba
state (and the default BF16 convolution state). Any context, memory, cache,
backend, or state-dtype fallback is a new serving configuration and must be
documented and re-smoked before collection.

## Benchmark cells

Use the natural prompt, `--max-turns 50`, `--function-call-timeout-secs 20`,
`--pipeline-idle-timeout-secs 900`, `--max-tokens 10000`, and the native
template toggle through `--openai-no-budget-thinking-toggle`:

| Cell | Template control | Sampling |
|---|---|---|
| thinking on | `enable_thinking=true` | temperature 0.6, top-p 0.95 |
| thinking off | `enable_thinking=false` | greedy (`temperature=0`; omit top-p) |

Map on/off to benchmark `--thinking high|none`. The on-cell sampler follows
NVIDIA's tool-calling recommendation (the separate pure-reasoning recommendation
is 1.0/1.0); the off cell follows NVIDIA's non-reasoning greedy recommendation.
`max_tokens=10000` is a shared output safety ceiling recommended by the model
card, not a reasoning budget. Send no `thinking_budget` or equivalent xarg.

The current harness also sends `force_nonempty_content=true` on this Nemotron
binary-toggle route. Permit it, but qualify both modes: with `nemotron_3` it is
normally a no-op and must never turn a completion truncated inside reasoning
into a plausible answer or tool call.

## Preflight and collection

1. Record GPU/process state; benchmark commit and task/system/rubric hashes;
   checkpoint hashes; image digest, dirty status, and binary diff; exact launch
   command; and the rendered template delta.
2. Treat the full server log as an acceptance gate. Require the intended model
   path, `NemotronHForCausalLM`, `modelopt_fp4`, SM120 FlashInfer-CUTLASS FP4
   dense/MoE kernels, FlashInfer attention, FP8/`fp8_e4m3` KV with no missing
   scale warning, FP32 temporal/BF16 convolution state, enabled Mamba/Radix
   caching, 262,144 context, one running request, and no speculative algorithm.
3. Save direct streaming response JSON for both modes. Verify reasoning
   separation, nonempty content, parsed tool calls, EOS ids 2/11 stopping before
   the ceiling, and assistant/tool-history reconstruction across multiple tool
   cycles. Confirm no budget control is transmitted and flag every invocation
   of the nonempty-content fallback.
4. Run and judge one complete port-to-port smoke per cell. Stop collection if
   serving, parsing, history, toggle, or truncation behavior is not verified.
5. Add a sequential collection script (no fail-fast wrapper) that calls
   `POST /flush_cache` before each independent conversation, records status and
   body, retries only while the endpoint becomes idle, and never begins that
   attempt without HTTP 200. Leave Radix caching enabled within a conversation;
   log an infrastructure failure and continue later attempts if flushing cannot
   be established.
6. Collect alternating on/off attempts for `r01` through `r25`, one request at a
   time. These are paired cohort/order labels, not seeded scenario variants.
   Log `RUN_START`/`RUN_EXIT`; every started benchmark gets its own `--log-json`
   and console log. Keep all model failures that produced raw JSON in the fixed
   N=25 cohorts.
7. Judge immutable batches with Claude Sonnet 4.6. Add a small read-only analysis
   script for per-run/per-turn completion and reasoning-token distributions,
   `finish_reason=length`, empty content, nonempty-fallback use, and malformed
   tools. Report those beside score, completion, terminal classes, pooled turn
   P50/P90, and total-time P50. Turn latency is the full model decision latency,
   including reasoning and completion generation.

## Publication

Add both Nano cells and the two already judged Lightning cells to a prompt-pure
canonical input manifest, then rebuild both natural leaderboard variants to
scratch with `build_primary_leaderboard.py` and review the diff before copying.
Do not hand-edit or delete historical budgeted Nano rows. The generated Nano
identity is `nemotron-3-nano-30b-nvfp4 (th=none|high, mt=10000,
base=127.0.0.1:8000)`; describe Local RTX 5090 / NVFP4 / SGLang in leaderboard
notes or README prose because the generated table has no hardware column.

Add the best new Nano cell to the README table/chart only if its unrounded score
is at least 80 and turn P50 is below four seconds. Preserve prompt hash
`68d2c77be6548b77cd2e65ca0489edb2080c4a652feeb11f5ef5317f91e4b1f0`
and rubric `port_to_port_primary_v1`. Document that co-published Lightning used
1.0/0.95 without a max-token ceiling and did not flush between conversations;
its latency regime is therefore not identical to this model-card-matched Nano
run.
