# Nemotron 3 Nano native-thinking rerun results

## Qualified stack

- Model: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4` at revision
  `ce1b118ae66ec705d02c241525192832eb045fd3`.
- Server: pinned SGLang image
  `lmsysorg/sglang@sha256:a04d9a1a7ffe371b05230aecab001d4ba2bfa0e5c137bc56409ecc4cbc3ac864`
  on one RTX 5090.
- Context: 262,144 tokens; one running request; FP8 KV cache; FP32 Mamba
  state; FlashInfer attention and FP4 MoE; unified Radix/Mamba cache enabled;
  speculative decoding disabled.
- Parser qualification: `nemotron_3` reasoning and `qwen3_coder` tool parsing
  passed the direct multi-turn off/on protocol probe. Thinking off emitted no
  reasoning; thinking on emitted parsed reasoning and tools.

The earlier 65,536-token smoke is retained as invalid configuration evidence:
one accumulated request reached 60,262 input tokens, leaving insufficient room
for the model-card 10,000-token output allowance. All production runs used the
native 262,144-token context and had no context-limit response.

## Production design

- Prompt: natural, hash
  `68d2c77be6548b77cd2e65ca0489edb2080c4a652feeb11f5ef5317f91e4b1f0`.
- Rubric: `port_to_port_primary_v1`.
- 25 thinking-off and 25 native-thinking runs in strict alternating order.
- Cache flushed successfully before each independent conversation; prefix
  caching remained enabled within each conversation.
- Shared controls: 50 maximum turns, 20-second function timeout, 900-second
  pipeline idle timeout, `max_tokens=10000`, no thinking budget.
- Thinking off: `enable_thinking=false`, temperature 0.
- Thinking on: `enable_thinking=true`, temperature 0.6, top-p 0.95.
- Judge: Claude Sonnet 4.6 with LLM report-accuracy judging.

## Judged results

| Mode | N | Primary /100 | Complete | Turn P50 | Turn P90 | Total P50 | Terminals |
|---|---:|---:|---:|---:|---:|---:|---|
| Native thinking on | 25 | 37 | 12% (3/25) | 6,753.2 ms | 31,781.8 ms | 358.18 s | 3 strict success, 12 no-tool stall, 10 other failure |
| Thinking off | 25 | 13 | 0% (0/25) | 246.4 ms | 282.5 ms | 62.17 s | 25 max-turn exhaustion |

Telemetry found no malformed tool calls or genuinely empty streams. One
thinking-on turn consumed the full 10,000 completion tokens without visible
content or a tool call, consistent with a reasoning-only completion exhausting
the generation allowance. Pipecat artifacts do not retain raw finish reasons
or reasoning-token counts, so the direct protocol JSON and server log provide
the missing parser/stream coverage.

## Publication

Both Nano cells and both previously judged Nemotron 3.5 Lightning cells were
added to the prompt-pure natural standalone leaderboards. A scratch rebuild of
the pre-publication source set reproduced each committed table body exactly;
the final table diff adds only the four new sorted rows. The Nano labels omit
`tb=` because the binary native-thinking route sent no budget.

Nano does not meet the README gate of score at least 80 and turn P50 below four
seconds, so the root README table/chart is intentionally unchanged.

Primary evidence:

- Raw production runs: `runs/nemotron-3-nano-30b-nvfp4-natural-*-sglang-prod-native-20260812T192200Z-r*.json`
- Judge output: `runs/eval-nemotron3-nano-native-prod-20260812T192200Z/`
- Telemetry: `analysis-prod-native-20260812T192200Z.json`
- Direct probe: `protocol-262k-20260812T191601Z.json`
- Server log: `server-262k-20260812T191440Z.log`
- Canonical source manifest: `leaderboard-natural-nano-lightning-manifest.tsv`
